import uuid
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.assessments.models import Assessment, AssessmentSnapshot, TestAttempt
from apps.proctoring.models import IntegrityIncident
from apps.proctoring.services import AttemptTerminationPolicyService
from apps.invigilation.services import LiveInterventionService

class IntegrityStateVersionTest(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='integrity_student@example.com',
            password='Password123!',
            role='STUDENT'
        )
        self.proctor = User.objects.create_user(
            email='integrity_proctor@example.com',
            password='Password123!',
            role='PROCTOR'
        )
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title='Integrity Version Test Exam',
            status='PUBLISHED',
            created_by=self.proctor,
            duration_minutes=60,
            start_datetime=now,
            end_datetime=now + timezone.timedelta(days=1),
        )
        self.snapshot = AssessmentSnapshot.objects.create(
            assessment=self.assessment,
            version_number=1,
            snapshot_data={},
        )
        self.attempt = TestAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            status='IN_PROGRESS',
            started_at=timezone.now(),
            state_version=0
        )

    def test_state_version_increments_on_termination_pending(self):
        self.assertEqual(self.attempt.state_version, 0)
        res = AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id), reason='TAB_SWITCH')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state_version, 1)
        self.assertEqual(res['state_version'], 1)

    def test_state_version_increments_on_proctor_rescue(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id), reason='TAB_SWITCH')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state_version, 1)

        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id),
            reason='False positive tab switch'
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state_version, 2)
        self.assertFalse(self.attempt.termination_pending)

    def test_integrity_incident_idempotency(self):
        client_id = uuid.uuid4()
        inc1, created1 = IntegrityIncident.objects.get_or_create(
            attempt=self.attempt,
            client_incident_id=client_id,
            defaults={'incident_type': 'TAB_SWITCH', 'metadata': {'test': True}}
        )
        self.assertTrue(created1)

        inc2, created2 = IntegrityIncident.objects.get_or_create(
            attempt=self.attempt,
            client_incident_id=client_id,
            defaults={'incident_type': 'TAB_SWITCH', 'metadata': {'test': True}}
        )
        self.assertFalse(created2)
        self.assertEqual(inc1.id, inc2.id)
