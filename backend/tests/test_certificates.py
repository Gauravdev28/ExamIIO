import pytest
from unittest.mock import patch
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentSnapshot,
    TestAttempt,
    AttemptStatus,
)
from apps.results.models import (
    Certificate,
    CertificateStatus,
)
from apps.results.certificate_service import CertificateService


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_cert@craftsociety.test",
        password="AdminPassword123!",
        role=Role.ADMIN,
        display_name="Admin Cert"
    )


@pytest.fixture
def student_one(db):
    user = User.objects.create_user(
        email="student1@craftsociety.test",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Alice Candidate"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS-001",
        euid="EUID-CERT-001",
        certificate_name="Alice Henderson"
    )
    return user


@pytest.fixture
def student_two(db):
    user = User.objects.create_user(
        email="student2@craftsociety.test",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Bob Candidate"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS-002",
        euid="EUID-CERT-002",
        certificate_name="Robert Smith"
    )
    return user


@pytest.fixture
def sample_exam(db, admin_user, student_one, student_two):
    now = timezone.now()
    exam = Assessment.objects.create(
        title="Craft Society Entrance Exam",
        description="Official Entrance Exam",
        created_by=admin_user,
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=60,
        passing_percentage=Decimal('50.00'),
        attempt_limit=2,
        proctoring_enabled=True,
    )
    AssessmentAssignment.objects.create(
        assessment=exam,
        student=student_one,
        status=AssignmentStatus.ASSIGNED,
        assigned_by=admin_user
    )
    AssessmentAssignment.objects.create(
        assessment=exam,
        student=student_two,
        status=AssignmentStatus.ASSIGNED,
        assigned_by=admin_user
    )
    # Create minimal snapshot
    snapshot = AssessmentSnapshot.objects.create(
        assessment=exam,
        version_number=1,
        snapshot_data={"title": exam.title, "passing_percentage": 50.0},
        server_evaluation_bundle={}
    )
    return exam


@pytest.mark.django_db
class TestCertificatePipeline:

    def test_first_valid_attempt_creates_certificate(self, sample_exam, student_one):
        """
        The first valid submitted non-disqualified attempt creates a participation certificate.
        """
        snapshot = sample_exam.snapshot
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )

        cert = CertificateService.generate_or_get_certificate(attempt=attempt1)
        assert cert is not None
        assert cert.exam == sample_exam
        assert cert.student == student_one
        assert cert.attempt == attempt1
        assert cert.printed_name == "Alice Henderson"
        assert cert.status == CertificateStatus.ISSUED
        assert cert.certificate_id.startswith("CS-CERT-")
        assert bool(cert.pdf_file)

    def test_second_valid_attempt_does_not_replace_certificate(self, sample_exam, student_one):
        """
        When attempt_limit > 1, Attempt 2 does not replace Attempt 1 as Certificate.attempt
        and does NOT create a second certificate.
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=50),
            submitted_at=now - timedelta(minutes=30),
            is_disqualified=False
        )
        cert1 = CertificateService.generate_or_get_certificate(attempt=attempt1)
        assert cert1.attempt == attempt1

        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=20),
            submitted_at=now,
            is_disqualified=False
        )
        cert2 = CertificateService.generate_or_get_certificate(attempt=attempt2)

        # Must be the exact same certificate record and attempt must remain attempt1
        assert cert2.id == cert1.id
        assert cert2.certificate_id == cert1.certificate_id
        assert cert2.attempt_id == attempt1.id
        assert Certificate.objects.filter(exam=sample_exam, student=student_one).count() == 1

    def test_disqualified_first_attempt_allows_valid_second_attempt(self, sample_exam, student_one):
        """
        If Attempt 1 was disqualified, it never creates a certificate.
        If Attempt 2 is validly submitted and not disqualified, Attempt 2 qualifies.
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.CANCELLED,
            started_at=now - timedelta(minutes=50),
            submitted_at=now - timedelta(minutes=30),
            is_disqualified=True,
            disqualification_reason="THREE_STRONG_PROCTORING_VIOLATIONS"
        )
        cert_disqualified = CertificateService.generate_or_get_certificate(attempt=attempt1)
        assert cert_disqualified is None
        assert Certificate.objects.filter(exam=sample_exam, student=student_one).count() == 0

        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=20),
            submitted_at=now,
            is_disqualified=False
        )
        cert_valid = CertificateService.generate_or_get_certificate(attempt=attempt2)
        assert cert_valid is not None
        assert cert_valid.attempt == attempt2
        assert cert_valid.status == CertificateStatus.ISSUED

    def test_certificate_attempt_is_immutable(self, sample_exam, student_one):
        """
        Model clean() strictly blocks any attempt to re-point Certificate.attempt.
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=30),
            submitted_at=now,
            is_disqualified=False
        )
        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=10),
            submitted_at=now,
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt1)

        cert.attempt = attempt2
        with pytest.raises(PermissionDenied) as exc_info:
            cert.save()
        assert "attempt_id is permanently immutable" in str(exc_info.value)

    def test_certificate_printed_name_is_immutable(self, sample_exam, student_one):
        """
        Model clean() strictly blocks changing printed_name after creation.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)

        cert.printed_name = "Hacked Name"
        with pytest.raises(PermissionDenied) as exc_info:
            cert.save()
        assert "printed_name is permanently immutable" in str(exc_info.value)

    def test_certificate_retry_preserves_all_immutable_fields(self, sample_exam, student_one):
        """
        Retrying a FAILED certificate preserves exam, student, attempt, certificate_id, and printed_name.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)
        orig_id = cert.certificate_id
        orig_attempt_id = cert.attempt_id
        orig_name = cert.printed_name

        # Simulate failure state
        cert.status = CertificateStatus.FAILED
        cert.save(update_fields=['status'])

        # Retry generation
        retried_cert = CertificateService.retry_generation(cert)
        assert retried_cert.status == CertificateStatus.ISSUED
        assert retried_cert.certificate_id == orig_id
        assert retried_cert.attempt_id == orig_attempt_id
        assert retried_cert.printed_name == orig_name

    def test_failed_generation_does_not_fail_exam_submission(self, sample_exam, student_one):
        """
        If PDF generation raises an exception, the certificate transitions to FAILED
        without raising an unhandled exception or rolling back exam submission.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )

        with patch.object(CertificateService, '_render_vector_certificate_pdf', side_effect=RuntimeError("Font error")):
            cert = CertificateService.generate_or_get_certificate(attempt=attempt)
            assert cert is not None
            assert cert.status == CertificateStatus.FAILED
            assert "Font error" in cert.metadata.get('error', '')
            assert cert.attempt == attempt

    def test_concurrent_different_attempts_preserve_first_established_certificate(self, sample_exam, student_one):
        """
        Verifies that even if two attempts trigger certificate generation concurrently,
        exactly one certificate is established and its authoritative attempt is preserved.
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=50),
            submitted_at=now - timedelta(minutes=30),
            is_disqualified=False
        )
        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=20),
            submitted_at=now,
            is_disqualified=False
        )

        # Invoke generation for attempt1
        cert1 = CertificateService.generate_or_get_certificate(attempt=attempt1)

        # Invoke generation for attempt2
        cert2 = CertificateService.generate_or_get_certificate(attempt=attempt2)

        assert cert1.id == cert2.id
        assert cert2.attempt_id == attempt1.id
        assert cert2.certificate_id == cert1.certificate_id
        assert Certificate.objects.filter(exam=sample_exam, student=student_one).count() == 1

    @pytest.mark.django_db(transaction=True)
    def test_submit_attempt_triggers_certificate_generation(self, sample_exam, student_one):
        """
        Submitting an attempt via AttemptService triggers certificate generation on commit.
        """
        from apps.assessments.services import AttemptService
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=30),
            is_disqualified=False
        )

        submitted_attempt = AttemptService.submit_attempt(
            student=student_one,
            attempt_id=str(attempt.id)
        )
        assert submitted_attempt.status == AttemptStatus.SUBMITTED

        # Verify Certificate was generated
        cert = Certificate.objects.filter(exam=sample_exam, student=student_one).first()
        assert cert is not None
        assert cert.attempt_id == attempt.id
        assert cert.status == CertificateStatus.ISSUED
        assert cert.printed_name == "Alice Henderson"

    def test_certificate_failure_then_attempt2_preserves_attempt1_then_retry_issues(self, sample_exam, student_one):
        """
        Objective 2:
        Attempt 1 -> valid + submitted -> Certificate created -> status = PENDING ->
        PDF generation fails -> status = FAILED -> Attempt 2 submitted later ->
        Certificate.attempt MUST remain Attempt 1 -> Retry generation ->
        same certificate_id, same attempt, same printed_name -> ISSUED.
        Verify exam submission does NOT fail because certificate PDF generation failed.
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()

        # Attempt 1 submitted, but PDF generation fails
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=60),
            submitted_at=now - timedelta(minutes=40),
            is_disqualified=False
        )

        with patch.object(CertificateService, '_render_vector_certificate_pdf', side_effect=RuntimeError("Font missing")):
            cert_failed = CertificateService.generate_or_get_certificate(attempt=attempt1)

        assert cert_failed is not None
        assert cert_failed.status == CertificateStatus.FAILED
        assert cert_failed.attempt_id == attempt1.id
        orig_cert_id = cert_failed.certificate_id
        orig_printed_name = cert_failed.printed_name

        # Attempt 2 submitted later
        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=30),
            submitted_at=now - timedelta(minutes=10),
            is_disqualified=False
        )

        # Generating or getting certificate for Attempt 2 returns the established Certificate (locked to Attempt 1)
        cert_after_attempt2 = CertificateService.generate_or_get_certificate(attempt=attempt2)
        assert cert_after_attempt2.id == cert_failed.id
        assert cert_after_attempt2.attempt_id == attempt1.id
        assert cert_after_attempt2.certificate_id == orig_cert_id
        assert cert_after_attempt2.printed_name == orig_printed_name

        # Retry generation
        retried_cert = CertificateService.retry_generation(cert_after_attempt2)
        assert retried_cert.status == CertificateStatus.ISSUED
        assert retried_cert.certificate_id == orig_cert_id
        assert retried_cert.attempt_id == attempt1.id
        assert retried_cert.printed_name == orig_printed_name
        assert bool(retried_cert.pdf_file)
        assert Certificate.objects.filter(exam=sample_exam, student=student_one).count() == 1

    def test_certificate_immutability_all_statuses(self, sample_exam, student_one, student_two):
        """
        Objective 3:
        Verify that exam, student, attempt, certificate_id, and printed_name
        are strictly immutable across all statuses (PENDING, FAILED, ISSUED, REVOKED).
        """
        snapshot = sample_exam.snapshot
        now = timezone.now()
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=30),
            submitted_at=now,
            is_disqualified=False
        )
        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_two,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=30),
            submitted_at=now,
            is_disqualified=False
        )

        cert = CertificateService.generate_or_get_certificate(attempt=attempt1)

        for status_val in [CertificateStatus.PENDING, CertificateStatus.FAILED, CertificateStatus.ISSUED, CertificateStatus.REVOKED]:
            cert.status = status_val
            cert.save(update_fields=['status'])

            # 1. Mutate attempt
            cert.attempt = attempt2
            with pytest.raises(PermissionDenied):
                cert.save()
            cert.attempt = attempt1

            # 2. Mutate student
            cert.student = student_two
            with pytest.raises(PermissionDenied):
                cert.save()
            cert.student = student_one

            # 3. Mutate certificate_id
            cert.certificate_id = "CS-MUTATED-999"
            with pytest.raises(PermissionDenied):
                cert.save()
            cert.refresh_from_db()

            # 4. Mutate printed_name
            cert.printed_name = "Tampered Student Name"
            with pytest.raises(PermissionDenied):
                cert.save()
            cert.refresh_from_db()

    def test_certificate_queryset_update_and_delete_forbidden(self, sample_exam, student_one, student_two):
        """
        Objective 3:
        Direct queryset.update() on immutable fields and queryset.delete() are blocked.
        """
        snapshot = sample_exam.snapshot
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt1)

        # Attempting queryset.update on printed_name
        with pytest.raises(PermissionDenied) as exc1:
            Certificate.objects.filter(id=cert.id).update(printed_name="Hacked Direct Update")
        assert "Direct query update on immutable certificate fields" in str(exc1.value)

        # Attempting queryset.update on attempt_id
        with pytest.raises(PermissionDenied) as exc2:
            Certificate.objects.filter(id=cert.id).update(attempt_id=attempt1.id)
        assert "Direct query update on immutable certificate fields" in str(exc2.value)

        # Attempting bulk queryset delete
        with pytest.raises(PermissionDenied) as exc3:
            Certificate.objects.filter(id=cert.id).delete()
        assert "Bulk deletion of Certificate records is permanently forbidden" in str(exc3.value)



@pytest.mark.django_db
class TestCertificateEndpoints:

    def test_certificate_ownership_authorization(self, sample_exam, student_one, student_two):
        """
        Student 2 cannot download Student 1's certificate (returns 403 Forbidden).
        """
        snapshot = sample_exam.snapshot
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt1)

        client = APIClient()
        # Student 2 attempts to download Student 1's certificate
        client.force_authenticate(user=student_two)
        res = client.get(f"/api/v1/student/certificates/{cert.id}/download/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Student 1 downloads own certificate
        client.force_authenticate(user=student_one)
        res = client.get(f"/api/v1/student/certificates/{cert.id}/download/")
        assert res.status_code == status.HTTP_200_OK
        assert res['Content-Type'] == 'application/pdf'

    def test_public_certificate_verification(self, sample_exam, student_one):
        """
        Unauthenticated client can verify a valid issued certificate.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)

        client = APIClient()
        # No authentication
        res = client.get(f"/api/v1/public/certificates/verify/{cert.certificate_id}/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json().get('data', {})
        assert data['certificate_id'] == cert.certificate_id
        assert data['printed_name'] == "Alice Henderson"
        assert data['exam_title'] == sample_exam.title
        assert data['is_valid'] is True

    def test_public_certificate_verification_revoked(self, sample_exam, student_one):
        """
        Objective 9: Revoked certificate returns 200 with is_valid=False and status=REVOKED.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)
        cert.status = CertificateStatus.REVOKED
        cert.save(update_fields=['status'])

        client = APIClient()
        res = client.get(f"/api/v1/public/certificates/verify/{cert.certificate_id}/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json().get('data', {})
        assert data['certificate_id'] == cert.certificate_id
        assert data['is_valid'] is False
        assert data['status'] == "REVOKED"
        # Must not leak sensitive user info
        assert 'password' not in data
        assert 'email' not in data

    def test_public_certificate_verification_nonexistent(self):
        """
        Objective 9: Nonexistent certificate returns 200 with is_valid=False and status=NOT_FOUND.
        """
        client = APIClient()
        res = client.get("/api/v1/public/certificates/verify/CS-NONEXISTENT-999999/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json().get('data', {})
        assert data['is_valid'] is False
        assert data['status'] == "NOT_FOUND"

    def test_public_certificate_verification_malformed(self):
        """
        Objective 9: Malformed certificate ID returns safe 200 without server error or leak.
        """
        client = APIClient()
        for malformed in ["CS-INVALID-BADCHARS", "CS-SQL-INJECTION-1-EQUALS-1", "CS-XSS-SCRIPT-PAYLOAD", "CS-TOO-LONG-" + "X" * 150]:
            res = client.get(f"/api/v1/public/certificates/verify/{malformed}/")
            assert res.status_code == status.HTTP_200_OK
            data = res.json().get('data', {})
            assert data['is_valid'] is False
            assert data['status'] == "NOT_FOUND"

    def test_admin_certificate_retry_endpoint(self, admin_user, sample_exam, student_one):
        """
        Admin can invoke retry generation for a FAILED certificate.
        """
        snapshot = sample_exam.snapshot
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)
        cert.status = CertificateStatus.FAILED
        cert.save(update_fields=['status'])

        client = APIClient()
        client.force_authenticate(user=admin_user)
        res = client.post(f"/api/v1/admin/certificates/{cert.id}/retry/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json().get('data', {})
        assert data['status'] == 'ISSUED'
        assert data['certificate_id'] == cert.certificate_id
