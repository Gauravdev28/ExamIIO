import pytest
from datetime import timedelta
from unittest.mock import patch
from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role, AuditLog
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
)
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    VersionStatus,
)
from apps.results.models import Certificate, CertificateStatus
from apps.results.certificate_service import CertificateService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_user_a(db):
    user = User.objects.create_user(
        email="student_a_sec@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student A Sec"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-SEC-A",
        euid="CG-ROLL-SEC-A",
        certificate_name="Student A Official",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_user_b(db):
    user = User.objects.create_user(
        email="student_b_sec@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student B Sec"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-SEC-B",
        euid="CG-ROLL-SEC-B",
        certificate_name="Student B Official",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_user_empty(db):
    user = User.objects.create_user(
        email="student_empty_sec@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Empty Sec"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-SEC-EMPTY",
        euid="CG-ROLL-SEC-EMPTY",
        certificate_name="",
        first_login_required=False
    )
    return user


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_sec@codeguard.local",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="proctor_sec@codeguard.local",
        password="ProctorPassword123!",
        role=Role.PROCTOR
    )


@pytest.fixture
def published_assessment(db, admin_user, student_user_a, student_user_empty):
    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Phase 6 Security Audit Assessment",
        description="Comprehensive exam security verification",
        created_by=admin_user,
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=5),
        duration_minutes=60,
        attempt_limit=1,
    )

    for student in [student_user_a, student_user_empty]:
        AssessmentAssignment.objects.create(
            assessment=assessment,
            student=student,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED,
        )

    q = Question.objects.create(question_type=QuestionType.MCQ, created_by=admin_user)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="Sample MCQ Question",
        question_type=QuestionType.MCQ,
        points=10,
        status=VersionStatus.PUBLISHED,
        created_by=admin_user,
        type_config={"options": [{"id": "opt_1", "text": "Correct Option", "is_correct": True}]},
    )

    snap = AssessmentSnapshot.objects.create(
        assessment=assessment,
        version_number=1,
        snapshot_data={
            "title": assessment.title,
            "questions": [
                {
                    "snapshot_question_id": str(q.id),
                    "title": "Sample MCQ Question",
                    "description": "Choose the correct option",
                    "question_type": "MCQ",
                    "points": 10,
                }
            ]
        }
    )

    AssessmentSnapshotQuestion.objects.create(
        snapshot=snap,
        question_version=qv,
        snapshot_question_id=str(q.id),
        order=1,
        points=10,
        question_type=qv.question_type,
        type_config=qv.type_config,
    )

    return assessment


@pytest.mark.django_db
class TestOfficialNameSecurityAndValidationHardening:
    """
    Phase 6 Official Name Security & Validation Comprehensive Verification Suite
    """

    PROFILE_ENDPOINT = "/api/v1/student/profile/"

    # ==========================================================================
    # 1. Input Validation & Type Hardening (Section 2 & 3)
    # ==========================================================================

    def test_01_non_string_json_inputs_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        invalid_payloads = [
            {"official_name": 12345},
            {"official_name": 45.67},
            {"official_name": True},
            {"official_name": False},
            {"official_name": ["Rahul", "Sharma"]},
            {"official_name": {"name": "Rahul"}},
            {"certificate_name": 98765},
            {"certificate_name": ["List"]},
        ]

        for payload in invalid_payloads:
            res = api_client.patch(self.PROFILE_ENDPOINT, payload, format="json")
            assert res.status_code == status.HTTP_400_BAD_REQUEST, f"Failed for {payload}"

        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Student A Official"

    def test_02_empty_and_whitespace_inputs_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        empty_inputs = ["", "   ", "\t", "\t\t", "\n", " \n \t "]
        for inp in empty_inputs:
            res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": inp})
            assert res.status_code == status.HTTP_400_BAD_REQUEST

        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Student A Official"

    def test_03_control_characters_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        control_inputs = [
            "Rahul\x00Sharma",      # Null byte
            "Rahul\x07Sharma",      # Bell
            "Rahul\x1bSharma",      # Escape
            "Rahul\x7fSharma",      # Delete
            "Rahul\x85Sharma",      # Next Line (C1 control)
            "Rahul\r\nSharma",      # Carriage return + newline
        ]
        for inp in control_inputs:
            res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": inp})
            assert res.status_code == status.HTTP_400_BAD_REQUEST
            err = res.data.get("error", {})
            assert "control characters" in str(err).lower() or res.status_code == status.HTTP_400_BAD_REQUEST

        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Student A Official"

    def test_04_length_boundaries(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        # Minimum length: 1 char rejected, 2 chars accepted
        res_min_invalid = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "A"})
        assert res_min_invalid.status_code == status.HTTP_400_BAD_REQUEST

        res_min_valid = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Al"})
        assert res_min_valid.status_code == status.HTTP_200_OK

        # Maximum length: 255 chars accepted, 256 chars rejected
        name_255 = "A" * 255
        res_255 = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": name_255})
        assert res_255.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        assert len(student_user_a.student_profile.certificate_name) == 255

        name_256 = "A" * 256
        res_256 = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": name_256})
        assert res_256.status_code == status.HTTP_400_BAD_REQUEST

    def test_05_legitimate_unicode_and_punctuation_names_accepted(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        valid_names = [
            "Rahul Sharma",
            "Dr. Jane Alice Doe",
            "José María de la Cruz",
            "Renée Dupont",
            "Søren Kierkegaard",
            "Aarav Kumar Sharma",
            "Jean-Luc Picard",
            "Conan O'Brien",
            "李明",
        ]

        for name in valid_names:
            res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": name})
            assert res.status_code == status.HTTP_200_OK
            student_user_a.student_profile.refresh_from_db()
            assert student_user_a.student_profile.certificate_name == name

    def test_06_server_side_normalization(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "   Rahul Sharma   "})
        assert res.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        student_user_a.refresh_from_db()

        assert student_user_a.student_profile.certificate_name == "Rahul Sharma"
        assert student_user_a.display_name == "Rahul Sharma"

    # ==========================================================================
    # 2. Authorization / IDOR Security (Section 4)
    # ==========================================================================

    def test_07_idor_tampering_attempts_prevented(self, api_client, student_user_a, student_user_b):
        api_client.force_authenticate(user=student_user_a)

        # Attempt to target Student B through various ID injection fields
        payload = {
            "official_name": "Tampered Name",
            "profile_id": str(student_user_b.student_profile.id),
            "student_id": str(student_user_b.id),
            "user_id": str(student_user_b.id),
            "roll_number": student_user_b.student_profile.roll_number,
            "email": student_user_b.email,
        }
        res = api_client.patch(self.PROFILE_ENDPOINT, payload)
        assert res.status_code == status.HTTP_200_OK

        # Student A is updated
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Tampered Name"

        # Student B remains completely unchanged
        student_user_b.student_profile.refresh_from_db()
        student_user_b.refresh_from_db()
        assert student_user_b.student_profile.certificate_name == "Student B Official"
        assert student_user_b.display_name == "Student B Sec"

    # ==========================================================================
    # 3. Role Security (Section 5)
    # ==========================================================================

    def test_08_role_authorization_boundaries(self, api_client, admin_user, proctor_user, student_user_a):
        # Admin blocked from student self-service
        api_client.force_authenticate(user=admin_user)
        res_admin = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Admin Name"})
        assert res_admin.status_code == status.HTTP_403_FORBIDDEN

        # Proctor blocked from student self-service
        api_client.force_authenticate(user=proctor_user)
        res_proctor = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Proctor Name"})
        assert res_proctor.status_code == status.HTTP_403_FORBIDDEN

        # Unauthenticated blocked
        api_client.force_authenticate(user=None)
        res_anon = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Anon Name"})
        assert res_anon.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Inactive student blocked
        student_user_a.is_active = False
        student_user_a.save()
        api_client.force_authenticate(user=student_user_a)
        res_inactive = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Inactive Name"})
        assert res_inactive.status_code == status.HTTP_403_FORBIDDEN

    # ==========================================================================
    # 4. Mass-Assignment / Field-Tampering (Section 6)
    # ==========================================================================

    def test_09_mass_assignment_protection(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        payload = {
            "official_name": "Valid Updated Name",
            "role": Role.ADMIN,
            "is_active": False,
            "is_staff": True,
            "email": "hacker@codeguard.local",
            "roll_number": "HACKED_ROLL",
            "euid": "HACKED_EUID",
            "first_login_required": True,
            "admin_id": "ADMIN-HACKED",
            "section": "HACKED_SECTION",
        }
        res = api_client.patch(self.PROFILE_ENDPOINT, payload)
        assert res.status_code == status.HTTP_200_OK

        student_user_a.refresh_from_db()
        student_user_a.student_profile.refresh_from_db()

        assert student_user_a.student_profile.certificate_name == "Valid Updated Name"
        assert student_user_a.role == Role.STUDENT
        assert student_user_a.is_active is True
        assert student_user_a.is_staff is False
        assert student_user_a.email == "student_a_sec@codeguard.local"
        assert student_user_a.student_profile.roll_number == "ROLL-SEC-A"
        assert student_user_a.student_profile.euid == "CG-ROLL-SEC-A"
        assert student_user_a.student_profile.first_login_required is False

    # ==========================================================================
    # 5. First-Login / Official-Name State Matrix (Section 7)
    # ==========================================================================

    def test_10_state_matrix_cases(self, api_client, admin_user, published_assessment):
        now = timezone.now()

        # CASE A: first_login_required=True, certificate_name=""
        u_a = User.objects.create_user(email="matrix_a@test.local", password="P1", role=Role.STUDENT)
        StudentProfile.objects.create(user=u_a, roll_number="R-A", euid="E-A", certificate_name="", first_login_required=True)
        AssessmentAssignment.objects.create(assessment=published_assessment, student=u_a, assigned_by=admin_user)

        api_client.force_authenticate(user=u_a)
        res_a = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res_a.status_code == status.HTTP_403_FORBIDDEN
        assert "Initial password change is mandatory" in res_a.data.get("error", {}).get("message", "")

        # CASE B: first_login_required=True, certificate_name="Valid Name"
        u_b = User.objects.create_user(email="matrix_b@test.local", password="P1", role=Role.STUDENT)
        StudentProfile.objects.create(user=u_b, roll_number="R-B", euid="E-B", certificate_name="Valid Name", first_login_required=True)
        AssessmentAssignment.objects.create(assessment=published_assessment, student=u_b, assigned_by=admin_user)

        api_client.force_authenticate(user=u_b)
        res_b = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res_b.status_code == status.HTTP_403_FORBIDDEN
        assert "Initial password change is mandatory" in res_b.data.get("error", {}).get("message", "")

        # CASE C: first_login_required=False, certificate_name=""
        u_c = User.objects.create_user(email="matrix_c@test.local", password="P1", role=Role.STUDENT)
        StudentProfile.objects.create(user=u_c, roll_number="R-C", euid="E-C", certificate_name="", first_login_required=False)
        AssessmentAssignment.objects.create(assessment=published_assessment, student=u_c, assigned_by=admin_user)

        api_client.force_authenticate(user=u_c)
        res_c = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res_c.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_c.data.get("error", {}).get("message", "")

        # CASE D: first_login_required=False, certificate_name="Valid Name"
        u_d = User.objects.create_user(email="matrix_d@test.local", password="P1", role=Role.STUDENT)
        StudentProfile.objects.create(user=u_d, roll_number="R-D", euid="E-D", certificate_name="Valid Name", first_login_required=False)
        AssessmentAssignment.objects.create(assessment=published_assessment, student=u_d, assigned_by=admin_user)

        api_client.force_authenticate(user=u_d)
        res_d = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res_d.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

        # CASE E: first_login_required=False, StudentProfile missing
        u_e = User.objects.create_user(email="matrix_e@test.local", password="P1", role=Role.STUDENT)
        AssessmentAssignment.objects.create(assessment=published_assessment, student=u_e, assigned_by=admin_user)

        api_client.force_authenticate(user=u_e)
        res_e = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res_e.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_e.data.get("error", {}).get("message", "")

    # ==========================================================================
    # 6. Direct Exam API Bypass Testing (Section 9)
    # ==========================================================================

    def test_11_all_exam_boundaries_block_student_with_empty_official_name(
        self, api_client, student_user_empty, published_assessment
    ):
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_user_empty,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        api_client.force_authenticate(user=student_user_empty)

        # 1. POST /student/assessments/<id>/start/
        r1 = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert r1.status_code == status.HTTP_403_FORBIDDEN

        # 2. GET /student/attempts/<id>/
        r2 = api_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert r2.status_code == status.HTTP_403_FORBIDDEN

        # 3. POST /student/attempts/<id>/answers/<qid>/
        r3 = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/answers/fake_qid/",
            {"answer_data": {"selected_options": ["opt_1"]}},
            format="json"
        )
        assert r3.status_code == status.HTTP_403_FORBIDDEN

        # 4. POST /student/attempts/<id>/submit/
        r4 = api_client.post(f"/api/v1/student/attempts/{attempt.id}/submit/", format="json")
        assert r4.status_code == status.HTTP_403_FORBIDDEN

        # 5. POST /student/attempts/<id>/terminate/
        r5 = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/terminate/",
            {"reason": "Attempting termination"},
            format="json"
        )
        assert r5.status_code == status.HTTP_403_FORBIDDEN

        # 6. POST /student/attempts/<aid>/questions/<qid>/run/
        r6 = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/questions/fake_qid/run/",
            {"code": "print('test')", "language": "PYTHON"}
        )
        assert r6.status_code == status.HTTP_403_FORBIDDEN

        # 7. POST /student/attempts/<aid>/questions/<qid>/submit/
        r7 = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/questions/fake_qid/submit/",
            {"code": "print('test')", "language": "PYTHON"}
        )
        assert r7.status_code == status.HTTP_403_FORBIDDEN

    # ==========================================================================
    # 7. Certificate Immutability & Security (Section 10)
    # ==========================================================================

    def test_12_issued_certificate_printed_name_is_immutable(
        self, api_client, student_user_a, published_assessment
    ):
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_user_a,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=30),
            submitted_at=now,
            expires_at=now + timedelta(minutes=30),
        )

        # Issue certificate
        cert = CertificateService.generate_or_get_certificate(attempt)
        assert cert is not None
        assert cert.printed_name == "Student A Official"

        # Student now updates their profile certificate_name
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Newly Changed Name"})
        assert res.status_code == status.HTTP_200_OK

        # Verify existing certificate printed_name remains locked
        cert.refresh_from_db()
        assert cert.printed_name == "Student A Official"

    # ==========================================================================
    # 8. Error Response Security (Section 11)
    # ==========================================================================

    def test_13_safe_error_responses_no_internals_leaked(self, api_client, student_user_empty):
        api_client.force_authenticate(user=student_user_empty)

        res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": ""})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

        res_str = str(res.data)
        # Verify no internals leaked
        assert "Traceback" not in res_str
        assert "SELECT" not in res_str
        assert "apps.accounts" not in res_str
        assert "/Users/" not in res_str

    # ==========================================================================
    # 9. Concurrency / Atomicity (Section 12)
    # ==========================================================================

    def test_14_profile_and_user_update_atomic(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        with patch.object(User, "save", side_effect=DatabaseError("Simulated write failure")):
            res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Fail Atomic Name"})
            assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        student_user_a.refresh_from_db()
        student_user_a.student_profile.refresh_from_db()

        assert student_user_a.student_profile.certificate_name == "Student A Official"
        assert student_user_a.display_name == "Student A Sec"

    # ==========================================================================
    # 10. Audit Log Security (Section 13)
    # ==========================================================================

    def test_15_audit_log_does_not_leak_sensitive_information(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        res = api_client.patch(self.PROFILE_ENDPOINT, {"official_name": "Audit Safe Name"})
        assert res.status_code == status.HTTP_200_OK

        audit = AuditLog.objects.filter(
            action="STUDENT_OFFICIAL_NAME_UPDATED",
            target_id=str(student_user_a.student_profile.id)
        ).first()

        assert audit is not None
        assert "password" not in audit.metadata
        assert "token" not in audit.metadata
        assert "session" not in audit.metadata
        assert audit.metadata.get("name_length") == len("Audit Safe Name")
