from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .models import User, StudentProfile, Role, AuditLog, Section


class SectionSerializer(serializers.ModelSerializer):
    """
    Representation of an Academic Section entity.
    """
    student_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Section
        fields = [
            'id',
            'code',
            'name',
            'is_active',
            'student_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreateSectionSerializer(serializers.Serializer):
    """
    Schema for creating a new Academic Section.
    """
    code = serializers.CharField(required=True, max_length=32)
    name = serializers.CharField(required=True, max_length=128)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_code(self, value):
        from .services import SectionService
        return SectionService.normalize_code(value)


class UpdateSectionSerializer(serializers.Serializer):
    """
    Schema for updating an Academic Section.
    """
    name = serializers.CharField(required=False, max_length=128)
    is_active = serializers.BooleanField(required=False)


class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Representation of the student profile entity.
    """
    section = SectionSerializer(read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'section',
            'roll_number',
            'euid',
            'first_login_required',
            'certificate_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """
    Safe public user representation.
    Strictly excludes sensitive fields such as password hash, security tokens, or permissions internals.
    """
    student_profile = StudentProfileSerializer(read_only=True)
    first_login_required = serializers.SerializerMethodField()
    admin_id = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    is_primary = serializers.SerializerMethodField()
    is_primary_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'role',
            'is_active',
            'is_staff',
            'is_primary',
            'is_primary_admin',
            'first_login_required',
            'student_profile',
            'admin_id',
            'display_name',
            'first_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_first_login_required(self, obj: User) -> bool:
        if obj.role == Role.STUDENT and hasattr(obj, 'student_profile') and obj.student_profile:
            return obj.student_profile.first_login_required or getattr(obj, 'first_login_required', False)
        return getattr(obj, 'first_login_required', False)

    def get_is_primary(self, obj: User) -> bool:
        return getattr(obj, 'is_primary_admin', False)


class AdministratorSerializer(serializers.ModelSerializer):
    """
    Representation of an Administrator user for the Admin Management area.
    """
    admin_id = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    is_primary = serializers.SerializerMethodField()
    is_primary_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'admin_id',
            'email',
            'display_name',
            'first_name',
            'role',
            'is_active',
            'is_primary',
            'is_primary_admin',
            'first_login_required',
            'created_at',
            'updated_at',
            'last_login',
        ]
        read_only_fields = fields

    def get_is_primary(self, obj: User) -> bool:
        return getattr(obj, 'is_primary_admin', False)


class UpdateAdministratorSerializer(serializers.Serializer):
    """
    Decommissioned: Administrator identity and account details are immutable. Editing is prohibited.
    """
    display_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        raise serializers.ValidationError("Administrator identity and account details are immutable. Editing is prohibited.")


class ResetPasswordSerializer(serializers.Serializer):
    """
    Serializer for administrative password reset.
    Requires an administrative justification, temporary password, and confirmation.
    """
    reason = serializers.CharField(
        required=True,
        min_length=3,
        max_length=500,
        trim_whitespace=True,
        help_text="Administrative justification for the password reset."
    )
    temporary_password = serializers.CharField(
        required=False,
        allow_blank=True,
        default=None,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Optional custom temporary password."
    )
    confirm_temporary_password = serializers.CharField(
        required=False,
        allow_blank=True,
        default=None,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Confirmation of the optional custom temporary password."
    )

    def validate(self, attrs):
        temp_pwd = attrs.get('temporary_password')
        confirm_pwd = attrs.get('confirm_temporary_password')
        if temp_pwd or confirm_pwd:
            if not temp_pwd or not confirm_pwd:
                raise serializers.ValidationError({
                    "confirm_temporary_password": "Both temporary password and confirmation are required if setting manually."
                })
            if temp_pwd != confirm_pwd:
                raise serializers.ValidationError({
                    "confirm_temporary_password": "Temporary password and confirmation do not match."
                })
            validate_password(temp_pwd)
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the immutable Security Audit Trail.
    Strictly sanitizes and never returns sensitive tokens, credentials, or hashes.
    """
    actor_id = serializers.UUIDField(source='actor.id', read_only=True)
    actor_name = serializers.SerializerMethodField()
    actor_admin_id = serializers.SerializerMethodField()
    target_identity = serializers.SerializerMethodField()
    target_email = serializers.SerializerMethodField()
    target_role = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'actor_id',
            'actor_name',
            'actor_admin_id',
            'target_type',
            'target_id',
            'target_identity',
            'target_email',
            'target_role',
            'reason',
            'result',
            'metadata',
            'ip_address',
            'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj: AuditLog) -> str:
        if obj.metadata and 'actor_name' in obj.metadata:
            return obj.metadata['actor_name']
        if obj.actor:
            return obj.actor.display_name
        return "SYSTEM"

    def get_actor_admin_id(self, obj: AuditLog) -> str:
        if obj.metadata and 'actor_admin_id' in obj.metadata:
            return obj.metadata['actor_admin_id']
        if obj.actor and getattr(obj.actor, 'admin_id', None):
            return obj.actor.admin_id
        return ""

    def get_target_identity(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_identity') or obj.metadata.get('euid') or obj.metadata.get('admin_id') or obj.metadata.get('roll_number') or ""

    def get_target_email(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_email') or obj.metadata.get('email') or ""

    def get_target_role(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_role') or ""

    def get_reason(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('reason') or ""

    def get_result(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return "SUCCESS"
        return obj.metadata.get('result', "SUCCESS")



class CreateAdministratorSerializer(serializers.Serializer):
    """
    Validation schema for creating a new Administrator account.
    """
    email = serializers.EmailField()
    display_name = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=False, allow_blank=True, default=None, write_only=True, min_length=8)
    is_active = serializers.BooleanField(default=True)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return email

    def validate(self, attrs):
        pwd = attrs.get('password')
        confirm_pwd = attrs.get('confirm_password')
        if confirm_pwd is not None and pwd != confirm_pwd:
            raise serializers.ValidationError({"confirm_password": "Password and confirmation do not match."})
        validate_password(pwd)
        return attrs


class StudentDetailSerializer(serializers.ModelSerializer):
    """
    Admin-level detailed student representation joining User and StudentProfile fields.
    """
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email')
    is_active = serializers.BooleanField(source='user.is_active')
    role = serializers.CharField(source='user.role', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    display_name = serializers.CharField(source='user.display_name', read_only=True)
    name = serializers.SerializerMethodField()
    coins = serializers.SerializerMethodField()
    section = SectionSerializer(read_only=True)
    section_id = serializers.UUIDField(source='section.id', read_only=True, allow_null=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'user_id',
            'email',
            'role',
            'name',
            'first_name',
            'last_name',
            'display_name',
            'coins',
            'section',
            'section_id',
            'roll_number',
            'euid',
            'is_active',
            'first_login_required',
            'certificate_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'role', 'roll_number', 'euid', 'created_at', 'updated_at']

    def get_name(self, obj: StudentProfile) -> str:
        if obj.certificate_name:
            return obj.certificate_name
        if obj.user and obj.user.display_name:
            return obj.user.display_name
        if obj.user and (obj.user.first_name or obj.user.last_name):
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.roll_number

    def get_coins(self, obj: StudentProfile) -> int:
        if hasattr(obj, 'coins') and obj.coins is not None:
            return obj.coins
        if hasattr(obj.user, 'coins') and obj.user.coins is not None:
            return obj.user.coins
        from apps.results.models import StudentCoinLedger
        from django.db.models import Sum
        val = StudentCoinLedger.objects.filter(student_id=obj.user_id).aggregate(total=Sum('coins_awarded'))['total']
        return val or 0


class CreateStudentSerializer(serializers.Serializer):
    """
    Serializer for individual student creation by an administrator.
    Section-free: students identified by Name + Roll Number + Email.
    """
    email = serializers.EmailField(required=True)
    roll_number = serializers.CharField(required=True, max_length=64)
    name = serializers.CharField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    display_name = serializers.CharField(required=False, allow_blank=True, default="")
    section_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class UpdateStudentSerializer(serializers.Serializer):
    """
    Serializer for updating student profile.
    Email and academic section classification may be modified by authorized administrators.
    Roll number, EUID, role, and internal fields are strictly immutable.
    """
    email = serializers.EmailField(required=False)
    section_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        # Explicitly reject attempts to modify immutable identity or server-controlled fields
        immutable_fields = [
            'roll_number',
            'euid',
            'role',
            'user_id',
            'id',
            'is_active',
            'first_login_required',
            'password',
        ]
        errors = {}
        for field in immutable_fields:
            if field in self.initial_data:
                field_label = field.replace('_', ' ').capitalize()
                errors[field] = [f"{field_label} cannot be modified after student creation."]

        if errors:
            raise ValidationError(errors)

        return attrs


class BulkImportStudentItemSerializer(serializers.Serializer):
    """
    Schema for individual student row in bulk import payload.
    Supports roll-number-only onboarding or roll_number + name / email.
    """
    roll_number = serializers.CharField(required=True, max_length=64)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    name = serializers.CharField(required=False, allow_blank=True, default="")
    certificate_name = serializers.CharField(required=False, allow_blank=True, default="")
    section = serializers.CharField(required=False, allow_blank=True, default="")


class BulkImportConfirmSerializer(serializers.Serializer):
    """
    Payload containing verified student rows to create in batch.
    """
    filename = serializers.CharField(required=False, allow_blank=True, default="import.csv")
    students = BulkImportStudentItemSerializer(many=True, required=True)


class ChangePasswordSerializer(serializers.Serializer):
    """
    Secure password change serializer with Django validator integration and first_login satisfaction.
    """
    current_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=150
    )
    last_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=150
    )
    certificate_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Full name as it should appear on official certificates of participation."
    )

    def validate(self, attrs):
        user = self.context.get('request').user
        current_password = attrs.get('current_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if not user.check_password(current_password):
            raise ValidationError({"current_password": "The current password provided is incorrect."})

        if new_password != confirm_password:
            raise ValidationError({"confirm_password": "New password and confirmation do not match."})

        if current_password == new_password:
            raise ValidationError({"new_password": "New password must be different from current password."})

        # Run Django's configured password validators
        validate_password(new_password, user=user)

        # On student first login, require certificate_name or fall back to full name
        if user.role == Role.STUDENT and user.first_login_required:
            cert_name = attrs.get('certificate_name', '').strip()
            fallback_name = f"{attrs.get('first_name', '').strip()} {attrs.get('last_name', '').strip()}".strip()
            if not cert_name and not fallback_name and not getattr(user, 'display_name', '').strip():
                raise ValidationError({
                    "certificate_name": "Full Name for Certificate Printing is required upon initial setup."
                })

        return attrs


class LoginSerializer(serializers.Serializer):
    """
    Multi-Identifier Authentication Login Serializer.
    Supports: Email + Password, EUID + Password, or Roll Number + Password.
    """
    identifier = serializers.CharField(
        required=False,
        help_text="Student Email, Exam Unique ID (EUID), or Roll Number"
    )
    email = serializers.CharField(
        required=False,
        help_text="Alternative email field for backward compatibility"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        raw_id = (attrs.get('identifier') or attrs.get('email') or '').strip()
        password = attrs.get('password')

        if not raw_id or not password:
            raise ValidationError("Both login identifier (Email, EUID, or Roll Number) and password are required.")

        user_obj = None

        # Determine if login identifier is Email or EUID
        if '@' in raw_id:
            email_lookup = raw_id.lower()
            try:
                user_obj = User.objects.select_related('student_profile').get(email=email_lookup)
            except User.DoesNotExist:
                user_obj = None
        else:
            raw_upper = raw_id.upper()
            if raw_upper.startswith('EUAD-') or raw_upper.startswith('CG-ADM-'):
                raise AuthenticationFailed(
                    detail="Admin ID is an identity display identifier, not a login credential. Please sign in with your registered email.",
                    code="ADMIN_ID_NOT_LOGIN_CREDENTIAL"
                )
            # EUID lookup for students (starts with CG-)
            if raw_upper.startswith('CG-'):
                try:
                    profile = StudentProfile.objects.select_related('user').get(euid=raw_upper)
                    user_obj = profile.user
                except StudentProfile.DoesNotExist:
                    user_obj = None
            else:
                # Roll number or fallback EUID lookup for students
                profile = StudentProfile.objects.select_related('user').filter(
                    Q(roll_number__iexact=raw_id) | Q(euid__iexact=raw_id)
                ).first()
                if profile:
                    user_obj = profile.user
                else:
                    user_obj = None

        if user_obj and not user_obj.is_active:
            raise AuthenticationFailed(
                detail="Your account has been disabled. Please contact system administrator.",
                code="ACCOUNT_DISABLED"
            )

        if not user_obj:
            raise AuthenticationFailed(
                detail="Invalid login credentials.",
                code="INVALID_CREDENTIALS"
            )

        # Authenticate with resolved user email
        user = authenticate(
            request=self.context.get('request'),
            username=user_obj.email,
            password=password
        )

        if not user:
            raise AuthenticationFailed(
                detail="Invalid login credentials.",
                code="INVALID_CREDENTIALS"
            )

        if not user.is_active:
            raise AuthenticationFailed(
                detail="Your account has been disabled. Please contact system administrator.",
                code="ACCOUNT_DISABLED"
            )

        attrs['user'] = user
        return attrs


class BulkAccountDeleteSerializer(serializers.Serializer):
    """
    Serializer for bulk deletion of students or secondary administrators.
    """
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of target user or profile IDs to delete."
    )

