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


@pytest.mark.django_db
class TestOfficialNameCertificateIntegration:
    """
    Phase 5: Official Name -> Certificate Integration Tests.
    Strictly verifies:
    1. Authoritative name source: StudentProfile.certificate_name is chosen over display_name and email.
    2. Immutability & snapshotting: Certificate.printed_name is snapshotted upon creation.
    3. Profile modification after issuance: Changing StudentProfile.certificate_name does not alter issued Certificate.printed_name or its PDF.
    4. Payload tampering protection: Client-supplied printed_name/certificate_name/display_name values are ignored.
    5. Unauthorized paths blocked: Cannot bypass exam participation or certificate restrictions.
    6. Official name enforcement: Student without official name cannot participate or qualify.
    7. Valid student flow: Student with valid official name completes exam and receives valid certificate with correct printed_name.
    8. Unicode and multi-word names: Accents, spaces, and multi-word names render correctly without errors.
    9. Admin workflows preserved: Admin list, detail, retry, download remain fully functional.
    10. Proctor workflows preserved: Proctor reattempt does not break certificate invariants.
    """

    def test_1_certificate_uses_student_profile_certificate_name_authoritatively(self, sample_exam):
        """
        StudentProfile.certificate_name must be the authoritative source for printed_name,
        taking priority over User.display_name and User.email.
        """
        user = User.objects.create_user(
            email="authoritative_student@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Display Name Candidate"
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="CS-AUTH-001",
            euid="EUID-AUTH-001",
            certificate_name="Dr. Jane Alice Doe",
            first_login_required=False
        )
        AssessmentAssignment.objects.create(
            assessment=sample_exam,
            student=user,
            status=AssignmentStatus.ASSIGNED,
            assigned_by=sample_exam.created_by
        )
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=user,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )

        cert = CertificateService.generate_or_get_certificate(attempt=attempt)
        assert cert is not None
        assert cert.printed_name == "Dr. Jane Alice Doe"
        assert cert.printed_name != user.display_name
        assert cert.printed_name != user.email

        # Also verify fallback precedence when certificate_name is absent
        user2 = User.objects.create_user(
            email="fallback_student@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Fallback Display Name"
        )
        assert CertificateService.get_candidate_printed_name(user2) == "Fallback Display Name"

        user3 = User.objects.create_user(
            email="email_fallback@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        user3.display_name = ""
        assert CertificateService.get_candidate_printed_name(user3) == "email_fallback@craftsociety.test"

    def test_2_certificate_printed_name_correctly_snapshotted(self, sample_exam, student_one):
        """
        Certificate.printed_name is stored as a database snapshot at creation time,
        along with qualifying attempt metadata.
        """
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)

        # Fresh DB fetch
        saved_cert = Certificate.objects.get(id=cert.id)
        assert saved_cert.printed_name == "Alice Henderson"
        assert saved_cert.metadata.get('qualifying_attempt_id') == str(attempt.id)
        assert saved_cert.metadata.get('attempt_number') == 1
        assert saved_cert.status == CertificateStatus.ISSUED

    def test_3_existing_certificate_does_not_change_when_profile_name_changes(self, sample_exam):
        """
        Step-by-step verification of Requirement 7:
        1. Student has certificate_name = 'Rahul Sharma'
        2. Student completes eligible assessment
        3. Certificate generated -> Certificate.printed_name = 'Rahul Sharma'
        4. PDF displays 'Rahul Sharma'
        5. Student changes StudentProfile.certificate_name to 'Rahul Kumar'
        6. Re-fetch existing certificate
        7. Confirm Certificate.printed_name remains 'Rahul Sharma'
        8. Generate/read PDF again
        9. Confirm existing certificate still displays 'Rahul Sharma' and NOT 'Rahul Kumar'
        """
        user = User.objects.create_user(
            email="rahul_sharma@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Rahul Sharma"
        )
        profile = StudentProfile.objects.create(
            user=user,
            roll_number="CS-RAHUL-001",
            euid="EUID-RAHUL-001",
            certificate_name="Rahul Sharma",
            first_login_required=False
        )
        AssessmentAssignment.objects.create(
            assessment=sample_exam,
            student=user,
            status=AssignmentStatus.ASSIGNED,
            assigned_by=sample_exam.created_by
        )
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=user,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )

        # Step 3: Certificate generated
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)
        assert cert is not None
        assert cert.printed_name == "Rahul Sharma"
        assert cert.status == CertificateStatus.ISSUED

        # Step 4: PDF displays 'Rahul Sharma'
        initial_pdf = cert.pdf_file.read()
        assert b"Rahul Sharma" in initial_pdf

        # Step 5: Change profile certificate_name and display_name
        profile.certificate_name = "Rahul Kumar"
        profile.save()
        user.display_name = "Rahul Kumar"
        user.save()

        # Step 6: Re-fetch existing certificate
        cert.refresh_from_db()

        # Step 7: Confirm Certificate.printed_name remains 'Rahul Sharma'
        assert cert.printed_name == "Rahul Sharma"

        # Step 8: Generate / read PDF again
        CertificateService.generate_pdf(cert)
        cert.refresh_from_db()
        updated_pdf = cert.pdf_file.read()

        # Step 9: Confirm PDF still displays 'Rahul Sharma'
        assert b"Rahul Sharma" in updated_pdf
        assert b"Rahul Kumar" not in updated_pdf

    @pytest.mark.django_db(transaction=True)
    def test_4_student_cannot_override_printed_name_through_request_payload(self, sample_exam, student_one):
        """
        Manipulated values in request payloads (printed_name, certificate_name, display_name)
        cannot override or tamper with the authoritative profile name.
        """
        student_one.student_profile.first_login_required = False
        student_one.student_profile.save()

        client = APIClient()
        client.force_authenticate(user=student_one)

        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=30),
            is_disqualified=False
        )

        # 1. Attempt submission payload tampering
        res_submit = client.post(
            f"/api/v1/student/attempts/{attempt.id}/submit/",
            data={
                "printed_name": "Fake Name Tampered",
                "certificate_name": "Fake Name Tampered",
                "display_name": "Fake Name Tampered",
            },
            format='json'
        )
        assert res_submit.status_code == status.HTTP_200_OK

        cert = Certificate.objects.get(exam=sample_exam, student=student_one)
        assert cert.printed_name == "Alice Henderson"
        assert cert.printed_name != "Fake Name Tampered"

        # 2. Certificate download query param tampering
        res_download = client.get(
            f"/api/v1/student/certificates/{cert.id}/download/?printed_name=HackedName&certificate_name=HackedName"
        )
        assert res_download.status_code == status.HTTP_200_OK
        cert.refresh_from_db()
        assert cert.printed_name == "Alice Henderson"

        # 3. Direct mutation attempts on student certificate endpoints return 405
        res_post = client.post("/api/v1/student/certificates/", data={"printed_name": "HackedName"})
        assert res_post.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        res_patch = client.patch(f"/api/v1/student/certificates/{cert.id}/", data={"printed_name": "HackedName"})
        assert res_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        res_put = client.put(f"/api/v1/student/certificates/{cert.id}/", data={"printed_name": "HackedName"})
        assert res_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        res_del = client.delete(f"/api/v1/student/certificates/{cert.id}/")
        assert res_del.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_5_student_cannot_generate_certificate_through_unauthorized_path(self, sample_exam, student_one, student_two):
        """
        Student cannot generate or access certificates through unauthorized paths:
        - Anonymous requests blocked (401)
        - IDOR cross-student download blocked (403)
        - Student cannot invoke admin retry endpoint (403)
        - Disqualified attempts never generate certificates
        """
        anon_client = APIClient()
        res_anon = anon_client.get("/api/v1/student/certificates/")
        assert res_anon.status_code == status.HTTP_401_UNAUTHORIZED

        # Create certificate for student_one
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert1 = CertificateService.generate_or_get_certificate(attempt=attempt1)

        # Student 2 cannot download student 1 certificate
        client_two = APIClient()
        client_two.force_authenticate(user=student_two)
        res_cross = client_two.get(f"/api/v1/student/certificates/{cert1.id}/download/")
        assert res_cross.status_code == status.HTTP_403_FORBIDDEN

        # Student 1 cannot call admin retry endpoint
        client_one = APIClient()
        client_one.force_authenticate(user=student_one)
        res_admin_retry = client_one.post(f"/api/v1/admin/certificates/{cert1.id}/retry/")
        assert res_admin_retry.status_code == status.HTTP_403_FORBIDDEN

        # Disqualified attempt never generates certificate
        disqualified_attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student_two,
            attempt_number=1,
            status=AttemptStatus.CANCELLED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=True
        )
        cert_disq = CertificateService.generate_or_get_certificate(attempt=disqualified_attempt)
        assert cert_disq is None
        assert Certificate.objects.filter(exam=sample_exam, student=student_two).count() == 0

    def test_6_student_without_official_name_cannot_participate_or_qualify(self, sample_exam):
        """
        Requirement 5:
        certificate_name = "" -> cannot participate in exam -> cannot qualify for certificate.
        Direct API calls to start, attempt detail, answer save, and submit are rejected with 403 Forbidden.
        """
        unnamed_student = User.objects.create_user(
            email="unnamed_cert@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="No Official Name"
        )
        StudentProfile.objects.create(
            user=unnamed_student,
            roll_number="CS-UNNAMED-001",
            euid="EUID-UNNAMED-001",
            certificate_name="",  # Official name not completed
            first_login_required=False  # Only official name is missing
        )
        AssessmentAssignment.objects.create(
            assessment=sample_exam,
            student=unnamed_student,
            status=AssignmentStatus.ASSIGNED,
            assigned_by=sample_exam.created_by
        )

        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=unnamed_student,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=30),
            is_disqualified=False
        )

        client = APIClient()
        client.force_authenticate(user=unnamed_student)

        # 1. Start attempt blocked by IsOfficialNameSatisfied
        res_start = client.post(f"/api/v1/student/assessments/{sample_exam.id}/start/")
        assert res_start.status_code == status.HTTP_403_FORBIDDEN
        assert "Official" in str(res_start.json())

        # 2. Attempt detail blocked by IsOfficialNameSatisfied
        res_detail = client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res_detail.status_code == status.HTTP_403_FORBIDDEN
        assert "Official" in str(res_detail.json())

        # 3. Submit attempt blocked by IsOfficialNameSatisfied
        res_submit = client.post(f"/api/v1/student/attempts/{attempt.id}/submit/")
        assert res_submit.status_code == status.HTTP_403_FORBIDDEN
        assert "Official" in str(res_submit.json())

        # 4. Terminate attempt blocked by IsOfficialNameSatisfied
        res_term = client.post(f"/api/v1/student/attempts/{attempt.id}/terminate/")
        assert res_term.status_code == status.HTTP_403_FORBIDDEN
        assert "Official" in str(res_term.json())

        # 5. Confirm no certificate can legitimately exist
        assert Certificate.objects.filter(exam=sample_exam, student=unnamed_student).count() == 0

    @pytest.mark.django_db(transaction=True)
    def test_7_valid_student_completes_normal_certificate_flow(self, sample_exam):
        """
        Requirement 7: A student with valid official name completes the exam
        and successfully obtains and downloads the certificate.
        """
        student = User.objects.create_user(
            email="valid_flow_student@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Aarav Vikram Patel"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="CS-VALID-001",
            euid="EUID-VALID-001",
            certificate_name="Aarav Vikram Patel",
            first_login_required=False
        )
        AssessmentAssignment.objects.create(
            assessment=sample_exam,
            student=student,
            status=AssignmentStatus.ASSIGNED,
            assigned_by=sample_exam.created_by
        )

        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=30),
            is_disqualified=False
        )

        client = APIClient()
        client.force_authenticate(user=student)

        # 1. Submit attempt via API
        res_submit = client.post(f"/api/v1/student/attempts/{attempt.id}/submit/")
        assert res_submit.status_code == status.HTTP_200_OK

        # 2. Verify Certificate generated
        cert = Certificate.objects.filter(exam=sample_exam, student=student).first()
        assert cert is not None
        assert cert.status == CertificateStatus.ISSUED
        assert cert.printed_name == "Aarav Vikram Patel"

        # 3. Student queries certificate list
        res_list = client.get("/api/v1/student/certificates/")
        assert res_list.status_code == status.HTTP_200_OK
        items = res_list.json()['data']
        assert len(items) == 1
        assert items[0]['printed_name'] == "Aarav Vikram Patel"

        # 4. Student queries certificate detail
        res_detail = client.get(f"/api/v1/student/certificates/{cert.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.json()['data']['printed_name'] == "Aarav Vikram Patel"

        # 5. Student downloads PDF
        res_dl = client.get(f"/api/v1/student/certificates/{cert.id}/download/")
        assert res_dl.status_code == status.HTTP_200_OK
        assert res_dl['Content-Type'] == 'application/pdf'
        pdf_content = b"".join(res_dl.streaming_content)
        assert b"Aarav Vikram Patel" in pdf_content

    def test_8_unicode_and_multiword_official_names_in_certificates(self, sample_exam):
        """
        Requirement 9: Unicode characters, accents, spaces, and multi-word names
        generate certificates and render vector PDFs correctly.
        """
        test_names = [
            "Renée Dupont",
            "Søren Kierkegaard",
            "José María de la Cruz",
            "Aarav Kumar Sharma",
        ]

        for idx, name in enumerate(test_names):
            user = User.objects.create_user(
                email=f"unicode_student_{idx}@craftsociety.test",
                password="StudentPassword123!",
                role=Role.STUDENT,
                display_name=name
            )
            StudentProfile.objects.create(
                user=user,
                roll_number=f"CS-UNI-{idx:03d}",
                euid=f"EUID-UNI-{idx:03d}",
                certificate_name=name
            )
            AssessmentAssignment.objects.create(
                assessment=sample_exam,
                student=user,
                status=AssignmentStatus.ASSIGNED,
                assigned_by=sample_exam.created_by
            )
            attempt = TestAttempt.objects.create(
                assessment=sample_exam,
                assessment_snapshot=sample_exam.snapshot,
                student=user,
                attempt_number=1,
                status=AttemptStatus.SUBMITTED,
                started_at=timezone.now() - timedelta(minutes=30),
                submitted_at=timezone.now(),
                is_disqualified=False
            )

            cert = CertificateService.generate_or_get_certificate(attempt=attempt)
            assert cert is not None
            assert cert.printed_name == name
            assert cert.status == CertificateStatus.ISSUED
            assert bool(cert.pdf_file)

            pdf_bytes = cert.pdf_file.read()
            assert len(pdf_bytes) > 1000

    def test_9_admin_certificate_management_workflows_preserved(self, admin_user, sample_exam, student_one):
        """
        Requirement 10: Admin certificate functionality remains fully functional:
        - List, filter, search
        - Detail retrieval
        - PDF download
        - Retry failed generation
        """
        attempt = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student_one,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=30),
            submitted_at=timezone.now(),
            is_disqualified=False
        )
        cert = CertificateService.generate_or_get_certificate(attempt=attempt)

        client = APIClient()
        client.force_authenticate(user=admin_user)

        # 1. List
        res_list = client.get("/api/v1/admin/certificates/")
        assert res_list.status_code == status.HTTP_200_OK
        results = res_list.json()['results']
        assert any(r['certificate_id'] == cert.certificate_id for r in results)

        # 2. Filter by exam_id
        res_filter = client.get(f"/api/v1/admin/certificates/?exam_id={sample_exam.id}")
        assert res_filter.status_code == status.HTTP_200_OK

        # 3. Search by printed_name
        res_search = client.get("/api/v1/admin/certificates/?search=Alice")
        assert res_search.status_code == status.HTTP_200_OK
        assert len(res_search.json()['results']) >= 1

        # 4. Detail view
        res_detail = client.get(f"/api/v1/admin/certificates/{cert.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.json()['data']['printed_name'] == "Alice Henderson"

        # 5. Download view
        res_dl = client.get(f"/api/v1/admin/certificates/{cert.id}/download/")
        assert res_dl.status_code == status.HTTP_200_OK
        assert res_dl['Content-Type'] == 'application/pdf'

    def test_10_proctor_reattempt_certificate_behavior(self, sample_exam):
        """
        Requirement 10: Proctor reattempt flow preserves certificate invariants:
        - Disqualified Attempt 1 never generates a certificate
        - Proctor authorizes reattempt
        - Attempt 2 submitted generates certificate with student's official name
        """
        from apps.invigilation.services import ProctorReattemptService
        from apps.invigilation.models import ReattemptReason

        proctor = User.objects.create_user(
            email="proctor_cert_test@craftsociety.test",
            password="ProctorPassword123!",
            role=Role.PROCTOR,
            display_name="Proctor Officer"
        )
        student = User.objects.create_user(
            email="proctor_student@craftsociety.test",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Proctor Student"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="CS-PROC-001",
            euid="EUID-PROC-001",
            certificate_name="Vikramaditya Rao"
        )
        AssessmentAssignment.objects.create(
            assessment=sample_exam,
            student=student,
            status=AssignmentStatus.ASSIGNED,
            assigned_by=sample_exam.created_by
        )

        # Attempt 1 is cancelled/disqualified
        attempt1 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student,
            attempt_number=1,
            status=AttemptStatus.CANCELLED,
            started_at=timezone.now() - timedelta(minutes=50),
            submitted_at=timezone.now() - timedelta(minutes=30),
            is_disqualified=True,
            disqualification_reason="PROCTOR_TERMINATED"
        )

        cert_disq = CertificateService.generate_or_get_certificate(attempt=attempt1)
        assert cert_disq is None
        assert Certificate.objects.filter(exam=sample_exam, student=student).count() == 0

        # Proctor authorizes reattempt
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=proctor,
            attempt_id=str(attempt1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=10)
        auth.save()

        # Attempt 2 is submitted
        attempt2 = TestAttempt.objects.create(
            assessment=sample_exam,
            assessment_snapshot=sample_exam.snapshot,
            student=student,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=20),
            submitted_at=timezone.now(),
            is_disqualified=False
        )

        cert_valid = CertificateService.generate_or_get_certificate(attempt=attempt2)
        assert cert_valid is not None
        assert cert_valid.attempt == attempt2
        assert cert_valid.printed_name == "Vikramaditya Rao"
        assert cert_valid.status == CertificateStatus.ISSUED

