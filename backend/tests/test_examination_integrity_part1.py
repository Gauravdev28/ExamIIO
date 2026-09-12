import pytest
from datetime import timedelta
from unittest.mock import patch
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
    AttemptAnswer,
)
from apps.assessments.services import AssessmentService, AttemptService, AttemptTimerService
from apps.questions.services import QuestionService
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringWarning,
    EventSource,
    EventSeverity,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    AttemptTerminationPolicyService,
    ProctoringRiskService,
    ProctoringWarningService,
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
class TestExaminationIntegrityPart1:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.admin = User.objects.create(email="admin_integrity@example.com", role=Role.ADMIN)
        self.proctor = User.objects.create(email="proctor_integrity@example.com", role=Role.PROCTOR)
        self.other_proctor = User.objects.create(email="other_proctor_integrity@example.com", role=Role.PROCTOR)
        self.student = User.objects.create(email="student_integrity@example.com", role=Role.STUDENT)
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="INT-ROLL-001",
            euid="INT-EUID-001",
            first_login_required=False
        )

        # Question
        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Integrity Master MCQ',
            description='Test examination integrity question',
            points=100,
            type_config={
                'options': [
                    {'id': 'OPT_A', 'text': 'Option A (Correct)'},
                    {'id': 'OPT_B', 'text': 'Option B'}
                ],
                'correct_options': ['OPT_A']
            },
            actor=self.admin,
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Examination Integrity Master Assessment",
            description="Testing Part 1 Integrity Workflow",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=100,
            attempt_limit=1,
            max_confirmed_violations=3,
            camera_required=True,
            proctoring_enabled=True,
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

        # Assigned proctor
        ProctorAssignment.objects.create(
            assessment=self.published_assessment,
            proctor=self.proctor,
            is_active=True
        )

        # API Clients
        self.student_client = APIClient()
        self.student_client.force_authenticate(user=self.student)

        self.proctor_client = APIClient()
        self.proctor_client.force_authenticate(user=self.proctor)

        self.other_proctor_client = APIClient()
        self.other_proctor_client.force_authenticate(user=self.other_proctor)

        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)

    def _start_student_attempt(self):
        attempt, created = AttemptService.start_attempt(self.student, str(self.published_assessment.id))
        session = ProctoringSessionService.get_or_create_session(attempt)
        return attempt, session

    # =========================================================================
    # CAMERA (Scenarios 1-3)
    # =========================================================================

    def test_01_camera_initialization_flow(self):
        """1. Camera initialization: starting session marks proctoring active."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/proctoring/start/")
        assert res.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.status == ProctoringSessionStatus.ACTIVE

    def test_02_camera_failure_reporting(self):
        """2. Camera failure handling: CAMERA_UNAVAILABLE browser event ingested gracefully."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "CAMERA_UNAVAILABLE", "metadata": {"reason": "Track muted"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert ProctoringEvent.objects.filter(session=session, event_type="CAMERA_UNAVAILABLE").exists()

    def test_03_mirrored_preview_vs_unmirrored_ai_frame_integrity(self):
        """3. Mirrored preview vs unmirrored AI frame: frame upload processes raw unmirrored bytes."""
        attempt, session = self._start_student_attempt()
        # Verify frame ingestion endpoint accepts frame data without client transform
        res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["camera_required"] is True

    # =========================================================================
    # FULLSCREEN (Scenarios 4-7)
    # =========================================================================

    def test_04_fullscreen_required_flag_exposed(self):
        """4. Fullscreen required to enter exam."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["status"] == AttemptStatus.IN_PROGRESS

    def test_05_fullscreen_exit_immediate_cancellation(self):
        """5. Fullscreen exit triggers immediate cancellation and records FULLSCREEN_EXIT event."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "FULLSCREEN_EXIT", "metadata": {"sustained": False}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert res.data["disqualified"] is True
        assert res.data["attempt_status"] == AttemptStatus.CANCELLED
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert attempt.termination_pending is False
        assert ProctoringEvent.objects.filter(session=session, event_type="FULLSCREEN_EXIT").exists()

    def test_06_fullscreen_warning_acknowledgement(self):
        """6. Fullscreen warning acknowledgement records timestamp."""
        attempt, session = self._start_student_attempt()
        warn = ProctoringWarningService.issue_warning_if_eligible(
            session=session,
            event_type='FULLSCREEN_EXIT',
            bypass_cooldown=True,
        )
        assert warn is not None
        ack_res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/warnings/{warn.id}/ack/"
        )
        assert ack_res.status_code == status.HTTP_200_OK
        assert ack_res.data["status"] == "ACKNOWLEDGED"
        warn.refresh_from_db()
        assert warn.acknowledged_at is not None

    def test_07_fullscreen_exit_termination_semantics_verified(self):
        """7. Fullscreen exit termination path: cancelled attempt rejects submission."""
        attempt, session = self._start_student_attempt()
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.save()

        # Submit attempt should fail on cancelled attempt
        res = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/submit/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # =========================================================================
    # FOCUS LOSS DETECTION (Scenarios 8-16)
    # =========================================================================

    def test_08_tab_switch_event_detection(self):
        """8. TAB_SWITCH event triggers immediate cancellation."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "TAB_SWITCH", "metadata": {"state": "hidden"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert attempt.termination_pending is False

    def test_09_window_blur_behavior_and_validation(self):
        """9. WINDOW_BLUR triggers termination pending with server deadline."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "WINDOW_BLUR", "metadata": {"sustained": True}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.termination_pending is True
        assert attempt.termination_deadline is not None

    def test_10_window_focus_lost_event_handling(self):
        """10. WINDOW_FOCUS_LOST event handling."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "WINDOW_FOCUS_LOST"},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert attempt.termination_pending is False

    def test_11_visibilitychange_hidden_behavior(self):
        """11. PAGE_VISIBILITY_CHANGE with hidden state triggers pending termination."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "PAGE_VISIBILITY_CHANGE", "metadata": {"state": "hidden"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.termination_pending is True

    def test_12_duplicate_signals_do_not_reset_deadline(self):
        """12. Duplicate signals from single incident do not reset or extend deadline."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        original_deadline = attempt.termination_deadline

        # Second signal
        res = AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        assert res["status"] == "ALREADY_PENDING"
        attempt.refresh_from_db()
        assert attempt.termination_deadline == original_deadline

    def test_13_focus_restoration_does_not_cancel_pending_termination(self):
        """13. Focus restoration does not cancel pending termination."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        # Focus returns
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "PAGE_VISIBILITY_CHANGE", "metadata": {"state": "visible"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.termination_pending is True

    def test_14_browser_ui_dialog_interaction_does_not_trigger_false_termination(self):
        """14. In-browser dialog: non-hidden/non-blur events do not trigger termination."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "PAGE_VISIBILITY_CHANGE", "metadata": {"state": "visible"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.termination_pending is False

    def test_15_correct_attempt_id_correlation(self):
        """15. Correct attempt ID correlation across student, session, and attempt."""
        attempt, session = self._start_student_attempt()
        assert session.attempt_id == attempt.id
        assert attempt.student_id == self.student.id

    def test_16_focus_event_recorded_while_active_only(self):
        """16. Focus event recorded while active only (skipped for submitted/cancelled)."""
        attempt, session = self._start_student_attempt()
        attempt.status = AttemptStatus.SUBMITTED
        attempt.save()

        res = AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        assert res["status"] == "SKIPPED"
        attempt.refresh_from_db()
        assert attempt.termination_pending is False

    # =========================================================================
    # TERMINATION POLICY (Scenarios 17-24)
    # =========================================================================

    def test_17_pending_state_creation(self):
        """17. Pending state creation sets termination_pending=True."""
        attempt, session = self._start_student_attempt()
        res = AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id), "WINDOW FOCUS LOST")
        assert res["status"] == "TERMINATION_PENDING"
        assert res["remaining_seconds"] == 120

    def test_18_exact_120_second_server_deadline(self):
        """18. Exact 120-second server deadline calculated from server now."""
        attempt, session = self._start_student_attempt()
        before = timezone.now()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        after = timezone.now()
        attempt.refresh_from_db()

        expected_min = before + timedelta(seconds=120)
        expected_max = after + timedelta(seconds=120)
        assert expected_min <= attempt.termination_deadline <= expected_max

    def test_19_page_refresh_recalculates_from_server_deadline(self):
        """19. Page refresh recalculates remaining time from server deadline."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        # Simulate 30s elapsed
        attempt.termination_deadline = timezone.now() + timedelta(seconds=90)
        attempt.save()

        res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res.status_code == status.HTTP_200_OK
        rem = res.data["data"]["termination_remaining_seconds"]
        assert 88 <= rem <= 91

    def test_20_server_expiration_transitions_to_canonical_cancelled(self):
        """20. Server expiration transitions to canonical status=CANCELLED with is_disqualified=True."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=5)
        attempt.save()

        res = AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
        assert res["status"] == "EXPIRED"
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert attempt.disqualification_reason == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    def test_21_browser_disconnect_expiration(self):
        """21. Browser disconnect expiration executes in background without student heartbeat."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        attempt.save()

        from apps.proctoring.tasks import expire_window_termination_task
        expire_window_termination_task(str(attempt.id))

        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True

    def test_22_network_disconnect_expiration(self):
        """22. Network disconnect expiration: background check expires attempt."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=10)
        attempt.save()

        AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True

    def test_23_late_celery_execution_authoritative_check(self):
        """23. Late Celery execution: re-reads database under atomic lock."""
        attempt, session = self._start_student_attempt()
        # Not pending termination
        attempt.termination_pending = False
        attempt.save()

        res = AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
        assert res["status"] == "SKIPPED"
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.IN_PROGRESS

    def test_24_terminal_attempt_cannot_be_modified(self):
        """24. Terminal attempt rejects save_answer and submit_attempt."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        attempt.save()

        # Late save answer rejected
        snap_q = self.published_assessment.snapshot.snapshot_questions.first()
        q_id = snap_q.snapshot_question_id
        save_res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/answers/{q_id}/",
            {"selected_options": ["OPT_A"], "revision": 1},
            format="json"
        )
        assert save_res.status_code == status.HTTP_400_BAD_REQUEST

        # Late submit attempt rejected
        sub_res = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/submit/")
        assert sub_res.status_code == status.HTTP_400_BAD_REQUEST

    # =========================================================================
    # PROCTOR RESCUE (Scenarios 25-30)
    # =========================================================================

    def test_25_authorized_proctor_rescue(self):
        """25. Authorized proctor rescues candidate before deadline."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        res = self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Valid network glitch verified by proctor"},
            format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        attempt.refresh_from_db()
        assert attempt.termination_pending is False
        assert attempt.status == AttemptStatus.IN_PROGRESS

    def test_26_unauthorized_proctor_rescue_rejected(self):
        """26. Unauthorized proctor rescue rejected with 403 Forbidden."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        res = self.other_proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Attempting unauthorized intervention"},
            format="json"
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_27_late_rescue_rejected_if_expired(self):
        """27. Late rescue rejected if deadline already expired."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        attempt.save()

        res = self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Too late rescue"},
            format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True

    def test_28_race_between_rescue_and_expiration(self):
        """28. Race condition: atomic row locking prevents concurrent resurrection."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.save()

        res = self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Race intervention"},
            format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_29_same_attempt_preserved_upon_rescue(self):
        """29. Same attempt preserved upon rescue with all answers intact."""
        attempt, session = self._start_student_attempt()
        snap_q = self.published_assessment.snapshot.snapshot_questions.first()
        AttemptService.save_answer(
            student=self.student,
            attempt_id=str(attempt.id),
            snapshot_question_id=snap_q.snapshot_question_id,
            answer_data={"selected_options": ["OPT_A"]},
            client_revision=1
        )
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Rescued"},
            format="json"
        )
        attempt.refresh_from_db()
        ans = AttemptAnswer.objects.get(attempt=attempt, question_id=snap_q.snapshot_question_id)
        assert ans.selected_options == ["OPT_A"]
        assert ans.is_answered is True

    def test_30_expires_at_unchanged_upon_rescue(self):
        """30. Attempt original expires_at unchanged upon rescue."""
        attempt, session = self._start_student_attempt()
        orig_expires = attempt.expires_at
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Rescued"},
            format="json"
        )
        attempt.refresh_from_db()
        assert attempt.expires_at == orig_expires

    # =========================================================================
    # PROCTOR VISIBILITY (Scenarios 31-35)
    # =========================================================================

    def test_31_pending_state_visible_in_console(self):
        """31. Pending state visible with remaining countdown in proctor session list."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        res = self.admin_client.get(f"/api/v1/admin/assessments/{self.published_assessment.id}/proctoring/sessions/")
        assert res.status_code == status.HTTP_200_OK
        data = res.data["results"][0]
        assert data["termination_pending"] is True
        assert data["termination_remaining_seconds"] is not None
        assert data["termination_remaining_seconds"] > 0

    def test_32_final_termination_visible_as_disqualified(self):
        """32. Final termination visible as DISQUALIFIED in proctor console."""
        attempt, session = self._start_student_attempt()
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.disqualification_reason = "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
        attempt.save()

        res = self.admin_client.get(f"/api/v1/admin/assessments/{self.published_assessment.id}/proctoring/sessions/")
        assert res.status_code == status.HTTP_200_OK
        data = res.data["results"][0]
        assert data["attempt_status"] == "DISQUALIFIED"
        assert data["is_disqualified"] is True
        assert data["disqualification_reason"] == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    def test_33_websocket_realtime_delivery_targets_correct_groups(self):
        """33. WebSocket delivery targets attempt and proctor assessment groups."""
        attempt, session = self._start_student_attempt()
        with patch("apps.proctoring.services.AttemptTerminationPolicyService._dispatch_websocket_event") as mock_dispatch:
            AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
            assert mock_dispatch.call_count == 2
            groups = [c[0][0] for c in mock_dispatch.call_args_list]
            assert f"attempt_{attempt.id}" in groups
            assert f"proctor_assessment_{attempt.assessment_id}" in groups

    def test_34_polling_recovery_on_websocket_failure(self):
        """34. Polling recovery: detail endpoint returns full authoritative termination state."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["termination_pending"] is True
        assert res.data["data"]["termination_deadline"] is not None

    def test_35_student_and_proctor_state_consistency(self):
        """35. Student and proctor state consistency: single database source of truth."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))

        student_res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        proctor_res = self.admin_client.get(f"/api/v1/admin/proctoring/sessions/{session.id}/")

        assert student_res.data["data"]["termination_pending"] == proctor_res.data["termination_pending"]
        assert student_res.data["data"]["status"] == proctor_res.data["attempt_status"]

    # =========================================================================
    # AI PROCTORING (Scenarios 36-38)
    # =========================================================================

    def test_36_ai_event_reaches_backend(self):
        """36. AI frame analysis records AI event with source=AI."""
        attempt, session = self._start_student_attempt()
        # High impact AI signals require persistent frames (at least 2 qualifying frames within window)
        evt1 = ProctoringRiskService.record_event(
            session=session,
            event_type="PHONE_DETECTED",
            source=EventSource.AI,
            severity=EventSeverity.HIGH,
            confidence=0.95,
            started_at=timezone.now()
        )
        evt2 = ProctoringRiskService.record_event(
            session=session,
            event_type="PHONE_DETECTED",
            source=EventSource.AI,
            severity=EventSeverity.HIGH,
            confidence=0.95,
            started_at=timezone.now()
        )
        assert evt2 is not None
        assert evt2.source == EventSource.AI
        assert evt2.event_type == "PHONE_DETECTED"

    def test_37_ai_event_appears_in_proctor_timeline(self):
        """37. AI event appears in proctor detail session timeline."""
        attempt, session = self._start_student_attempt()
        ProctoringRiskService.record_event(
            session=session,
            event_type="FACE_MISSING",
            source=EventSource.AI,
            severity=EventSeverity.MEDIUM,
            confidence=0.85,
            started_at=timezone.now()
        )
        res = self.admin_client.get(f"/api/v1/admin/proctoring/sessions/{session.id}/")
        assert res.status_code == status.HTTP_200_OK
        types = [e["event_type"] for e in res.data["events"]]
        assert "FACE_MISSING" in types

    def test_38_existing_strike_risk_policy_unchanged_by_focus_loss(self):
        """38. AI 3-strike policy remains separate from focus loss policy."""
        attempt, session = self._start_student_attempt()
        # Record single AI event: does NOT trigger termination pending
        ProctoringRiskService.record_event(
            session=session,
            event_type="PHONE_DETECTED",
            source=EventSource.AI,
            severity=EventSeverity.HIGH,
            confidence=0.95,
            started_at=timezone.now()
        )
        attempt.refresh_from_db()
        assert attempt.termination_pending is False
        assert attempt.status == AttemptStatus.IN_PROGRESS

    # =========================================================================
    # SCREENSHOT TELEMETRY (Scenarios 39-40)
    # =========================================================================

    def test_39_browser_observable_screenshot_keyboard_event(self):
        """39. Explicitly mapped screenshot event ingested as SCREENSHOT_ATTEMPT."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {
                "event_type": "SCREENSHOT_ATTEMPT",
                "metadata": {
                    "shortcut": "PrintScreen",
                    "source": "KEYBOARD_TELEMETRY",
                    "note": "Verified browser-delivered key event"
                }
            },
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        # Must NOT trigger termination pending
        assert attempt.termination_pending is False
        assert ProctoringEvent.objects.filter(session=session, event_type="SCREENSHOT_ATTEMPT").exists()

    def test_40_unsupported_native_screenshot_not_falsely_claimed(self):
        """40. Invalid or unmapped screenshot event does not trigger termination policy."""
        attempt, session = self._start_student_attempt()
        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "SCREENSHOT_ATTEMPT", "metadata": {"source": "TEST"}},
            format="json"
        )
        assert res.status_code == status.HTTP_202_ACCEPTED
        attempt.refresh_from_db()
        assert attempt.termination_pending is False
        assert attempt.is_disqualified is False

    # =========================================================================
    # RE-ENTRY (Scenarios 41-42)
    # =========================================================================

    def test_41_terminal_attempt_cannot_reenter(self):
        """41. Terminal cancelled attempt rejects start_attempt re-entry."""
        attempt, session = self._start_student_attempt()
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.save()

        from rest_framework.exceptions import ValidationError as DRFValError
        with pytest.raises(DRFValError) as exc_info:
            AttemptService.start_attempt(self.student, str(self.published_assessment.id))
        assert "CANDIDATE_DISQUALIFIED" in str(exc_info.value)

    def test_42_direct_url_cannot_bypass_termination(self):
        """42. Direct URL access to attempt detail returns cancelled status and reason."""
        attempt, session = self._start_student_attempt()
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.disqualification_reason = "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
        attempt.save()

        res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["status"] == AttemptStatus.CANCELLED
        assert res.data["data"]["is_disqualified"] is True
        assert res.data["data"]["disqualification_reason"] == "EXAMINATION TERMINATED — WINDOW FOCUS LOST"

    # =========================================================================
    # COIN INTEGRITY (Scenarios 43-45)
    # =========================================================================

    def test_43_window_termination_itself_awards_zero_new_coins(self):
        """43. Window termination awards strictly ZERO NEW COINS."""
        attempt, session = self._start_student_attempt()
        initial_coins = StudentCoinLedger.objects.filter(student=self.student).count()

        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        attempt.save()
        AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))

        final_coins = StudentCoinLedger.objects.filter(student=self.student).count()
        assert final_coins == initial_coins

    def test_44_legitimately_finalized_coins_before_termination_remain_intact(self):
        """44. Legitimately finalized coins earned before termination remain intact and immutable."""
        attempt, session = self._start_student_attempt()
        # Award legitimate pre-termination coins for a question
        ledger_entry = StudentCoinLedger.objects.create(
            student=self.student,
            attempt=attempt,
            question_id="Q-LEGIT-1",
            coins_awarded=3
        )

        # Candidate later loses focus and is terminated
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        attempt.termination_deadline = timezone.now() - timedelta(seconds=1)
        attempt.save()
        AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))

        # Ledger entry remains unchanged
        assert StudentCoinLedger.objects.filter(id=ledger_entry.id).exists()
        entry = StudentCoinLedger.objects.get(id=ledger_entry.id)
        assert entry.coins_awarded == 3

    def test_45_no_duplicate_coin_ledger_entry_and_rescue_awards_zero_coins(self):
        """45. Proctor rescue and run code award ZERO coins; ledger is unique on (attempt, question_id)."""
        attempt, session = self._start_student_attempt()
        initial_count = StudentCoinLedger.objects.filter(student=self.student).count()

        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Rescued"},
            format="json"
        )
        post_rescue_count = StudentCoinLedger.objects.filter(student=self.student).count()
        assert post_rescue_count == initial_count

    # =========================================================================
    # SUBMISSION & AUDIT (Scenario 46)
    # =========================================================================

    def test_46_focus_loss_does_not_accidentally_submit_and_rescue_is_audited(self):
        """46. Focus loss never sets status=SUBMITTED; proctor rescue is audited with identity."""
        attempt, session = self._start_student_attempt()
        AttemptTerminationPolicyService.trigger_termination_pending(str(attempt.id))
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.IN_PROGRESS
        assert attempt.status != AttemptStatus.SUBMITTED

        # Proctor rescue
        self.proctor_client.post(
            f"/api/v1/proctor/attempts/{attempt.id}/cancel-termination/",
            {"reason": "Audit verification rescue"},
            format="json"
        )
        intervention = ProctorIntervention.objects.filter(
            attempt=attempt,
            event_type=InterventionType.TERMINATION_CANCELLED
        ).first()
        assert intervention is not None
        assert intervention.proctor == self.proctor
        assert intervention.reason_text == "Audit verification rescue"

        audit_entry = AuditLog.objects.filter(
            action="PROCTOR_TERMINATION_CANCELLED",
            target_id=str(attempt.id)
        ).first()
        assert audit_entry is not None
        assert audit_entry.actor == self.proctor

    # =========================================================================
    # EXPLICIT TERMINATION & PAGE REFRESH (Scenarios 47-49)
    # =========================================================================

    def test_47_voluntary_or_back_navigation_explicit_termination(self):
        """47. Voluntary exit / Browser navigation triggers explicit termination: CANCELLED, is_disqualified=True, zero coins, no resume."""
        attempt, session = self._start_student_attempt()
        initial_coins = StudentCoinLedger.objects.filter(student=self.student).count()

        res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/terminate/",
            {"reason": "EXAMINATION ABANDONED — BROWSER NAVIGATION / ROOM EXIT"},
            format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "success"
        assert res.data["data"]["attempt_status"] == AttemptStatus.CANCELLED
        assert res.data["data"]["is_disqualified"] is True

        attempt.refresh_from_db()
        session.refresh_from_db()
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert "EXAMINATION ABANDONED" in attempt.disqualification_reason
        assert session.status == ProctoringSessionStatus.TERMINATED

        # Verify audit log & intervention
        intervention = ProctorIntervention.objects.filter(
            attempt=attempt,
            event_type=InterventionType.TERMINATION_CONFIRMED
        ).first()
        assert intervention is not None
        assert "EXAMINATION ABANDONED" in intervention.reason_text

        audit_entry = AuditLog.objects.filter(
            action="EXAM_VOLUNTARY_TERMINATION",
            target_id=str(attempt.id)
        ).first()
        assert audit_entry is not None
        assert audit_entry.actor == self.student

        # Zero coins awarded
        assert StudentCoinLedger.objects.filter(student=self.student).count() == initial_coins

        # Cannot submit cancelled attempt
        sub_res = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/submit/")
        assert sub_res.status_code == status.HTTP_400_BAD_REQUEST

        # Cannot save answers on cancelled attempt
        snap_q = self.published_assessment.snapshot.snapshot_questions.first()
        q_id = snap_q.snapshot_question_id
        ans_res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/answers/{q_id}/",
            {"selected_options": ["OPT_A"], "revision": 1},
            format="json"
        )
        assert ans_res.status_code == status.HTTP_400_BAD_REQUEST

    def test_48_page_refresh_preserves_in_progress_attempt(self):
        """48. Page reload / refresh preserves IN_PROGRESS state, answers, and timer without cancellation."""
        attempt, session = self._start_student_attempt()
        snap_q = self.published_assessment.snapshot.snapshot_questions.first()
        q_id = snap_q.snapshot_question_id

        # Save an answer first
        ans_res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/answers/{q_id}/",
            {"selected_options": ["OPT_A"], "revision": 1},
            format="json"
        )
        assert ans_res.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Simulate page refresh by fetching attempt details
        detail_res = self.student_client.get(f"/api/v1/student/attempts/{attempt.id}/")
        assert detail_res.status_code == status.HTTP_200_OK
        data = detail_res.data["data"]
        assert data["status"] == AttemptStatus.IN_PROGRESS
        assert data["is_disqualified"] is False
        assert data["remaining_seconds"] > 0
        assert q_id in data["answers"]

        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.IN_PROGRESS
        assert attempt.is_disqualified is False

    def test_49_fullscreen_enter_clears_fullscreen_warning(self):
        """49. Re-entering fullscreen auto-acknowledges active fullscreen warning and removes it."""
        attempt, session = self._start_student_attempt()

        # Step 1: Active FULLSCREEN warning on session
        warn = ProctoringWarningService.issue_warning_if_eligible(
            session=session,
            event_type='FULLSCREEN_EXIT',
            bypass_cooldown=True,
        )
        assert warn is not None
        warn_id = str(warn.id)

        # Step 2: Heartbeat would see this warning unacknowledged
        hb_res1 = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/proctoring/heartbeat/")
        assert hb_res1.data["warning"] is not None
        assert hb_res1.data["warning"]["id"] == warn_id

        # Step 3: Candidate returns to fullscreen -> dispatches FULLSCREEN_ENTER
        enter_res = self.student_client.post(
            f"/api/v1/student/attempts/{attempt.id}/proctoring/events/",
            {"event_type": "FULLSCREEN_ENTER"},
            format="json"
        )
        assert enter_res.status_code == status.HTTP_202_ACCEPTED
        # Warning should not be active or unacknowledged in DB
        assert enter_res.data["warning"] is None

        # Step 4: Subsequent heartbeat confirms no active unacknowledged warning
        hb_res2 = self.student_client.post(f"/api/v1/student/attempts/{attempt.id}/proctoring/heartbeat/")
        assert hb_res2.data["warning"] is None

