import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.accounts.services import AccountSecurityService
from apps.assessments.models import Assessment, AssessmentAssignment, AssessmentStatus


@pytest.fixture
def primary_admin_user(db):
    user = User.objects.filter(role=Role.ADMIN, primary_admin_marker='PRIMARY').first()
    if not user:
        user = User.objects.create_user(
            email='primary.admin.test@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True,
            admin_id='EUAD-GAURAV-099',
            primary_admin_marker='PRIMARY',
            display_name='Primary Admin'
        )
    return user


@pytest.fixture
def primary_client(primary_admin_user):
    client = APIClient()
    client.force_authenticate(user=primary_admin_user)
    return client


@pytest.fixture
def secondary_admin_user(db):
    return User.objects.create_user(
        email='secondary.admin.auth.test@codeguard.local',
        password='Password123!',
        role=Role.ADMIN,
        is_staff=True,
        display_name='Secondary Admin',
        is_active=True
    )


@pytest.fixture
def secondary_client(secondary_admin_user):
    client = APIClient()
    client.force_authenticate(user=secondary_admin_user)
    return client


@pytest.mark.django_db
class TestPrimaryAdminDeleteAuthorization:

    def test_primary_admin_can_delete_normal_admin(self, primary_client, primary_admin_user):
        """1. Primary admin can delete a normal secondary administrator."""
        target = User.objects.create_user(
            email='target.admin1@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Target Admin 1',
            is_active=True
        )
        url = f"/api/v1/admin/administrators/{target.id}/"
        response = primary_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.data.get("message", "").lower()
        assert not User.objects.filter(id=target.id).exists()

    def test_deleted_admin_remains_deleted_after_api_reload(self, primary_client, primary_admin_user):
        """2. Deleted admin remains deleted when loading the administrator directory."""
        target = User.objects.create_user(
            email='target.admin2@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Target Admin 2',
            is_active=True
        )
        url = f"/api/v1/admin/administrators/{target.id}/"
        resp_del = primary_client.delete(url)
        assert resp_del.status_code == status.HTTP_200_OK

        # Fetch administrators list (equivalent to page refresh)
        resp_list = primary_client.get("/api/v1/admin/administrators/")
        assert resp_list.status_code == status.HTTP_200_OK
        admins = resp_list.data.get("data", {}).get("administrators", [])
        admin_emails = [a["email"] for a in admins]
        assert target.email not in admin_emails

    def test_non_primary_admin_receives_403_when_deleting_admin(self, secondary_client, secondary_admin_user):
        """3 & 4. Non-primary admin receives HTTP 403 on delete attempt, target remains untouched."""
        target = User.objects.create_user(
            email='target.admin3@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Target Admin 3',
            is_active=True
        )
        url = f"/api/v1/admin/administrators/{target.id}/"
        response = secondary_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "only the primary administrator" in response.data.get("message", "").lower()

        # Confirm target administrator remains in database
        assert User.objects.filter(id=target.id).exists()

    def test_primary_admin_cannot_delete_self(self, primary_client, primary_admin_user):
        """5. Primary admin cannot delete their own account."""
        url = f"/api/v1/admin/administrators/{primary_admin_user.id}/"
        response = primary_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data.get("error", {}).get("code") in ["PRIMARY_ADMIN_IMMUTABLE", "SELF_DELETION_PROHIBITED"]
        assert User.objects.filter(id=primary_admin_user.id).exists()

    def test_primary_admin_account_cannot_be_deleted(self, secondary_client, primary_admin_user):
        """6. Primary admin account is protected against deletion attempts by anyone."""
        url = f"/api/v1/admin/administrators/{primary_admin_user.id}/"
        response = secondary_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert User.objects.filter(id=primary_admin_user.id).exists()

    def test_admin_with_foreign_keys_is_deleted_and_reattributed(self, primary_client, primary_admin_user):
        """7. Admin with foreign keys (assessments & assignments) is deleted and objects re-attributed."""
        author_admin = User.objects.create_user(
            email='author.admin@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Author Admin',
            is_active=True
        )
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="E2E Author Assessment",
            description="Testing foreign key reattribution on deletion",
            created_by=author_admin,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60,
        )

        student_user = User.objects.create_user(
            email='candidate.test@codeguard.local',
            password='Password123!',
            role=Role.STUDENT,
            is_active=True
        )
        assignment = AssessmentAssignment.objects.create(
            assessment=assessment,
            student=student_user,
            assigned_by=author_admin
        )

        url = f"/api/v1/admin/administrators/{author_admin.id}/"
        response = primary_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.data.get("message", "").lower()

        # Confirm author_admin is gone
        assert not User.objects.filter(id=author_admin.id).exists()

        # Confirm assessment and assignment are re-attributed to Primary Admin
        assessment.refresh_from_db()
        assert assessment.created_by == primary_admin_user
        assignment.refresh_from_db()
        assert assignment.assigned_by == primary_admin_user

    def test_non_primary_admin_bulk_delete_receives_403(self, secondary_client, secondary_admin_user):
        """8. Bulk delete by non-primary admin receives HTTP 403."""
        target = User.objects.create_user(
            email='bulk.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Bulk Target',
            is_active=True
        )
        url = "/api/v1/admin/administrators/bulk-delete/"
        response = secondary_client.post(url, {"ids": [str(target.id)]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert User.objects.filter(id=target.id).exists()

    def test_primary_admin_bulk_delete_success(self, primary_client, primary_admin_user):
        """9. Bulk delete by primary admin deletes secondary admins cleanly."""
        target1 = User.objects.create_user(
            email='bulk1.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Bulk Target 1',
            is_active=True
        )
        target2 = User.objects.create_user(
            email='bulk2.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Bulk Target 2',
            is_active=True
        )
        url = "/api/v1/admin/administrators/bulk-delete/"
        response = primary_client.post(url, {"ids": [str(target1.id), str(target2.id)]}, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", {})
        assert data.get("success_count") == 2
        assert data.get("failure_count") == 0
        assert not User.objects.filter(id__in=[target1.id, target2.id]).exists()

    def test_service_level_authorization_enforcement(self, primary_admin_user, secondary_admin_user):
        """10. Service layer enforces Primary Admin authority directly."""
        target = User.objects.create_user(
            email='service.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Service Target',
            is_active=True
        )
        from django.core.exceptions import PermissionDenied
        with pytest.raises(PermissionDenied):
            AccountSecurityService.delete_administrator(target_admin=target, actor=secondary_admin_user)

        with pytest.raises(PermissionDenied):
            AccountSecurityService.bulk_delete_administrators(admin_ids=[str(target.id)], actor=secondary_admin_user)


@pytest.mark.django_db
class TestPrimaryAdminDeactivationAuthorization:

    def test_primary_admin_can_deactivate_secondary_admin(self, primary_client, primary_admin_user):
        """1. Primary admin can deactivate a secondary administrator account."""
        target = User.objects.create_user(
            email='deact.target1@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Deact Target 1',
            is_active=True
        )
        url = f"/api/v1/admin/administrators/{target.id}/status/"
        response = primary_client.post(url, {"is_active": False, "reason": "Administrative suspension"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.is_active is False

    def test_secondary_admin_cannot_deactivate_another_admin(self, secondary_client, secondary_admin_user):
        """2, 3 & 4. Secondary admin receives HTTP 403 and zero DB mutation occurs."""
        target = User.objects.create_user(
            email='deact.target2@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Deact Target 2',
            is_active=True
        )
        url = f"/api/v1/admin/administrators/{target.id}/status/"
        response = secondary_client.post(url, {"is_active": False, "reason": "Unauthorized attempt"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "only the primary administrator" in response.data.get("message", "").lower()

        # Zero DB mutation
        target.refresh_from_db()
        assert target.is_active is True

    def test_primary_admin_cannot_deactivate_self(self, primary_client, primary_admin_user):
        """5. Primary admin cannot deactivate their own account."""
        url = f"/api/v1/admin/administrators/{primary_admin_user.id}/status/"
        response = primary_client.post(url, {"is_active": False, "reason": "Self deactivation"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        primary_admin_user.refresh_from_db()
        assert primary_admin_user.is_active is True

    def test_primary_admin_cannot_deactivate_last_active_admin(self, primary_client, primary_admin_user):
        """6. Cannot deactivate the last remaining active administrator."""
        target = User.objects.create_user(
            email='last.active.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Last Active Target',
            is_active=True
        )
        # Mark all other admins except target inactive in DB
        User.objects.filter(role=Role.ADMIN).exclude(id=target.id).update(is_active=False)
        url = f"/api/v1/admin/administrators/{target.id}/status/"
        response = primary_client.post(url, {"is_active": False}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "LAST_ADMIN_PROTECTED" in str(response.data) or "at least one active" in str(response.data).lower()
        target.refresh_from_db()
        assert target.is_active is True

    def test_service_level_deactivation_authorization(self, primary_admin_user, secondary_admin_user):
        """7. Service layer enforces Primary Admin authority for set_administrator_status directly."""
        target = User.objects.create_user(
            email='service.deact.target@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            display_name='Service Deact Target',
            is_active=True
        )
        from django.core.exceptions import PermissionDenied
        with pytest.raises(PermissionDenied):
            AccountSecurityService.set_administrator_status(
                target_admin=target,
                is_active=False,
                actor=secondary_admin_user
            )
        target.refresh_from_db()
        assert target.is_active is True

