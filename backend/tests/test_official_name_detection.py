import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_empty_name(db):
    user = User.objects.create_user(
        email="student_empty@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Empty"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-EMPTY-001",
        euid="CG-ROLL-EMPTY-001",
        certificate_name="",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_whitespace_name(db):
    user = User.objects.create_user(
        email="student_space@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Space"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-SPACE-002",
        euid="CG-ROLL-SPACE-002",
        certificate_name="     ",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_valid_name(db):
    user = User.objects.create_user(
        email="student_valid@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Rahul Sharma"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-VALID-003",
        euid="CG-ROLL-VALID-003",
        certificate_name="Rahul Sharma",
        first_login_required=False
    )
    return user


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_user@codeguard.local",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="proctor_user@codeguard.local",
        password="ProctorPassword123!",
        role=Role.PROCTOR
    )


@pytest.mark.django_db
class TestOfficialNameDetection:

    def test_1_student_with_empty_certificate_name_requires_setup(self, api_client, student_empty_name):
        api_client.force_authenticate(user=student_empty_name)
        res = api_client.get("/api/v1/auth/me/")

        assert res.status_code == status.HTTP_200_OK
        user_data = res.data.get("data", {})
        assert user_data.get("role") == Role.STUDENT
        assert user_data.get("official_name_required") is True
        assert user_data.get("student_profile", {}).get("official_name_required") is True

    def test_2_student_with_whitespace_only_certificate_name_requires_setup(self, api_client, student_whitespace_name):
        api_client.force_authenticate(user=student_whitespace_name)
        res = api_client.get("/api/v1/auth/me/")

        assert res.status_code == status.HTTP_200_OK
        user_data = res.data.get("data", {})
        assert user_data.get("official_name_required") is True
        assert user_data.get("student_profile", {}).get("official_name_required") is True

    def test_3_student_with_valid_certificate_name_does_not_require_setup(self, api_client, student_valid_name):
        api_client.force_authenticate(user=student_valid_name)
        res = api_client.get("/api/v1/auth/me/")

        assert res.status_code == status.HTTP_200_OK
        user_data = res.data.get("data", {})
        assert user_data.get("official_name_required") is False
        assert user_data.get("student_profile", {}).get("official_name_required") is False

    def test_4_admin_never_requires_official_name_setup(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/auth/me/")

        assert res.status_code == status.HTTP_200_OK
        user_data = res.data.get("data", {})
        assert user_data.get("role") == Role.ADMIN
        assert user_data.get("official_name_required") is False
        assert user_data.get("student_profile") is None

    def test_5_proctor_never_requires_official_name_setup(self, api_client, proctor_user):
        api_client.force_authenticate(user=proctor_user)
        res = api_client.get("/api/v1/auth/me/")

        assert res.status_code == status.HTTP_200_OK
        user_data = res.data.get("data", {})
        assert user_data.get("role") == Role.PROCTOR
        assert user_data.get("official_name_required") is False
        assert user_data.get("student_profile") is None

    def test_6_login_response_exposes_correct_state(self, api_client, student_empty_name, student_valid_name):
        # Student needing name setup
        res_empty = api_client.post("/api/v1/auth/login/", {
            "email": "student_empty@codeguard.local",
            "password": "StudentPassword123!"
        })
        assert res_empty.status_code == status.HTTP_200_OK
        user_empty = res_empty.data["data"]["user"]
        assert user_empty["official_name_required"] is True
        assert user_empty["student_profile"]["official_name_required"] is True

        # Student with setup complete
        res_valid = api_client.post("/api/v1/auth/login/", {
            "email": "student_valid@codeguard.local",
            "password": "StudentPassword123!"
        })
        assert res_valid.status_code == status.HTTP_200_OK
        user_valid = res_valid.data["data"]["user"]
        assert user_valid["official_name_required"] is False
        assert user_valid["student_profile"]["official_name_required"] is False

    def test_7_auth_me_exposes_correct_state(self, api_client, student_empty_name, student_valid_name):
        api_client.force_authenticate(user=student_empty_name)
        me_empty = api_client.get("/api/v1/auth/me/")
        assert me_empty.data["data"]["official_name_required"] is True

        api_client.force_authenticate(user=student_valid_name)
        me_valid = api_client.get("/api/v1/auth/me/")
        assert me_valid.data["data"]["official_name_required"] is False

    def test_8_login_and_auth_me_return_consistent_state(self, api_client, student_empty_name):
        login_res = api_client.post("/api/v1/auth/login/", {
            "email": "student_empty@codeguard.local",
            "password": "StudentPassword123!"
        })
        assert login_res.status_code == status.HTTP_200_OK
        login_state = login_res.data["data"]["user"]["official_name_required"]

        # Follow up with /auth/me/ using the active session
        me_res = api_client.get("/api/v1/auth/me/")
        assert me_res.status_code == status.HTTP_200_OK
        me_state = me_res.data["data"]["official_name_required"]

        assert login_state == me_state is True

    def test_9_after_official_name_is_saved_state_becomes_false(self, api_client, student_empty_name):
        api_client.force_authenticate(user=student_empty_name)

        # Before update: official_name_required == True
        me_before = api_client.get("/api/v1/auth/me/")
        assert me_before.data["data"]["official_name_required"] is True

        # Perform name update
        patch_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Priya Singh"
        })
        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.data["data"]["official_name_required"] is False
        assert patch_res.data["data"]["certificate_name"] == "Priya Singh"

        # Subsequent /auth/me/ check: official_name_required == False
        # Refresh user from database to ensure fresh state
        student_empty_name.refresh_from_db()
        me_after = api_client.get("/api/v1/auth/me/")
        assert me_after.data["data"]["official_name_required"] is False
        assert me_after.data["data"]["display_name"] == "Priya Singh"
        assert me_after.data["data"]["student_profile"]["certificate_name"] == "Priya Singh"
        assert me_after.data["data"]["student_profile"]["official_name_required"] is False

    def test_10_client_cannot_submit_official_name_required_false_to_bypass(self, api_client, student_empty_name):
        api_client.force_authenticate(user=student_empty_name)

        # Attempt to bypass by sending official_name_required=False without a valid name
        res = api_client.patch("/api/v1/student/profile/", {
            "official_name_required": False
        })
        # Serializer requires official_name or certificate_name
        assert res.status_code == status.HTTP_400_BAD_REQUEST

        # Verify state is still required on /auth/me/
        student_empty_name.refresh_from_db()
        me_res = api_client.get("/api/v1/auth/me/")
        assert me_res.data["data"]["official_name_required"] is True

    def test_11_first_login_required_remains_independent(self, api_client, db):
        # Verify first_login_required is not altered by name state
        user = User.objects.create_user(
            email="independent_test@codeguard.local",
            password="Password123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="ROLL-INDEP-001",
            euid="CG-ROLL-INDEP-001",
            certificate_name="",
            first_login_required=True
        )

        api_client.force_authenticate(user=user)
        me_res = api_client.get("/api/v1/auth/me/")
        data = me_res.data["data"]
        assert data["first_login_required"] is True
        assert data["official_name_required"] is True

        # Now save name
        patch_res = api_client.patch("/api/v1/student/profile/", {
            "official_name": "Test Independence"
        })
        assert patch_res.status_code == status.HTTP_200_OK

        # official_name_required becomes False, but first_login_required stays True!
        user.refresh_from_db()
        me_after = api_client.get("/api/v1/auth/me/")
        after_data = me_after.data["data"]
        assert after_data["official_name_required"] is False
        assert after_data["first_login_required"] is True

    def test_12_student_first_login_false_certificate_empty(self, api_client, db):
        user = User.objects.create_user(
            email="case_12@codeguard.local",
            password="Password123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="ROLL-12-001",
            euid="CG-ROLL-12-001",
            certificate_name="",
            first_login_required=False
        )
        api_client.force_authenticate(user=user)
        res = api_client.get("/api/v1/auth/me/")
        data = res.data["data"]
        assert data["first_login_required"] is False
        assert data["official_name_required"] is True

    def test_13_student_first_login_true_certificate_empty(self, api_client, db):
        user = User.objects.create_user(
            email="case_13@codeguard.local",
            password="Password123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="ROLL-13-001",
            euid="CG-ROLL-13-001",
            certificate_name="",
            first_login_required=True
        )
        api_client.force_authenticate(user=user)
        res = api_client.get("/api/v1/auth/me/")
        data = res.data["data"]
        assert data["first_login_required"] is True
        assert data["official_name_required"] is True

    def test_14_student_first_login_true_certificate_valid(self, api_client, db):
        user = User.objects.create_user(
            email="case_14@codeguard.local",
            password="Password123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="ROLL-14-001",
            euid="CG-ROLL-14-001",
            certificate_name="Valid Name",
            first_login_required=True
        )
        api_client.force_authenticate(user=user)
        res = api_client.get("/api/v1/auth/me/")
        data = res.data["data"]
        assert data["first_login_required"] is True
        assert data["official_name_required"] is False

    def test_15_student_first_login_false_certificate_valid(self, api_client, db):
        user = User.objects.create_user(
            email="case_15@codeguard.local",
            password="Password123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="ROLL-15-001",
            euid="CG-ROLL-15-001",
            certificate_name="Valid Name",
            first_login_required=False
        )
        api_client.force_authenticate(user=user)
        res = api_client.get("/api/v1/auth/me/")
        data = res.data["data"]
        assert data["first_login_required"] is False
        assert data["official_name_required"] is False
