import pytest
from unittest.mock import patch
from django.db import DatabaseError
from rest_framework import status

from apps.accounts.models import User, StudentProfile, Role, AuditLog


@pytest.fixture
def student_user_a(db):
    user = User.objects.create_user(
        email="student_a@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student A Initial"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-A-001",
        euid="CG-ROLL-A-001",
        certificate_name="Original Name A",
        first_login_required=False
    )
    return user


@pytest.fixture
def student_user_b(db):
    user = User.objects.create_user(
        email="student_b@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student B Initial"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-B-002",
        euid="CG-ROLL-B-002",
        certificate_name="Untouched Name B",
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
class TestStudentOfficialNameAPI:

    ENDPOINT = "/api/v1/student/profile/"

    def test_1_authenticated_student_can_save_official_name(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "Rahul Sharma"})

        assert res.status_code == status.HTTP_200_OK
        data = res.data.get("data", {})
        assert data.get("certificate_name") == "Rahul Sharma"
        assert data.get("display_name") == "Rahul Sharma"

    def test_2_leading_trailing_whitespace_normalized(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "   Priya Singh   "})

        assert res.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Priya Singh"

    def test_3_empty_name_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": ""})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Original Name A"

    def test_4_whitespace_only_name_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "    "})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Original Name A"

    def test_5_name_shorter_than_2_chars_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "A"})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Original Name A"

    def test_6_name_longer_than_255_chars_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "A" * 256})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Original Name A"

    def test_7_control_characters_rejected(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res_null = api_client.patch(self.ENDPOINT, {"official_name": "Rahul\x00Sharma"})
        assert res_null.status_code == status.HTTP_400_BAD_REQUEST

        res_nl = api_client.patch(self.ENDPOINT, {"official_name": "Rahul\nSharma"})
        assert res_nl.status_code == status.HTTP_400_BAD_REQUEST

        res_tab = api_client.patch(self.ENDPOINT, {"official_name": "Rahul\tSharma"})
        assert res_tab.status_code == status.HTTP_400_BAD_REQUEST

        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Original Name A"

    def test_8_legitimate_unicode_names_accepted(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        res1 = api_client.patch(self.ENDPOINT, {"official_name": "José García"})
        assert res1.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "José García"

        res2 = api_client.patch(self.ENDPOINT, {"official_name": "李明"})
        assert res2.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "李明"

        res3 = api_client.patch(self.ENDPOINT, {"official_name": "Ananya R."})
        assert res3.status_code == status.HTTP_200_OK
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Ananya R."

    def test_9_display_name_synchronized(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "Vikul Tomar"})

        assert res.status_code == status.HTTP_200_OK
        student_user_a.refresh_from_db()
        assert student_user_a.display_name == "Vikul Tomar"

    def test_10_certificate_name_persisted(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        api_client.patch(self.ENDPOINT, {"certificate_name": "Gaurav Agarwal"})

        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Gaurav Agarwal"

    def test_11_unauthenticated_request_rejected(self, api_client):
        res = api_client.patch(self.ENDPOINT, {"official_name": "Hacker"})
        assert res.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_12_admin_cannot_use_student_self_service_endpoint(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.patch(self.ENDPOINT, {"official_name": "Admin Name"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_13_proctor_cannot_use_student_self_service_endpoint(self, api_client, proctor_user):
        api_client.force_authenticate(user=proctor_user)
        res = api_client.patch(self.ENDPOINT, {"official_name": "Proctor Name"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_14_student_cannot_modify_another_student(self, api_client, student_user_a, student_user_b):
        api_client.force_authenticate(user=student_user_a)
        # Attempt to supply student_user_b's IDs in payload
        res = api_client.patch(self.ENDPOINT, {
            "id": str(student_user_b.student_profile.id),
            "user_id": str(student_user_b.id),
            "official_name": "Student A Renamed"
        })
        assert res.status_code == status.HTTP_200_OK

        # Student A updated
        student_user_a.student_profile.refresh_from_db()
        assert student_user_a.student_profile.certificate_name == "Student A Renamed"

        # Student B untouched
        student_user_b.student_profile.refresh_from_db()
        assert student_user_b.student_profile.certificate_name == "Untouched Name B"

    def test_15_attempting_to_submit_unrelated_protected_fields_ignored(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {
            "official_name": "Protected Field Test",
            "roll_number": "HACKED_ROLL",
            "euid": "HACKED_EUID",
            "role": "ADMIN",
            "is_active": False,
            "first_login_required": True,
            "email": "hacked@example.com"
        })
        assert res.status_code == status.HTTP_200_OK

        student_user_a.refresh_from_db()
        student_user_a.student_profile.refresh_from_db()

        assert student_user_a.student_profile.certificate_name == "Protected Field Test"
        assert student_user_a.student_profile.roll_number == "ROLL-A-001"
        assert student_user_a.student_profile.euid == "CG-ROLL-A-001"
        assert student_user_a.role == Role.STUDENT
        assert student_user_a.is_active is True
        assert student_user_a.student_profile.first_login_required is False
        assert student_user_a.email == "student_a@codeguard.local"

    def test_16_database_operation_is_atomic(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)

        # Mock user.save to simulate failure after profile.save inside atomic block
        with patch.object(User, "save", side_effect=DatabaseError("Simulated write failure")):
            res = api_client.patch(self.ENDPOINT, {"official_name": "Failed Atomic Name"})
            assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        student_user_a.refresh_from_db()
        student_user_a.student_profile.refresh_from_db()
        # Because of transaction.atomic(), both remain at initial values
        assert student_user_a.student_profile.certificate_name == "Original Name A"
        assert student_user_a.display_name == "Student A Initial"

    def test_17_existing_certificate_name_remains_unchanged(self, student_user_b):
        # Student B did not call the endpoint; verify untouched
        student_user_b.student_profile.refresh_from_db()
        assert student_user_b.student_profile.certificate_name == "Untouched Name B"

    def test_18_audit_log_created_for_name_update(self, api_client, student_user_a):
        api_client.force_authenticate(user=student_user_a)
        res = api_client.patch(self.ENDPOINT, {"official_name": "Audit Verified Name"})
        assert res.status_code == status.HTTP_200_OK

        audit = AuditLog.objects.filter(
            action="STUDENT_OFFICIAL_NAME_UPDATED",
            target_id=str(student_user_a.student_profile.id)
        ).first()

        assert audit is not None
        assert audit.actor == student_user_a
        assert audit.metadata.get("roll_number") == "ROLL-A-001"
        assert audit.metadata.get("euid") == "CG-ROLL-A-001"
        assert audit.metadata.get("name_length") == len("Audit Verified Name")
