import io
import uuid
import logging
from typing import Optional
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from apps.accounts.models import User
from apps.assessments.models import Assessment, TestAttempt, AttemptStatus
from .models import Certificate, CertificateStatus

logger = logging.getLogger(__name__)


class CertificateService:
    """
    Authoritative Participation Certificate Service for Craft Society.
    Enforces:
    1. Maximum one certificate per (exam, student) via database UniqueConstraint.
    2. Immutability of (exam, student, attempt, certificate_id, printed_name) starting at creation.
    3. Authoritative attempt locking: First qualifying submitted non-disqualified attempt establishes and locks Certificate.attempt.
    4. Safe atomic get_or_create with race handling.
    5. Pure vector ReportLab PDF generation.
    """

    @classmethod
    def generate_certificate_id(cls, assessment: Assessment) -> str:
        """
        Generates a unique deterministic certificate ID.
        Format: CS-CERT-{YYYY}-{RANDOM_HEX_8}
        """
        year = timezone.now().year
        for _ in range(10):
            candidate_id = f"CS-CERT-{year}-{uuid.uuid4().hex[:8].upper()}"
            if not Certificate.objects.filter(certificate_id=candidate_id).exists():
                return candidate_id
        return f"CS-CERT-{year}-{uuid.uuid4().hex.upper()[:12]}"

    @classmethod
    def get_candidate_printed_name(cls, student: User) -> str:
        """
        Resolves candidate printed name with strict precedence:
        1. StudentProfile.certificate_name (if set and non-empty)
        2. User.display_name (if set and non-empty)
        3. User.email
        """
        profile = getattr(student, 'student_profile', None)
        if profile and profile.certificate_name and profile.certificate_name.strip():
            return profile.certificate_name.strip()
        if student.display_name and student.display_name.strip():
            return student.display_name.strip()
        return student.email

    @classmethod
    def generate_or_get_certificate(
        cls,
        attempt: TestAttempt,
        actor: Optional[User] = None
    ) -> Optional[Certificate]:
        """
        Creates or retrieves the participation certificate for a qualifying attempt.
        Strict Invariants:
        - If certificate already exists for (attempt.assessment, attempt.student):
          returns existing certificate immediately without altering its attempt or printed_name.
        - If no certificate exists:
          locates the first submitted, non-disqualified attempt for this (assessment, student)
          and establishes the certificate record.
        - Disqualified attempts NEVER establish a certificate.
        - Unsubmitted attempts NEVER establish a certificate.
        """
        assessment = attempt.assessment
        student = attempt.student

        # Check existing certificate first
        existing_cert = Certificate.objects.filter(exam=assessment, student=student).first()
        if existing_cert:
            if existing_cert.status == CertificateStatus.PENDING:
                cls.generate_pdf(existing_cert)
                existing_cert.refresh_from_db()
            return existing_cert

        # Eligibility check for new creation:
        # Must be submitted and not disqualified
        if attempt.status != AttemptStatus.SUBMITTED or attempt.is_disqualified:
            logger.info(
                f"Attempt {attempt.id} not eligible for certificate: "
                f"status={attempt.status}, is_disqualified={attempt.is_disqualified}"
            )
            return None

        # Determine the first qualifying submitted non-disqualified attempt
        qualifying_attempt = TestAttempt.objects.filter(
            assessment=assessment,
            student=student,
            status=AttemptStatus.SUBMITTED,
            is_disqualified=False
        ).order_by('created_at').first()

        if not qualifying_attempt:
            return None

        printed_name = cls.get_candidate_printed_name(student)
        cert_id = cls.generate_certificate_id(assessment)

        try:
            with transaction.atomic():
                cert, created = Certificate.objects.get_or_create(
                    exam=assessment,
                    student=student,
                    defaults={
                        'attempt': qualifying_attempt,
                        'certificate_id': cert_id,
                        'printed_name': printed_name,
                        'status': CertificateStatus.PENDING,
                        'metadata': {
                            'qualifying_attempt_id': str(qualifying_attempt.id),
                            'attempt_number': qualifying_attempt.attempt_number,
                            'created_by': str(actor.id) if actor else 'system'
                        }
                    }
                )
        except IntegrityError:
            # Race condition: another concurrent process created the certificate
            cert = Certificate.objects.get(exam=assessment, student=student)
            created = False

        if created or cert.status == CertificateStatus.PENDING:
            cls.generate_pdf(cert)
            cert.refresh_from_db()

        return cert

    @classmethod
    def retry_generation(
        cls,
        certificate: Certificate,
        actor: Optional[User] = None
    ) -> Certificate:
        """
        Retries PDF generation for a PENDING or FAILED certificate.
        Immutability rule: Preserves original (exam, student, attempt, certificate_id, printed_name).
        """
        if certificate.status == CertificateStatus.REVOKED:
            raise PermissionDenied("Cannot regenerate a revoked certificate.")

        # Re-run PDF generation
        cls.generate_pdf(certificate)
        certificate.refresh_from_db()
        return certificate

    @classmethod
    def generate_pdf(cls, certificate: Certificate) -> bool:
        """
        Renders pure vector PDF certificate via ReportLab and persists it to certificate.pdf_file.
        Returns True on success, False on failure without raising (Zero Rollback Invariant).
        """
        if certificate.status == CertificateStatus.REVOKED:
            logger.warning(f"Skipping PDF generation for revoked certificate {certificate.certificate_id}")
            return False

        try:
            pdf_bytes = cls._render_vector_certificate_pdf(certificate)
            file_name = f"certificate_{certificate.certificate_id}.pdf"

            certificate.pdf_file.save(file_name, ContentFile(pdf_bytes), save=False)
            certificate.status = CertificateStatus.ISSUED
            certificate.issued_at = timezone.now()
            certificate.verification_url = f"/api/v1/public/certificates/verify/{certificate.certificate_id}/"
            certificate.metadata = {
                **certificate.metadata,
                'generated_at': timezone.now().isoformat(),
                'file_size_bytes': len(pdf_bytes)
            }
            certificate.save(update_fields=['pdf_file', 'status', 'issued_at', 'verification_url', 'metadata', 'updated_at'])
            logger.info(f"Successfully generated certificate PDF for {certificate.certificate_id}")
            return True

        except Exception as exc:
            logger.error(
                f"Failed to generate certificate PDF for {certificate.certificate_id}: {exc}",
                exc_info=True
            )
            try:
                certificate.status = CertificateStatus.FAILED
                certificate.metadata = {
                    **certificate.metadata,
                    'error': str(exc),
                    'failed_at': timezone.now().isoformat()
                }
                certificate.save(update_fields=['status', 'metadata', 'updated_at'])
            except Exception as save_exc:
                logger.error(f"Failed to update certificate status to FAILED: {save_exc}")
            return False

    @classmethod
    def _render_vector_certificate_pdf(cls, certificate: Certificate) -> bytes:
        """
        Renders a landscape A4 vector certificate matching Craft Society branding.
        Uses pure ReportLab canvas drawing primitives.
        """
        buf = io.BytesIO()
        width, height = landscape(A4)  # 841.89 x 595.28 pt

        c = canvas.Canvas(buf, pagesize=landscape(A4))
        c.setTitle(f"Certificate of Participation - {certificate.printed_name}")
        c.setAuthor("Craft Society Examination Board")
        c.setSubject(f"Examination: {certificate.exam.title}")

        # 1. Background Fill (Subtle warm off-white)
        c.setFillColor(colors.HexColor('#FCFDFE'))
        c.rect(0, 0, width, height, fill=1, stroke=0)

        # 2. Outer Border (Deep Slate)
        c.setStrokeColor(colors.HexColor('#0F172A'))
        c.setLineWidth(4)
        c.rect(24, 24, width - 48, height - 48)

        # 3. Inner Decorative Border (Gold / Amber)
        c.setStrokeColor(colors.HexColor('#D97706'))
        c.setLineWidth(1.5)
        c.rect(32, 32, width - 64, height - 64)

        # 4. Corner Geometric Accents (Gold)
        accent_size = 14
        corners = [
            (32, 32),
            (width - 32 - accent_size, 32),
            (32, height - 32 - accent_size),
            (width - 32 - accent_size, height - 32 - accent_size),
        ]
        c.setFillColor(colors.HexColor('#D97706'))
        for cx, cy in corners:
            c.rect(cx, cy, accent_size, accent_size, fill=1, stroke=0)

        center_x = width / 2.0

        # 5. Header: Organization Emblem / Seal Graphic
        emblem_y = height - 75
        c.setStrokeColor(colors.HexColor('#D97706'))
        c.setLineWidth(1.5)
        c.circle(center_x, emblem_y, 22, stroke=1, fill=0)
        c.setStrokeColor(colors.HexColor('#0F172A'))
        c.setLineWidth(0.8)
        c.circle(center_x, emblem_y, 18, stroke=1, fill=0)

        c.setFont('Helvetica-Bold', 12)
        c.setFillColor(colors.HexColor('#0F172A'))
        c.drawCentredString(center_x, emblem_y - 4, "CS")

        # 6. Organization Title
        c.setFont('Helvetica-Bold', 22)
        c.setFillColor(colors.HexColor('#0F172A'))
        c.drawCentredString(center_x, height - 120, "CRAFT SOCIETY")

        # Subtitle Divider
        c.setStrokeColor(colors.HexColor('#D97706'))
        c.setLineWidth(1.2)
        c.line(center_x - 120, height - 128, center_x + 120, height - 128)

        # 7. Certificate Category
        c.setFont('Helvetica-Bold', 14)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(center_x, height - 150, "CERTIFICATE OF PARTICIPATION")

        # 8. Presentation Preamble
        c.setFont('Helvetica-Oblique', 12)
        c.setFillColor(colors.HexColor('#64748B'))
        c.drawCentredString(center_x, height - 185, "This is to certify that")

        # 9. Candidate Name (Prominent)
        c.setFont('Helvetica-Bold', 26)
        c.setFillColor(colors.HexColor('#0F172A'))
        c.drawCentredString(center_x, height - 225, certificate.printed_name)

        # Name Underline Flourish
        name_width = min(360, max(220, len(certificate.printed_name) * 14))
        c.setStrokeColor(colors.HexColor('#D97706'))
        c.setLineWidth(1.5)
        c.line(center_x - (name_width / 2.0), height - 235, center_x + (name_width / 2.0), height - 235)

        # 10. Examination Participation Text
        c.setFont('Helvetica', 12)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(center_x, height - 268, "has successfully participated in the at-home examination")

        # Exam Title
        c.setFont('Helvetica-Bold', 18)
        c.setFillColor(colors.HexColor('#1E293B'))
        c.drawCentredString(center_x, height - 298, certificate.exam.title)

        # Date & Conduct
        issue_date_str = (
            certificate.issued_at.strftime("%B %d, %Y")
            if certificate.issued_at
            else timezone.now().strftime("%B %d, %Y")
        )
        c.setFont('Helvetica', 11)
        c.setFillColor(colors.HexColor('#64748B'))
        c.drawCentredString(
            center_x,
            height - 330,
            f"Conducted under Craft Society Examination Standards on {issue_date_str}"
        )

        # 11. Signatures / Authority Section
        sig_y = 110
        # Left Authority
        c.setStrokeColor(colors.HexColor('#94A3B8'))
        c.setLineWidth(1)
        c.line(90, sig_y, 250, sig_y)
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(colors.HexColor('#1E293B'))
        c.drawCentredString(170, sig_y - 15, "Examination Controller")
        c.setFont('Helvetica', 9)
        c.setFillColor(colors.HexColor('#64748B'))
        c.drawCentredString(170, sig_y - 28, "Craft Society Assessment Board")

        # Center Official Seal
        c.setStrokeColor(colors.HexColor('#D97706'))
        c.setLineWidth(1.2)
        c.circle(center_x, sig_y - 5, 26, stroke=1, fill=0)
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(colors.HexColor('#D97706'))
        c.drawCentredString(center_x, sig_y + 1, "OFFICIAL")
        c.drawCentredString(center_x, sig_y - 11, "VERIFIED")

        # Right Authority
        c.setStrokeColor(colors.HexColor('#94A3B8'))
        c.setLineWidth(1)
        c.line(width - 250, sig_y, width - 90, sig_y)
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(colors.HexColor('#1E293B'))
        c.drawCentredString(width - 170, sig_y - 15, "Academic Director")
        c.setFont('Helvetica', 9)
        c.setFillColor(colors.HexColor('#64748B'))
        c.drawCentredString(width - 170, sig_y - 28, "Craft Society Board")

        # 12. Bottom Verification Bar
        c.setFont('Courier', 9)
        c.setFillColor(colors.HexColor('#64748B'))
        c.drawString(45, 42, f"Certificate ID: {certificate.certificate_id}")

        verification_text = f"Verify at: /verify/{certificate.certificate_id}"
        c.drawRightString(width - 45, 42, verification_text)

        c.save()
        return buf.getvalue()
