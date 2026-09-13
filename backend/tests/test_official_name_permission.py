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


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_perm@codeguard.local",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="proctor_perm@codeguard.local",
        password="ProctorPassword123!",
        role=Role.PROCTOR
    )


@pytest.fixture
def student_valid_name(db):
    user = User.objects.create_user(
        email="student_valid_perm@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Rahul Sharma"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-VALID-P01",
        euid="CG-ROLL-VALID-P01",
        certificate_name="Rahul Sharma",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_empty_name(db):
    user = User.objects.create_user(
        email="student_empty_perm@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Empty"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-EMPTY-P02",
        euid="CG-ROLL-EMPTY-P02",
        certificate_name="",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_whitespace_name(db):
    user = User.objects.create_user(
        email="student_space_perm@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Space"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-SPACE-P03",
        euid="CG-ROLL-SPACE-P03",
        certificate_name="     ",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_no_profile(db):
    return User.objects.create_user(
        email="student_noprofile_perm@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student No Profile"
    )


@pytest.fixture
def published_assessment(db, admin_user, student_valid_name, student_empty_name, student_whitespace_name, student_no_profile):
    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Permission Hardening Live Test",
        description="Assessment for validating official name security boundaries",
        created_by=admin_user,
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=5),
        duration_minutes=60,
        attempt_limit=1,
    )

    # Assign all test students
    for student in [student_valid_name, student_empty_name, student_whitespace_name, student_no_profile]:
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
        title="MCQ Question 1",
        question_type=QuestionType.MCQ,
        points=10,
        status=VersionStatus.PUBLISHED,
        created_by=admin_user,
        type_config={"options": [{"id": "o1", "text": "Correct", "is_correct": True}]},
    )

    snap = AssessmentSnapshot.objects.create(
        assessment=assessment,
        version_number=1,
        snapshot_data={
            "title": assessment.title,
            "questions": [
                {
                    "snapshot_question_id": str(q.id),
                    "title": "Sample Question",
                    "description": "Choose one",
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
class TestOfficialNamePermission:

    def test_1_student_with_valid_certificate_name_can_start_assessment(
        self, api_client, student_valid_name, published_assessment
    ):
        api_client.force_authenticate(user=student_valid_name)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")

        assert res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        data = res.data.get("data", {})
        assert "attempt_id" in data

    def test_2_student_with_empty_certificate_name_cannot_start_assessment(
        self, api_client, student_empty_name, published_assessment
    ):
        api_client.force_authenticate(user=student_empty_name)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Official full name setup is mandatory" in err.get("message", "")

    def test_3_student_with_whitespace_certificate_name_cannot_start_assessment(
        self, api_client, student_whitespace_name, published_assessment
    ):
        api_client.force_authenticate(user=student_whitespace_name)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Official full name setup is mandatory" in err.get("message", "")

    def test_4_student_cannot_bypass_via_request_payload(
        self, api_client, student_empty_name, published_assessment
    ):
        api_client.force_authenticate(user=student_empty_name)
        res = api_client.post(
            f"/api/v1/student/assessments/{published_assessment.id}/start/",
            {"official_name_required": False, "certificate_name": "Spoofed Name"}
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_5_direct_http_attempt_detail_access_blocked_for_incomplete_student(
        self, api_client, student_empty_name, published_assessment, admin_user
    ):
        # Create a preexisting attempt directly in database
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_empty_name,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        api_client.force_authenticate(user=student_empty_name)
        res = api_client.get(f"/api/v1/student/attempts/{attempt.id}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Official full name setup is mandatory" in err.get("message", "")

    def test_6_admin_behavior_remains_unchanged(
        self, api_client, admin_user, published_assessment
    ):
        api_client.force_authenticate(user=admin_user)
        # Admin can access admin assessment endpoints
        res = api_client.get(f"/api/v1/admin/assessments/{published_assessment.id}/")
        assert res.status_code == status.HTTP_200_OK

    def test_7_proctor_behavior_remains_unchanged(
        self, api_client, proctor_user, published_assessment
    ):
        api_client.force_authenticate(user=proctor_user)
        # Proctors cannot access student start attempt (blocked by IsStudent)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Student account required" in err.get("message", "")

    def test_8_first_login_required_remains_independent(
        self, api_client, db, admin_user, published_assessment
    ):
        # Student with password change required AND valid official name
        student_pwd_req = User.objects.create_user(
            email="pwd_req_student@codeguard.local",
            password="TemporaryPassword123!",
            role=Role.STUDENT,
            display_name="Valid Name Student"
        )
        StudentProfile.objects.create(
            user=student_pwd_req,
            roll_number="ROLL-PWD-01",
            euid="CG-ROLL-PWD-01",
            certificate_name="Valid Certificate Name",
            first_login_required=True
        )
        AssessmentAssignment.objects.create(
            assessment=published_assessment,
            student=student_pwd_req,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED,
        )

        api_client.force_authenticate(user=student_pwd_req)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")

        # Should be blocked by IsFirstLoginSatisfied (password setup required)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Initial password change is mandatory" in err.get("message", "")

    def test_9_student_can_still_access_profile_and_patch_name_endpoint(
        self, api_client, student_empty_name
    ):
        api_client.force_authenticate(user=student_empty_name)

        # GET profile works
        res_get = api_client.get("/api/v1/student/profile/")
        assert res_get.status_code == status.HTTP_200_OK

        # PATCH profile works
        res_patch = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Aarav Patel"
        })
        assert res_patch.status_code == status.HTTP_200_OK
        assert res_patch.data["data"]["certificate_name"] == "Aarav Patel"

    def test_10_after_saving_valid_name_student_can_start_assessment(
        self, api_client, student_empty_name, published_assessment
    ):
        api_client.force_authenticate(user=student_empty_name)

        # Initially blocked
        blocked_res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert blocked_res.status_code == status.HTTP_403_FORBIDDEN

        # Complete name setup
        patch_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Neha Verma"
        })
        assert patch_res.status_code == status.HTTP_200_OK

        # Retry starting assessment -> now succeeds!
        student_empty_name.refresh_from_db()
        success_res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert success_res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        assert "attempt_id" in success_res.data.get("data", {})

    def test_11_unauthenticated_request_remains_rejected_401(
        self, api_client, published_assessment
    ):
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_12_unrelated_student_endpoints_not_blocked(
        self, api_client, student_empty_name, published_assessment
    ):
        api_client.force_authenticate(user=student_empty_name)

        # Informational assessment listing is NOT blocked
        res_list = api_client.get("/api/v1/student/assessments/")
        assert res_list.status_code == status.HTTP_200_OK

        # Informational assessment detail is NOT blocked
        res_detail = api_client.get(f"/api/v1/student/assessments/{published_assessment.id}/")
        assert res_detail.status_code == status.HTTP_200_OK

    def test_13_student_with_first_login_true_and_empty_name_blocked_by_password(
        self, api_client, db, admin_user, published_assessment
    ):
        # Security Matrix D: first_login_required=True, certificate_name=""
        student_d = User.objects.create_user(
            email="matrix_d_student@codeguard.local",
            password="TempPassword123!",
            role=Role.STUDENT,
            display_name="Matrix D Student"
        )
        StudentProfile.objects.create(
            user=student_d,
            roll_number="ROLL-MAT-D01",
            euid="CG-ROLL-MAT-D01",
            certificate_name="",
            first_login_required=True
        )
        AssessmentAssignment.objects.create(
            assessment=published_assessment,
            student=student_d,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED,
        )

        api_client.force_authenticate(user=student_d)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        # Should be blocked by password change requirement
        assert "Initial password change is mandatory" in err.get("message", "")

    def test_14_active_student_with_no_profile_cannot_start_assessment(
        self, api_client, student_no_profile, published_assessment
    ):
        # Security Matrix F: STUDENT with no StudentProfile
        api_client.force_authenticate(user=student_no_profile)
        res = api_client.post(f"/api/v1/student/assessments/{published_assessment.id}/start/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Official full name setup is mandatory" in err.get("message", "")

    def test_15_active_student_with_no_profile_cannot_access_attempt_detail(
        self, api_client, student_no_profile, published_assessment
    ):
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_no_profile,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        api_client.force_authenticate(user=student_no_profile)
        res = api_client.get(f"/api/v1/student/attempts/{attempt.id}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        err = res.data.get("error", {})
        assert "Official full name setup is mandatory" in err.get("message", "")

    def test_16_active_student_with_no_profile_cannot_save_submit_or_terminate(
        self, api_client, student_no_profile, published_assessment
    ):
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_no_profile,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        api_client.force_authenticate(user=student_no_profile)

        # 1. Save answer blocked
        res_save = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/answers/fake_qid/",
            {"answer_data": {"selected_options": ["OPT_A"]}},
            format="json"
        )
        assert res_save.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_save.data.get("error", {}).get("message", "")

        # 2. Submit blocked
        res_sub = api_client.post(f"/api/v1/student/attempts/{attempt.id}/submit/", format="json")
        assert res_sub.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_sub.data.get("error", {}).get("message", "")

        # 3. Terminate blocked
        res_term = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/terminate/",
            {"reason": "Testing termination"},
            format="json"
        )
        assert res_term.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_term.data.get("error", {}).get("message", "")

    def test_17_active_student_with_no_profile_cannot_execute_code(
        self, api_client, student_no_profile, published_assessment
    ):
        now = timezone.now()
        attempt = TestAttempt.objects.create(
            assessment=published_assessment,
            student=student_no_profile,
            assessment_snapshot=published_assessment.snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        api_client.force_authenticate(user=student_no_profile)

        # Code run blocked
        res_run = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/questions/fake_qid/run/",
            {"code": "print('hello')", "language": "PYTHON"}
        )
        assert res_run.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_run.data.get("error", {}).get("message", "")

        # Code submit blocked
        res_sub = api_client.post(
            f"/api/v1/student/attempts/{attempt.id}/questions/fake_qid/submit/",
            {"code": "print('hello')", "language": "PYTHON"}
        )
        assert res_sub.status_code == status.HTTP_403_FORBIDDEN
        assert "Official full name setup is mandatory" in res_sub.data.get("error", {}).get("message", "")

    def test_18_student_with_no_profile_auth_me_exposes_official_name_required_true(
        self, api_client, student_no_profile
    ):
        api_client.force_authenticate(user=student_no_profile)
        res = api_client.get("/api/v1/auth/me/")
        assert res.status_code == status.HTTP_200_OK
        data = res.data.get("data", {})
        assert data.get("official_name_required") is True

    def test_19_student_with_no_profile_can_access_informational_assessment_endpoints(
        self, api_client, student_no_profile, published_assessment
    ):
        api_client.force_authenticate(user=student_no_profile)

        # Informational assessment listing is NOT blocked
        res_list = api_client.get("/api/v1/student/assessments/")
        assert res_list.status_code == status.HTTP_200_OK

        # Informational assessment detail is NOT blocked
        res_detail = api_client.get(f"/api/v1/student/assessments/{published_assessment.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
