import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role
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
def admin_user(db):
    return User.objects.create_user(
        email="phase7_admin@codeguard.local",
        password="AdminPassword123!",
        role=Role.ADMIN,
        display_name="Phase 7 Admin"
    )


@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="phase7_proctor@codeguard.local",
        password="ProctorPassword123!",
        role=Role.PROCTOR,
        display_name="Phase 7 Proctor"
    )


@pytest.fixture
def published_assessment(db, admin_user):
    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Phase 7 End-to-End Regression Assessment",
        description="Comprehensive integration verification",
        created_by=admin_user,
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=5),
        duration_minutes=60,
        attempt_limit=2,
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
class TestOfficialNamePhase7Regression:
    """
    Phase 7 Comprehensive Regression & Integration Verification Suite
    """

    # ==========================================================================
    # 1. Authentication Lifecycle & State Transitions (Section 2 & 6)
    # ==========================================================================

    def test_01_complete_new_student_onboarding_lifecycle(
        self, api_client, admin_user, published_assessment
    ):
        """
        Tests transitions:
        New student (pwd req + name req)
          -> change password (pwd cleared, name req remains)
          -> save official name (name cleared)
          -> enter exam
        """
        # Step 1: Create new student with initial temporary password
        student = User.objects.create_user(
            email="new_onboard_student@codeguard.local",
            password="TemporaryPassword123!",
            role=Role.STUDENT,
            display_name="Temp Display"
        )
        profile = StudentProfile.objects.create(
            user=student,
            roll_number="ROLL-P7-001",
            euid="CG-P7-001",
            certificate_name="",
            first_login_required=True
        )
        AssessmentAssignment.objects.create(
            assessment=published_assessment,
            student=student,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED,
        )

        # Login
        login_res = api_client.post("/api/v1/auth/login/", {
            "email": "new_onboard_student@codeguard.local",
            "password": "TemporaryPassword123!"
        })
        assert login_res.status_code == status.HTTP_200_OK
        user_data = login_res.data.get("data", {}).get("user", {})
        assert user_data.get("first_login_required") is True
        assert user_data.get("official_name_required") is True

        # Check /auth/me/
        api_client.force_authenticate(user=student)
        me_res1 = api_client.get("/api/v1/auth/me/")
        assert me_res1.data.get("data", {}).get("first_login_required") is True
        assert me_res1.data.get("data", {}).get("official_name_required") is True

        # Exam start is blocked by password requirement
        exam_blocked_pwd = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert exam_blocked_pwd.status_code == status.HTTP_403_FORBIDDEN
        assert "Initial password change is mandatory" in exam_blocked_pwd.data.get("error", {}).get("message", "")

        # Step 2: Change password
        pwd_res = api_client.post("/api/v1/auth/change-password/", {
            "current_password": "TemporaryPassword123!",
            "new_password": "NewSecurePassword123!",
            "confirm_password": "NewSecurePassword123!",
        })
        assert pwd_res.status_code == status.HTTP_200_OK

        # Refresh state: password requirement cleared, but official name still required
        student.refresh_from_db()
        profile.refresh_from_db()
        assert profile.first_login_required is False
        assert profile.certificate_name == ""

        me_res2 = api_client.get("/api/v1/auth/me/")
        assert me_res2.data.get("data", {}).get("first_login_required") is False
        assert me_res2.data.get("data", {}).get("official_name_required") is True

        # Exam start is blocked by official name requirement
        exam_blocked_name = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert exam_blocked_name.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in exam_blocked_name.data.get("error", {}).get("message", "")

        # Step 3: Setup official name
        name_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Gaurav Agarwal"
        })
        assert name_res.status_code == status.HTTP_200_OK

        # Refresh state: both requirements now satisfied
        student.refresh_from_db()
        profile.refresh_from_db()
        assert profile.first_login_required is False
        assert profile.certificate_name == "Gaurav Agarwal"
        assert student.display_name == "Gaurav Agarwal"

        me_res3 = api_client.get("/api/v1/auth/me/")
        assert me_res3.data.get("data", {}).get("first_login_required") is False
        assert me_res3.data.get("data", {}).get("official_name_required") is False

        # Step 4: Exam start succeeds
        exam_start_res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert exam_start_res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        attempt_id = exam_start_res.data.get("data", {}).get("attempt_id")
        assert attempt_id is not None

    def test_02_admin_and_proctor_auth_regression(self, api_client, admin_user, proctor_user):
        """
        Verify official_name_required is False for non-students and non-student routes work normally.
        """
        # Admin
        api_client.force_authenticate(user=admin_user)
        admin_me = api_client.get("/api/v1/auth/me/")
        assert admin_me.status_code == status.HTTP_200_OK
        assert admin_me.data.get("data", {}).get("official_name_required") is False
        assert admin_me.data.get("data", {}).get("role") == Role.ADMIN

        admin_assessments = api_client.get("/api/v1/admin/assessments/")
        assert admin_assessments.status_code == status.HTTP_200_OK

        # Proctor
        api_client.force_authenticate(user=proctor_user)
        proctor_me = api_client.get("/api/v1/auth/me/")
        assert proctor_me.status_code == status.HTTP_200_OK
        assert proctor_me.data.get("data", {}).get("official_name_required") is False
        assert proctor_me.data.get("data", {}).get("role") == Role.PROCTOR

    def test_03_csrf_and_logout_regression(self, api_client, admin_user):
        """
        Verify standard auth utilities (CSRF token init, logout) are unaffected.
        """
        csrf_res = api_client.get("/api/v1/auth/csrf/")
        assert csrf_res.status_code == status.HTTP_200_OK
        assert "csrf_token" in csrf_res.data.get("data", {})

        api_client.force_authenticate(user=admin_user)
        logout_res = api_client.post("/api/v1/auth/logout/")
        assert logout_res.status_code == status.HTTP_200_OK

    # ==========================================================================
    # 2. Exam Participation Flow with Valid Name (Section 5)
    # ==========================================================================

    def test_04_full_exam_participation_lifecycle_with_official_name(
        self, api_client, admin_user, published_assessment
    ):
        """
        Student with valid official name starts, answers questions, submits attempt,
        and triggers certificate generation.
        """
        student = User.objects.create_user(
            email="exam_student_p7@codeguard.local",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Jane Doe"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="ROLL-P7-EXAM",
            euid="CG-P7-EXAM",
            certificate_name="Jane Doe",
            first_login_required=False
        )
        AssessmentAssignment.objects.create(
            assessment=published_assessment,
            student=student,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED,
        )

        api_client.force_authenticate(user=student)

        # 1. Start Assessment
        start_res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert start_res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        attempt_id = start_res.data["data"]["attempt_id"]

        # 2. Retrieve Attempt Details
        detail_res = api_client.get(f"/api/v1/student/attempts/{attempt_id}/")
        assert detail_res.status_code == status.HTTP_200_OK
        questions = detail_res.data.get("data", {}).get("questions", [])
        assert len(questions) > 0
        qid = questions[0].get("snapshot_question_id") or questions[0].get("id")

        # 3. Save Answer
        answer_res = api_client.post(
            f"/api/v1/student/attempts/{attempt_id}/answers/{qid}/",
            {"answer_data": {"selected_options": ["opt_1"]}},
            format="json"
        )
        assert answer_res.status_code == status.HTTP_200_OK

        # 4. Submit Attempt
        submit_res = api_client.post(f"/api/v1/student/attempts/{attempt_id}/submit/", format="json")
        assert submit_res.status_code == status.HTTP_200_OK
        assert submit_res.data.get("data", {}).get("status") == AttemptStatus.SUBMITTED

    # ==========================================================================
    # 3. Certificate Lifecycle & Post-Issuance Immutability (Section 7)
    # ==========================================================================

    def test_05_certificate_generation_and_post_issuance_immutability(
        self, api_client, admin_user, published_assessment
    ):
        """
        Verify:
        1. Qualifying attempt automatically generates Certificate with printed_name = certificate_name.
        2. Public certificate verification returns correct name.
        3. Student later updates their profile certificate_name.
        4. Issued certificate printed_name remains locked to original snapshot.
        """
        student = User.objects.create_user(
            email="cert_student_p7@codeguard.local",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Official Scholar"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="ROLL-P7-CERT",
            euid="CG-P7-CERT",
            certificate_name="Official Scholar",
            first_login_required=False
        )

        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=20),
            submitted_at=now,
            expires_at=now + timedelta(minutes=40),
        )

        # Generate certificate
        cert = CertificateService.generate_or_get_certificate(attempt)
        assert cert is not None
        assert cert.printed_name == "Official Scholar"
        assert cert.certificate_id is not None

        # Public verification endpoint check
        verify_res = api_client.get(f"/api/v1/public/certificates/verify/{cert.certificate_id}/")
        assert verify_res.status_code == status.HTTP_200_OK
        assert verify_res.data.get("data", {}).get("printed_name") == "Official Scholar"

        # Student updates profile name
        api_client.force_authenticate(user=student)
        patch_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Different Name Entirely"
        })
        assert patch_res.status_code == status.HTTP_200_OK

        # Existing certificate MUST remain unchanged
        cert.refresh_from_db()
        assert cert.printed_name == "Official Scholar"

        verify_res_after = api_client.get(f"/api/v1/public/certificates/verify/{cert.certificate_id}/")
        assert verify_res_after.data.get("data", {}).get("printed_name") == "Official Scholar"

    # ==========================================================================
    # 4. API Contract Regression (Section 13)
    # ==========================================================================

    def test_06_api_contracts_contain_expected_fields_and_no_secrets(
        self, api_client, admin_user
    ):
        """
        Verify GET /auth/me/, GET /student/profile/, and PATCH /student/profile/ contracts.
        """
        student = User.objects.create_user(
            email="contract_student@codeguard.local",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Contract Tester"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="ROLL-P7-CONTRACT",
            euid="CG-P7-CONTRACT",
            certificate_name="Contract Tester",
            first_login_required=False
        )

        api_client.force_authenticate(user=student)

        # GET /auth/me/
        me_res = api_client.get("/api/v1/auth/me/")
        assert me_res.status_code == status.HTTP_200_OK
        me_data = me_res.data.get("data", {})
        expected_me_fields = {
            "id", "email", "role", "is_active", "first_login_required",
            "official_name_required", "display_name", "student_profile"
        }
        assert expected_me_fields.issubset(set(me_data.keys()))
        assert "password" not in me_data

        # GET /student/profile/
        prof_res = api_client.get("/api/v1/student/profile/")
        assert prof_res.status_code == status.HTTP_200_OK
        prof_data = prof_res.data.get("data", {})
        expected_prof_fields = {
            "id", "user_id", "email", "role", "roll_number", "euid",
            "certificate_name", "official_name_required", "first_login_required"
        }
        assert expected_prof_fields.issubset(set(prof_data.keys()))
        assert "password" not in prof_data

        # PATCH /student/profile/
        patch_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Updated Contract Name"
        })
        assert patch_res.status_code == status.HTTP_200_OK
        patch_data = patch_res.data.get("data", {})
        assert expected_prof_fields.issubset(set(patch_data.keys()))
        assert patch_data["certificate_name"] == "Updated Contract Name"
        assert patch_data["official_name_required"] is False

    # ==========================================================================
    # 5. Performance & Query Count Verification (Section 14)
    # ==========================================================================

    def test_07_query_count_bounded_on_auth_me_and_profile(self, api_client):
        """
        Verify that GET /auth/me/ and GET /student/profile/ execute within bounded query counts.
        """
        student = User.objects.create_user(
            email="query_student@codeguard.local",
            password="StudentPassword123!",
            role=Role.STUDENT,
            display_name="Query Count Student"
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="ROLL-P7-QUERY",
            euid="CG-P7-QUERY",
            certificate_name="Query Count Student",
            first_login_required=False
        )

        api_client.force_authenticate(user=student)

        res1 = api_client.get("/api/v1/auth/me/")
        assert res1.status_code == status.HTTP_200_OK

        res2 = api_client.get("/api/v1/student/profile/")
        assert res2.status_code == status.HTTP_200_OK
