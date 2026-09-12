import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.accounts.serializers import ChangePasswordSerializer


@pytest.mark.django_db
class TestPasswordValidation:
    """
    Test suite for password validation and first-login password reset.
    Ensures user-attribute similarity restrictions (first_name, last_name, username)
    are removed, while minimum-length, common-password, and numeric validators remain active.
    """

    @pytest.fixture
    def student_user(self):
        user = User.objects.create(
            email="vikul.tomar@example.com",
            display_name="Vikul Tomar",
            role=Role.STUDENT,
            first_login_required=True,
            is_active=True,
        )
        user.set_password("InitialTempPass123!")
        user.save()
        return user

    def test_direct_password_validation_allows_first_name(self, student_user):
        """1. Direct validate_password with user context allows first_name in password."""
        assert student_user.first_name == "Vikul"
        # Both examples from requirements: "Vikul@12345" and "VikulTomar@123"
        validate_password("Vikul@12345", user=student_user)
        validate_password("VikulTomar@123", user=student_user)

    def test_direct_password_validation_allows_last_name(self, student_user):
        """2. Direct validate_password with user context allows last_name in password."""
        validate_password("TomarSecure#2026", user=student_user)

    def test_direct_password_validation_rejects_short_password(self, student_user):
        """3. Password shorter than 8 characters is rejected by MinimumLengthValidator."""
        with pytest.raises(DjangoValidationError) as excinfo:
            validate_password("Vikul1!", user=student_user)
        assert any("at least 8 characters" in msg for msg in excinfo.value.messages)

    def test_direct_password_validation_rejects_common_password(self, student_user):
        """4. Common password is rejected by CommonPasswordValidator."""
        with pytest.raises(DjangoValidationError) as excinfo:
            validate_password("password", user=student_user)
        assert any("too common" in msg for msg in excinfo.value.messages)

    def test_direct_password_validation_rejects_entirely_numeric_password(self, student_user):
        """5. Entirely numeric password is rejected by NumericPasswordValidator."""
        with pytest.raises(DjangoValidationError) as excinfo:
            validate_password("1234567890", user=student_user)
        assert any("entirely numeric" in msg for msg in excinfo.value.messages)

    def test_change_password_serializer_allows_first_name(self, student_user):
        """6. ChangePasswordSerializer accepts password containing first_name for first login."""
        class MockRequest:
            user = student_user

        data = {
            "current_password": "InitialTempPass123!",
            "new_password": "Vikul@12345",
            "confirm_password": "Vikul@12345",
            "first_name": "Vikul",
            "last_name": "Tomar",
            "certificate_name": "Vikul Tomar",
        }
        serializer = ChangePasswordSerializer(data=data, context={"request": MockRequest()})
        assert serializer.is_valid(), serializer.errors

    def test_change_password_api_endpoint_first_login_flow(self, student_user):
        """7. First-login password reset API accepts passwords with first_name and clears first_login_required."""
        client = APIClient()
        client.force_authenticate(user=student_user)

        res = client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": "InitialTempPass123!",
                "new_password": "VikulTomar@123",
                "confirm_password": "VikulTomar@123",
                "first_name": "Vikul",
                "last_name": "Tomar",
                "certificate_name": "Vikul Tomar",
            },
            format="json",
        )

        assert res.status_code == 200, res.data
        student_user.refresh_from_db()
        assert student_user.check_password("VikulTomar@123") is True
        assert student_user.first_login_required is False
