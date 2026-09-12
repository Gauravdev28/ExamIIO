import pytest
from django.core.management import call_command, CommandError
from rest_framework.test import APIClient

from apps.accounts.models import User, Role, StudentProfile, AuditLog
from apps.accounts.services import AuditService
from apps.assessments.models import Assessment, TestAttempt
from apps.results.models import AssessmentResult, Certificate


@pytest.fixture
def primary_admin(db):
    """Authoritative Primary Administrator fixture"""
    admin = User.objects.filter(admin_id='EUAD-GAURAV-099').first()
    if not admin:
        admin = User.objects.create_user(
            email='gauravagldeveloper28@gmail.com',
            password='Password123!',
            role=Role.ADMIN,
            admin_id='EUAD-GAURAV-099',
            display_name='Gaurav Agarwal',
            is_staff=True,
            is_superuser=True,
            primary_admin_marker='PRIMARY',
        )
    return admin


@pytest.mark.django_db
class TestSecurityAuditPurge:
    def test_audit_log_records_can_be_purged(self, primary_admin):
        AuditLog.objects.create(actor=primary_admin, action="TEST_ACTION_1")
        AuditLog.objects.create(actor=primary_admin, action="TEST_ACTION_2")
        assert AuditLog.objects.count() >= 2

        deleted_count = AuditService.purge_security_audit_trail(clear_all=True, confirm=True)
        assert deleted_count >= 2
        assert AuditLog.objects.count() == 0

    def test_clear_all_requires_explicit_confirmation_in_service(self, primary_admin):
        AuditLog.objects.create(actor=primary_admin, action="TEST_ACTION")
        initial_count = AuditLog.objects.count()

        with pytest.raises(ValueError, match="confirmation"):
            AuditService.purge_security_audit_trail(clear_all=True, confirm=False)

        assert AuditLog.objects.count() == initial_count

    def test_purge_removes_only_audit_logs_and_leaves_business_records_unchanged(self, primary_admin):
        # Setup business entities
        student_user = User.objects.create_user(
            email="student_purge_test@codeguard.test",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=student_user,
            roll_number="ROLL-PURGE-001",
            euid="EUID-PURGE-001"
        )
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Purge Test Assessment",
            description="Assessment for audit purge verification",
            start_datetime=now,
            end_datetime=now + timedelta(days=1),
            duration_minutes=60,
            created_by=primary_admin
        )
        from apps.assessments.models import AssessmentSnapshot, AttemptStatus
        snapshot = AssessmentSnapshot.objects.create(
            assessment=assessment,
            version_number=1,
            snapshot_data={"title": assessment.title},
            server_evaluation_bundle={}
        )
        attempt = TestAttempt.objects.create(
            assessment=assessment,
            assessment_snapshot=snapshot,
            student=student_user,
            status=AttemptStatus.SUBMITTED
        )
        result = AssessmentResult.objects.create(
            attempt=attempt,
            student=student_user,
            assessment=assessment,
            assessment_snapshot=snapshot,
            total_score_earned=100,
            total_possible_score=100,
            percentage=100
        )
        cert = Certificate.objects.create(
            certificate_id="CERT-PURGE-001",
            exam=assessment,
            student=student_user,
            attempt=attempt,
            printed_name="Student Test"
        )

        AuditLog.objects.create(actor=primary_admin, action="ADMIN_AUDIT_ENTRY")
        AuditLog.objects.create(actor=student_user, action="STUDENT_AUDIT_ENTRY")

        # Snapshot business entity counts
        user_count_before = User.objects.count()
        student_profile_count_before = StudentProfile.objects.count()
        assessment_count_before = Assessment.objects.count()
        attempt_count_before = TestAttempt.objects.count()
        result_count_before = AssessmentResult.objects.count()
        cert_count_before = Certificate.objects.count()

        # Purge audit logs
        AuditService.purge_security_audit_trail(clear_all=True, confirm=True)

        # AuditLog is 0
        assert AuditLog.objects.count() == 0

        # All business records completely intact
        assert User.objects.count() == user_count_before
        assert StudentProfile.objects.count() == student_profile_count_before
        assert Assessment.objects.count() == assessment_count_before
        assert TestAttempt.objects.count() == attempt_count_before
        assert AssessmentResult.objects.count() == result_count_before
        assert Certificate.objects.count() == cert_count_before

    def test_management_command_without_confirm_does_not_delete_records(self, primary_admin):
        AuditLog.objects.create(actor=primary_admin, action="PROTECTED_ENTRY")
        initial_count = AuditLog.objects.count()

        with pytest.raises(CommandError, match="confirmation"):
            call_command('purge_security_audit_trail', all=True)

        assert AuditLog.objects.count() == initial_count

    def test_management_command_dry_run_reports_without_deleting(self, primary_admin):
        AuditLog.objects.create(actor=primary_admin, action="DRY_RUN_ENTRY")
        initial_count = AuditLog.objects.count()

        call_command('purge_security_audit_trail', all=True, dry_run=True)
        assert AuditLog.objects.count() == initial_count

    def test_management_command_with_confirm_purges_audit_trail(self, primary_admin):
        AuditLog.objects.create(actor=primary_admin, action="CONFIRMED_PURGE_ENTRY")
        assert AuditLog.objects.count() >= 1

        call_command('purge_security_audit_trail', all=True, confirm=True)
        assert AuditLog.objects.count() == 0

    def test_purge_is_safe_when_empty(self):
        AuditLog.objects.all().delete()
        assert AuditLog.objects.count() == 0

        deleted = AuditService.purge_security_audit_trail(clear_all=True, confirm=True)
        assert deleted == 0

        # Management command also handles empty state safely
        call_command('purge_security_audit_trail', all=True, confirm=True)
        assert AuditLog.objects.count() == 0

    def test_security_audit_log_api_endpoint_returns_empty_cleanly(self, primary_admin):
        AuditService.purge_security_audit_trail(clear_all=True, confirm=True)
        assert AuditLog.objects.count() == 0

        client = APIClient()
        client.force_authenticate(user=primary_admin)

        response = client.get('/api/v1/admin/audit-logs/')
        assert response.status_code == 200
        payload = response.json()
        assert payload['data']['total'] == 0
        assert payload['data']['logs'] == []
