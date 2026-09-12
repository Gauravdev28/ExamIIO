import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, StudentProfile, Role, AuditLog
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.questions.services import QuestionService
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    AttemptTerminationPolicyService,
)
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
)
from apps.invigilation.services import (
    LiveInterventionService,
    ProctorTriageQueueService,
)
from apps.results.services import CoinRewardService
from apps.results.models import StudentCoinLedger


@pytest.mark.django_db
class TestIssue3WindowTerminationPolicy:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.admin = User.objects.create(email="admin_term@example.com", role=Role.ADMIN)
        self.proctor = User.objects.create(email="proctor_term@example.com", role=Role.PROCTOR)
        self.student = User.objects.create(email="student_term@example.com", role=Role.STUDENT)
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="TERM-ROLL-001",
            euid="TERM-EUID-001",
            first_login_required=False
        )

        # Create test question
        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Termination Policy MCQ',
            description='Test termination policy question',
            points=100,
            type_config={
                'options': [
                    {'id': 'OPT_A', 'text': 'Correct Option'},
                    {'id': 'OPT_B', 'text': 'Wrong Option'}
                ],
                'correct_options': ['OPT_A']
            },
            actor=self.admin,
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Window Focus Termination Policy Assessment",
            description="Testing 2-minute termination policy",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=100,
            attempt_limit=1,
            max_confirmed_violations=3
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=100
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        # Assign proctor
        ProctorAssignment.objects.create(
            assessment=self.published_assessment,
            proctor=self.proctor,
            is_active=True
        )

        # Start attempt
        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.published_assessment.id),
            actor=self.student
        )
        self.session = ProctoringSessionService.start_session(self.attempt)

        self.client_student = APIClient()
        self.client_student.force_authenticate(user=self.student)

        self.client_proctor = APIClient()
        self.client_proctor.force_authenticate(user=self.proctor)

        self.client_admin = APIClient()
        self.client_admin.force_authenticate(user=self.admin)

    # Test 1: Student leaving examination window triggers focus-loss detection
    def test_01_student_leaving_window_triggers_focus_loss_detection(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_BLUR", "metadata": {"duration_ms": 1000}}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["status"] == "RECORDED"
        assert res.data["termination_pending"] is True

    # Test 2: Focus loss sets attempt termination state to TERMINATION_PENDING
    def test_02_focus_loss_sets_attempt_termination_pending(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        self.client_student.post(url, {"event_type": "WINDOW_BLUR"}, format="json")
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True

    # Test 3: Termination pending state sets 2-minute countdown (120 seconds)
    def test_03_termination_pending_sets_2_minute_countdown(self):
        now = timezone.now()
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        self.attempt.refresh_from_db()
        assert self.attempt.termination_deadline is not None
        diff = (self.attempt.termination_deadline - now).total_seconds()
        assert 118 <= diff <= 122

    # Test 4: Continuous countdown timer decrements correctly
    def test_04_continuous_countdown_timer_decrements_correctly(self):
        now = timezone.now()
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = now + timedelta(seconds=90)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/"
        res = self.client_student.get(url)
        assert res.status_code == status.HTTP_200_OK
        rem = res.data["data"]["termination_remaining_seconds"]
        assert 88 <= rem <= 91

    # Test 5: Student returning focus to examination window does NOT dismiss warning
    def test_05_student_returning_focus_does_not_dismiss_warning(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/heartbeat/"
        res = self.client_student.post(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["termination_pending"] is True

    # Test 6: Student returning focus does NOT reset or cancel termination countdown
    def test_06_student_returning_focus_does_not_reset_countdown(self):
        past_deadline = timezone.now() + timedelta(seconds=75)
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = past_deadline
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        # Send heartbeat (simulating window in focus)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/heartbeat/"
        res = self.client_student.post(url)
        assert res.status_code == status.HTTP_200_OK
        self.attempt.refresh_from_db()
        # Deadline remains 75s in future, NOT reset to 120s
        assert self.attempt.termination_deadline == past_deadline

    # Test 7: Page refresh recalculates remaining time from server deadline without restarting at 2:00
    def test_07_page_refresh_recalculates_remaining_time_without_restart(self):
        now = timezone.now()
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = now + timedelta(seconds=60)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/"
        res = self.client_student.get(url)
        rem = res.data["data"]["termination_remaining_seconds"]
        assert 58 <= rem <= 61

    # Test 8: Multiple window blur events do NOT restart or extend the 2-minute countdown
    def test_08_multiple_blur_events_do_not_restart_or_extend_countdown(self):
        now = timezone.now()
        original_deadline = now + timedelta(seconds=120)
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = original_deadline
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        # Ingest another blur event
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_BLUR"}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        self.attempt.refresh_from_db()
        assert self.attempt.termination_deadline == original_deadline

    # Test 9: Authorized proctor receives real-time notification of focus loss
    def test_09_proctor_receives_realtime_notification_of_focus_loss(self):
        res = AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id), reason="EXAM WINDOW LOST FOCUS")
        assert res["status"] == "TERMINATION_PENDING"
        interventions = ProctorIntervention.objects.filter(
            attempt=self.attempt,
            event_type=InterventionType.TERMINATION_PENDING
        )
        assert interventions.exists()

    # Test 10: Proctor receives candidate identifier, assessment title, attempt number, and focus-loss reason
    def test_10_proctor_receives_candidate_assessment_attempt_focus_loss_reason(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id), reason="EXAM WINDOW LOST FOCUS")
        intervention = ProctorIntervention.objects.filter(
            attempt=self.attempt,
            event_type=InterventionType.TERMINATION_PENDING
        ).first()
        assert intervention is not None
        assert intervention.reason_text == "EXAM WINDOW LOST FOCUS"
        assert intervention.student == self.student
        assert intervention.attempt.assessment.title == self.published_assessment.title

    # Test 11: Proctor dashboard displays TERMINATION PENDING status with live countdown
    def test_11_proctor_dashboard_displays_termination_pending_with_countdown(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        roster = ProctorTriageQueueService.get_triage_roster(str(self.published_assessment.id), self.proctor)
        item = next(r for r in roster if r["attempt_id"] == str(self.attempt.id))
        assert item["termination_pending"] is True
        assert item["termination_remaining_seconds"] is not None
        assert 115 <= item["termination_remaining_seconds"] <= 120

    # Test 12: Proctor dashboard provides clear "Cancel Exam Termination" action
    def test_12_proctor_dashboard_provides_clear_cancel_action(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        url = f"/api/v1/invigilation/attempts/{self.attempt.id}/cancel-termination/"
        res = self.client_proctor.post(url, {"reason": "Proctor verified accidental blur"}, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "TERMINATION_CANCELLED"

    # Test 13: Proctor intervention successfully cancels pending termination before 2-minute expiration
    def test_13_proctor_intervention_cancels_pending_termination_before_expiration(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        intervention = LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id),
            reason="Rescued by proctor"
        )
        assert intervention is not None
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is False

    # Test 14: Proctor intervention returns attempt to normal IN_PROGRESS status
    def test_14_proctor_intervention_returns_attempt_to_normal_in_progress(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id)
        )
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    # Test 15: Proctor intervention dismisses student termination warning modal
    def test_15_proctor_intervention_dismisses_student_warning_modal(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id)
        )
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/heartbeat/"
        res = self.client_student.post(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["termination_pending"] is False

    # Test 16: Examination continues normally after proctor intervention without timer loss
    def test_16_examination_continues_normally_after_proctor_intervention_without_timer_loss(self):
        original_expires_at = self.attempt.expires_at
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id)
        )
        self.attempt.refresh_from_db()
        # Original exam expiration is strictly preserved (no time penalty, no improper extension)
        assert self.attempt.expires_at == original_expires_at

    # Test 17: All answers previously submitted or saved remain intact after proctor intervention
    def test_17_all_answers_previously_submitted_or_saved_remain_intact(self):
        q_id = self.attempt.question_order[0]
        AttemptService.save_answer(
            student=self.student,
            attempt_id=str(self.attempt.id),
            snapshot_question_id=q_id,
            answer_data={"selected_options": ["OPT_A"]},
            client_revision=1,
            actor=self.student
        )
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id)
        )
        self.attempt.refresh_from_db()
        ans = self.attempt.answers.filter(question_id=q_id).first()
        assert ans is not None
        assert ans.selected_options == ["OPT_A"]

    # Test 18: Proctor cancellation is logged in audit trail with proctor identity, timestamp, and justification
    def test_18_proctor_cancellation_logged_in_audit_trail(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id),
            reason="Verified legitimate disruption"
        )
        audit = AuditLog.objects.filter(
            action="PROCTOR_TERMINATION_CANCELLED",
            target_id=str(self.attempt.id)
        ).first()
        assert audit is not None
        assert audit.actor == self.proctor
        assert audit.metadata.get("reason") == "Verified legitimate disruption"

    # Test 19: Proctor intervention records immutable audit event
    def test_19_proctor_intervention_records_immutable_audit_event(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        LiveInterventionService.cancel_pending_termination(
            proctor=self.proctor,
            attempt_id=str(self.attempt.id),
            reason="Audit test reason"
        )
        intervention = ProctorIntervention.objects.filter(
            attempt=self.attempt,
            event_type=InterventionType.TERMINATION_CANCELLED
        ).first()
        assert intervention is not None
        assert intervention.proctor == self.proctor
        assert intervention.reason_text == "Audit test reason"

    # Test 20: Countdown expiration without proctor intervention results in automatic examination cancellation
    def test_20_countdown_expiration_without_intervention_results_in_auto_cancellation(self):
        past = timezone.now() - timedelta(seconds=1)
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = past
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        result = AttemptTerminationPolicyService.check_and_expire_termination(str(self.attempt.id))
        assert result["status"] == "EXPIRED"

    # Test 21: Countdown expiration transitions attempt status to CANCELLED
    def test_21_countdown_expiration_transitions_attempt_status_to_cancelled(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=5)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        AttemptTerminationPolicyService.check_and_expire_termination(str(self.attempt.id))
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED

    # Test 22: Cancelled attempt records disqualification reason: "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
    def test_22_cancelled_attempt_records_disqualification_reason(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=5)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        AttemptTerminationPolicyService.check_and_expire_termination(str(self.attempt.id))
        self.attempt.refresh_from_db()
        assert self.attempt.is_disqualified is True
        assert self.attempt.disqualification_reason == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    # Test 23: Student sees clear, permanent termination notice after countdown expires
    def test_23_student_sees_clear_permanent_termination_notice_after_expiration(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=5)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/"
        res = self.client_student.get(url)
        assert res.status_code == status.HTTP_200_OK
        data = res.data["data"]
        assert data["status"] == "CANCELLED"
        assert data["is_disqualified"] is True
        assert data["disqualification_reason"] == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    # Test 24: Student cannot answer further questions after termination expiration
    def test_24_student_cannot_answer_further_questions_after_termination(self):
        self.attempt.status = AttemptStatus.CANCELLED
        self.attempt.is_disqualified = True
        self.attempt.disqualification_reason = "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
        self.attempt.save(update_fields=['status', 'is_disqualified', 'disqualification_reason'])

        q_id = self.attempt.question_order[0]
        url = f"/api/v1/student/attempts/{self.attempt.id}/answers/{q_id}/"
        res = self.client_student.post(url, {"selected_options": ["OPT_A"], "revision": 2}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # Test 25: Student cannot submit attempt after termination expiration
    def test_25_student_cannot_submit_attempt_after_termination(self):
        self.attempt.status = AttemptStatus.CANCELLED
        self.attempt.is_disqualified = True
        self.attempt.save(update_fields=['status', 'is_disqualified'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/submit/"
        res = self.client_student.post(url, {}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # Test 26: Proctor dashboard updates immediately to reflect automatic cancellation and final disqualified state
    def test_26_proctor_dashboard_updates_immediately_to_reflect_cancellation(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=5)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        # Roster auto-expires overdue attempts and exposes them in the final disqualified state
        roster = ProctorTriageQueueService.get_triage_roster(str(self.published_assessment.id), self.proctor)
        item = next(r for r in roster if r["attempt_id"] == str(self.attempt.id))
        assert item["is_disqualified"] is True
        assert item["status"] == "CANCELLED"
        assert item["attempt_status"] == "DISQUALIFIED"
        assert item["termination_pending"] is False
        assert item["disqualification_reason"] == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    # Test 27: Proctor cannot cancel termination after countdown expiration has occurred
    def test_27_proctor_cannot_cancel_termination_after_countdown_expiration(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=10)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/invigilation/attempts/{self.attempt.id}/cancel-termination/"
        res = self.client_proctor.post(url, {"reason": "Late proctor rescue"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # Test 28: Attempt to cancel already-expired termination is rejected with appropriate error
    def test_28_attempt_to_cancel_already_expired_termination_rejected_with_error(self):
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=10)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/invigilation/attempts/{self.attempt.id}/cancel-termination/"
        res = self.client_proctor.post(url, {"reason": "Late rescue"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "2-minute deadline has expired" in str(res.data)
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED

    # Test 29: Concurrent student actions during countdown do not corrupt examination state
    def test_29_concurrent_student_actions_during_countdown_do_not_corrupt_state(self):
        now = timezone.now()
        original_deadline = now + timedelta(seconds=100)
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = original_deadline
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        q_id = self.attempt.question_order[0]
        url_ans = f"/api/v1/student/attempts/{self.attempt.id}/answers/{q_id}/"
        res = self.client_student.post(url_ans, {"selected_options": ["OPT_A"], "revision": 1}, format="json")
        assert res.status_code == status.HTTP_200_OK

        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True
        assert self.attempt.termination_deadline == original_deadline

    # Test 30: Network reconnection during countdown synchronizes remaining time correctly
    def test_30_network_reconnection_during_countdown_synchronizes_remaining_time(self):
        now = timezone.now()
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = now + timedelta(seconds=45)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/heartbeat/"
        res = self.client_student.post(url)
        assert res.status_code == status.HTTP_200_OK
        rem = res.data["termination_remaining_seconds"]
        assert 43 <= rem <= 46

    # Test 31: Coins awarded upon termination are strictly 0 for disqualified attempts
    def test_31_coins_awarded_upon_termination_are_strictly_zero_for_disqualified(self):
        # Even if a student answered a question before focus loss
        q_id = self.attempt.question_order[0]
        AttemptService.save_answer(
            student=self.student,
            attempt_id=str(self.attempt.id),
            snapshot_question_id=q_id,
            answer_data={"selected_options": ["OPT_A"]},
            client_revision=1,
            actor=self.student
        )
        self.attempt.termination_pending = True
        self.attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        self.attempt.save(update_fields=['termination_pending', 'termination_deadline'])

        AttemptTerminationPolicyService.check_and_expire_termination(str(self.attempt.id))
        self.attempt.refresh_from_db()

        assert self.attempt.status == AttemptStatus.CANCELLED
        # No question results are evaluated as correct and no coins are awarded
        coins_awarded = StudentCoinLedger.objects.filter(attempt=self.attempt).count()
        assert coins_awarded == 0

    # Test 32: Completed examination with valid answers awards coins correctly while terminated attempt does not
    def test_32_completed_examination_awards_coins_while_terminated_does_not(self):
        # Student 2 completes normally and receives coins
        student2 = User.objects.create(email="student2_term@example.com", role=Role.STUDENT)
        StudentProfile.objects.create(user=student2, roll_number="TERM-002", euid="TERM-EUID-002", first_login_required=False)
        AssessmentAssignment.objects.create(assessment=self.assessment, student=student2, assigned_by=self.admin)
        attempt2, _ = AttemptService.start_attempt(student2, str(self.published_assessment.id), actor=student2)

        q_id = attempt2.question_order[0]
        AttemptService.save_answer(
            student=student2,
            attempt_id=str(attempt2.id),
            snapshot_question_id=q_id,
            answer_data={"selected_options": ["OPT_A"]},
            client_revision=1,
            actor=student2
        )
        AttemptService.submit_attempt(student2, str(attempt2.id), actor=student2)

        qr = type('QR', (), {'question_id': q_id, 'is_correct': True})()
        new_coins = CoinRewardService.award_coins_for_finalized_attempt(attempt2, [qr])
        assert new_coins == 3
        assert StudentCoinLedger.objects.filter(attempt=attempt2).count() == 1

        # While our terminated attempt has 0 coins
        assert StudentCoinLedger.objects.filter(attempt=self.attempt).count() == 0

    # Test 33: TAB_SWITCH event triggers immediate cancellation (Phase 3 policy)
    def test_33_tab_switch_event_triggers_termination_pending(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "TAB_SWITCH", "metadata": {"state": "hidden"}}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["status"] == "RECORDED"
        assert res.data["attempt_status"] == AttemptStatus.CANCELLED
        assert res.data["disqualified"] is True
        assert res.data["termination_pending"] is False
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert self.attempt.termination_pending is False

    # Test 34: WINDOW_FOCUS_LOST event triggers immediate cancellation (Phase 3 policy)
    def test_34_window_focus_lost_event_triggers_termination_pending(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_FOCUS_LOST", "metadata": {}}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["status"] == "RECORDED"
        assert res.data["attempt_status"] == AttemptStatus.CANCELLED
        assert res.data["disqualified"] is True
        assert res.data["termination_pending"] is False
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert self.attempt.termination_pending is False

    # Test 35: PAGE_VISIBILITY_CHANGE with state: hidden triggers termination pending
    def test_35_page_visibility_hidden_triggers_termination_pending(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "PAGE_VISIBILITY_CHANGE", "metadata": {"state": "hidden"}}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["status"] == "RECORDED"
        assert res.data["termination_pending"] is True
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True

    # Test 36: Focus loss event for already SUBMITTED attempt does NOT start termination
    def test_36_focus_loss_for_submitted_attempt_does_not_start_termination(self):
        self.attempt.status = AttemptStatus.SUBMITTED
        self.attempt.save(update_fields=['status'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_BLUR"}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is False
        assert self.attempt.termination_deadline is None

    # Test 37: Focus loss event for already CANCELLED attempt does NOT start termination
    def test_37_focus_loss_for_cancelled_attempt_does_not_start_termination(self):
        self.attempt.status = AttemptStatus.CANCELLED
        self.attempt.save(update_fields=['status'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_BLUR"}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is False
        assert self.attempt.termination_deadline is None

    # Test 38: Focus loss event for already EXPIRED attempt does NOT start termination
    def test_38_focus_loss_for_expired_attempt_does_not_start_termination(self):
        self.attempt.status = AttemptStatus.EXPIRED
        self.attempt.save(update_fields=['status'])

        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "WINDOW_BLUR"}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is False
        assert self.attempt.termination_deadline is None

    # Test 39: Admin session list and detail serializers expose authoritative termination fields
    def test_39_admin_session_list_and_detail_expose_authoritative_fields(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id), reason="WINDOW FOCUS LOST")

        # Admin session list endpoint
        url_list = f"/api/v1/admin/assessments/{self.published_assessment.id}/proctoring/sessions/"
        res_list = self.client_admin.get(url_list)
        assert res_list.status_code == status.HTTP_200_OK
        session_item = next(s for s in res_list.data["results"] if s["attempt_id"] == str(self.attempt.id))
        assert session_item["termination_pending"] is True
        assert session_item["termination_reason"] == "WINDOW FOCUS LOST"
        assert session_item["termination_deadline"] is not None
        assert session_item["termination_remaining_seconds"] is not None
        assert 115 <= session_item["termination_remaining_seconds"] <= 120
        assert session_item["is_disqualified"] is False

        # Admin session detail endpoint
        url_detail = f"/api/v1/admin/proctoring/sessions/{self.session.id}/"
        res_detail = self.client_admin.get(url_detail)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["termination_pending"] is True
        assert res_detail.data["termination_reason"] == "WINDOW FOCUS LOST"
        assert res_detail.data["termination_remaining_seconds"] is not None

    # Test 40: Proctor review verdict is persisted correctly
    def test_40_proctor_review_verdict_persisted_correctly(self):
        url = f"/api/v1/admin/proctoring/sessions/{self.session.id}/review/"
        res = self.client_admin.patch(url, {
            "decision": "REVIEWED_CLEAN",
            "notes": "Reviewed telemetry - accidental blur confirmed not cheating."
        }, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["decision"] == "REVIEWED_CLEAN"
        assert res.data["notes"] == "Reviewed telemetry - accidental blur confirmed not cheating."
        assert res.data["reviewed_by"] == self.admin.email

    # Test 41: Critical: "Not Disqualified / Clean" review verdict does NOT resurrect a terminal attempt
    def test_41_proctor_review_clean_does_not_resurrect_cancelled_attempt(self):
        # Force attempt into terminal cancelled & disqualified state
        self.attempt.status = AttemptStatus.CANCELLED
        self.attempt.is_disqualified = True
        self.attempt.disqualification_reason = "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
        self.attempt.termination_pending = False
        self.attempt.save(update_fields=['status', 'is_disqualified', 'disqualification_reason', 'termination_pending'])

        url = f"/api/v1/admin/proctoring/sessions/{self.session.id}/review/"
        res = self.client_admin.patch(url, {
            "decision": "REVIEWED_CLEAN",
            "notes": "Admin marked not disqualified for recordkeeping."
        }, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["decision"] == "REVIEWED_CLEAN"

        # Invariant: Attempt remains CANCELLED and is_disqualified remains True
        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert self.attempt.disqualification_reason == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    # Test 42: Screenshot telemetry is stored when browser-observable signal exists
    def test_42_screenshot_telemetry_is_stored_when_signal_exists(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {
            "event_type": "SCREENSHOT_ATTEMPT",
            "metadata": {
                "shortcut": "Cmd+Shift+4",
                "source": "KEYBOARD_TELEMETRY",
                "note": "Browser observable keyboard event"
            }
        }, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["status"] == "RECORDED"

        # Verify event was persisted in session
        ev = ProctoringEvent.objects.filter(session=self.session, event_type="SCREENSHOT_ATTEMPT").first()
        assert ev is not None
        assert ev.metadata.get("shortcut") == "Cmd+Shift+4"
        assert ev.metadata.get("source") == "KEYBOARD_TELEMETRY"

    # Test 43: Screenshot telemetry does NOT automatically trigger window termination
    def test_43_screenshot_telemetry_does_not_trigger_termination_pending(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {
            "event_type": "SCREENSHOT_ATTEMPT",
            "metadata": {"shortcut": "PrintScreen"}
        }, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED
        self.attempt.refresh_from_db()

        # Invariant: Screenshot telemetry does NOT start 2-minute termination countdown
        assert self.attempt.termination_pending is False
        assert self.attempt.termination_deadline is None
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    # Test 44: Unsupported native macOS screenshot actions are not falsely reported
    def test_44_unsupported_native_macos_shortcuts_not_falsely_reported(self):
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {
            "event_type": "NATIVE_OS_SCREENSHOT_FAKE",
            "metadata": {}
        }, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid client event type" in str(res.data)

    # Test 45: WebSocket termination event targets both attempt and assessment channels
    def test_45_websocket_termination_targets_correct_groups(self):
        dispatched_groups = []

        def mock_dispatch(group_name, event_data):
            dispatched_groups.append((group_name, event_data["event"]))

        original_dispatch = AttemptTerminationPolicyService._dispatch_websocket_event
        try:
            AttemptTerminationPolicyService._dispatch_websocket_event = mock_dispatch
            AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))

            expected_attempt_group = f"attempt_{self.attempt.id}"
            expected_proctor_group = f"proctor_assessment_{self.attempt.assessment_id}"

            assert (expected_attempt_group, "TERMINATION_PENDING") in dispatched_groups
            assert (expected_proctor_group, "TERMINATION_PENDING") in dispatched_groups
        finally:
            AttemptTerminationPolicyService._dispatch_websocket_event = original_dispatch

    # Test 46: Polling recovers authoritative state for student and proctor APIs
    def test_46_polling_recovers_authoritative_state(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))

        # Student polling endpoint
        student_url = f"/api/v1/student/attempts/{self.attempt.id}/"
        student_res = self.client_student.get(student_url)
        assert student_res.status_code == status.HTTP_200_OK
        assert student_res.data["data"]["termination_pending"] is True
        assert student_res.data["data"]["status"] == "IN_PROGRESS"

        # Proctor polling roster
        roster = ProctorTriageQueueService.get_triage_roster(str(self.published_assessment.id), self.proctor)
        item = next(r for r in roster if r["attempt_id"] == str(self.attempt.id))
        assert item["termination_pending"] is True
        assert item["termination_remaining_seconds"] is not None

        # Admin session polling endpoint
        admin_url = f"/api/v1/admin/proctoring/sessions/{self.session.id}/"
        admin_res = self.client_admin.get(admin_url)
        assert admin_res.status_code == status.HTTP_200_OK
        assert admin_res.data["termination_pending"] is True

    # Test 47: Focus restoration does NOT cancel pending termination
    def test_47_focus_restoration_does_not_cancel_termination(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))
        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True
        deadline_before = self.attempt.termination_deadline

        # Simulate client reporting focus or window re-entry event
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        res = self.client_student.post(url, {"event_type": "PAGE_VISIBILITY_CHANGE", "metadata": {"state": "visible"}}, format="json")
        assert res.status_code == status.HTTP_202_ACCEPTED

        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True
        assert self.attempt.termination_deadline == deadline_before

    # Test 48: Student cannot dismiss or override termination state
    def test_48_student_cannot_dismiss_or_override_termination(self):
        AttemptTerminationPolicyService.trigger_termination_pending(str(self.attempt.id))

        # Student attempts to hit proctor cancel-termination endpoint
        url = f"/api/v1/invigilation/attempts/{self.attempt.id}/cancel-termination/"
        res = self.client_student.post(url, {"reason": "Student self-rescue"}, format="json")
        assert res.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

        self.attempt.refresh_from_db()
        assert self.attempt.termination_pending is True

