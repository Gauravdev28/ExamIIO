import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Role, StudentProfile
from apps.accounts.services import AuditService
from apps.questions.services import QuestionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringWarning,
    RiskBand,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    ProctoringRiskService,
)
from apps.proctoring.serializers import (
    AdminProctoringSessionListSerializer,
    AdminProctoringSessionDetailSerializer,
)


@pytest.mark.django_db
class TestProctoringAuditFixes:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin_proct_audit@example.com",
            password="AdminPassword123!",
            role=Role.ADMIN,
        )
        self.student = User.objects.create_user(
            email="student_proct_audit@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT,
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="CS2026-AUDIT",
            euid="EUID-AUDIT-001",
        )
        self.other_student = User.objects.create_user(
            email="other_proct_audit@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=self.other_student,
            roll_number="CS2026-OTHER",
            euid="EUID-AUDIT-002",
        )

        # Question and published assessment
        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Audit Question',
            description='Test description',
            points=100,
            type_config={'options': [{'id': 'A', 'text': 'Option A'}, {'id': 'B', 'text': 'Option B'}], 'correct_options': ['A']},
            actor=self.admin,
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Proctoring Audit Assessment",
            description="Testing proctoring audit fixes",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=100,
            attempt_limit=1,
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=100,
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin,
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.other_student,
            assigned_by=self.admin,
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.published_assessment.id),
            actor=self.student,
        )
        self.session = ProctoringSessionService.start_session(self.attempt)

    def test_single_window_blur_does_not_increment_confirmed_violations_or_disqualify(self):
        """P2: WINDOW_BLUR is a supporting signal and does not increment confirmed violation count or disqualify."""
        event = ProctoringRiskService.record_event(
            session=self.session,
            event_type='WINDOW_BLUR',
            bypass_cooldown=True,
        )
        assert event is not None
        assert event.event_type == 'WINDOW_BLUR'

        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        # No disciplinary warnings issued for blur alone
        assert self.session.total_warnings_count == 0
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    def test_ingesting_three_confirmed_violations_automatically_terminates_and_disqualifies(self):
        """P2/P3: Ingesting 3 confirmed violations (TAB_SWITCH / FULLSCREEN_EXIT) terminates session and cancels attempt."""
        # Violation 1: Standard warning
        ev1 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
        )
        assert ev1 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.total_warnings_count == 1
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

        # Violation 2: Final warning
        ev2 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='FULLSCREEN_EXIT',
            bypass_cooldown=True,
        )
        assert ev2 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.total_warnings_count == 2
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

        # Violation 3: Immediate disqualification & session termination
        ev3 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
        )
        assert ev3 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        assert self.session.status == ProctoringSessionStatus.TERMINATED
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.submitted_at is not None

        # Check metadata on ev3
        ev3.refresh_from_db()
        assert ev3.metadata.get('disqualified') is True
        assert 'threshold exceeded' in ev3.metadata.get('disqualified_reason', '')

    def test_disqualified_attempt_rejects_answer_saving(self):
        """P3: Disqualified attempt rejects further answer persistence with HTTP 400."""
        # Force disqualify
        ProctoringRiskService._disqualify_candidate(self.session, None, 3)

        self.attempt.refresh_from_db()
        assert self.attempt.status == AttemptStatus.CANCELLED

        snapshot_q = self.attempt.assessment_snapshot.snapshot_questions.first()
        with pytest.raises(DRFValidationError) as exc:
            AttemptService.save_answer(
                student=self.student,
                attempt_id=str(self.attempt.id),
                snapshot_question_id=snapshot_q.snapshot_question_id,
                answer_data={"selected_options": ["A"]},
            )
        assert "Cannot save answer to attempt in CANCELLED status" in str(exc.value)

    def test_disqualified_attempt_cannot_be_submitted(self):
        """P4: Disqualified attempt cannot be submitted."""
        ProctoringRiskService._disqualify_candidate(self.session, None, 3)
        self.attempt.refresh_from_db()

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.submit_attempt(
                student=self.student,
                attempt_id=str(self.attempt.id),
            )
        assert "Cannot submit a cancelled or disqualified" in str(exc.value)

    def test_disqualified_attempt_cannot_be_resumed(self):
        """P4: Disqualified attempt cannot be resumed or retaken by start_attempt."""
        ProctoringRiskService._disqualify_candidate(self.session, None, 3)
        self.attempt.refresh_from_db()

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.start_attempt(
                student=self.student,
                assessment_id=str(self.published_assessment.id),
                actor=self.student,
            )
        assert "CANDIDATE_DISQUALIFIED" in str(exc.value)

    def test_student_cannot_resume_or_submit_another_student_attempt_idor(self):
        """P4 & Security: Student B cannot submit or save answers to Student A's attempt."""
        snapshot_q = self.attempt.assessment_snapshot.snapshot_questions.first()

        with pytest.raises(PermissionDenied):
            AttemptService.save_answer(
                student=self.other_student,
                attempt_id=str(self.attempt.id),
                snapshot_question_id=snapshot_q.snapshot_question_id,
                answer_data={"selected_options": ["A"]},
            )

        with pytest.raises(PermissionDenied):
            AttemptService.submit_attempt(
                student=self.other_student,
                attempt_id=str(self.attempt.id),
            )

    def test_admin_proctoring_session_list_serializer_includes_candidate_metadata_and_status(self):
        """P5: AdminProctoringSessionListSerializer returns enriched candidate details, attempt status, and latest violation."""
        # Record a TAB_SWITCH event
        ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
        )

        serializer = AdminProctoringSessionListSerializer(self.session)
        data = serializer.data

        assert data['student']['email'] == self.student.email
        assert data['student']['euid'] == "EUID-AUDIT-001"
        assert data['student']['roll_number'] == "CS2026-AUDIT"
        assert data['attempt_status'] == 'IN_PROGRESS'
        assert data['latest_violation'] is not None

        # Now disqualify and verify attempt_status transitions to DISQUALIFIED
        ProctoringRiskService._disqualify_candidate(self.session, None, 3)
        self.session.refresh_from_db()
        data_disq = AdminProctoringSessionListSerializer(self.session).data
        assert data_disq['attempt_status'] == 'DISQUALIFIED'

    def test_student_proctoring_event_ingestion_api_returns_disqualified_flag(self):
        """P2/P3 API: Telemetry ingestion endpoint immediately signals disqualification and cancellation on security violations."""
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"

        # Phase 3 Primary Policy: TAB_SWITCH triggers immediate disqualification and CANCELLED (Zero grace period)
        res1 = self.client.post(url, data={"event_type": "TAB_SWITCH", "metadata": {"bypass_cooldown": True}}, format="json")
        assert res1.status_code == status.HTTP_202_ACCEPTED
        assert res1.data['disqualified'] is True
        assert res1.data['attempt_status'] == 'CANCELLED'
        assert res1.data['termination_pending'] is False
        assert 'TAB SWITCH' in res1.data['disqualified_reason']

    def test_phone_and_multiple_faces_trigger_strong_strikes_and_disqualification(self):
        """P5: PHONE_DETECTED and MULTIPLE_FACES are strong violations that count towards disqualification."""
        # Signal 1: Phone detected (bypass persistence for direct service unit test)
        ev1 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='PHONE_DETECTED',
            confidence=0.95,
            bypass_cooldown=True,
        )
        assert ev1 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

        # Signal 2: Multiple faces detected
        ev2 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='MULTIPLE_FACES',
            confidence=0.90,
            bypass_cooldown=True,
        )
        assert ev2 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

        # Signal 3: Tab switch -> Reaches threshold 3 -> Disqualified!
        ev3 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
        )
        assert ev3 is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        assert self.session.status == ProctoringSessionStatus.TERMINATED
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert "threshold exceeded" in self.attempt.disqualification_reason
        assert self.attempt.disqualified_at is not None

    def test_supporting_signals_never_cause_strikes_or_disqualification(self):
        """P5: Supporting signals (WINDOW_BLUR, GAZE_DEVIATION, HEAD_TURN, FACE_MISSING) never trigger strikes or disqualification."""
        supporting_events = [
            'WINDOW_BLUR',
            'GAZE_DEVIATION',
            'HEAD_TURN_LEFT',
            'HEAD_TURN_RIGHT',
            'FACE_MISSING',
            'WINDOW_BLUR',
        ]
        for evt in supporting_events:
            ev = ProctoringRiskService.record_event(
                session=self.session,
                event_type=evt,
                bypass_cooldown=True,
            )
            assert ev is not None

        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        # Attempt must remain actively IN_PROGRESS and NOT disqualified
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS
        assert self.attempt.is_disqualified is False
        assert self.attempt.disqualified_at is None

    def test_custom_max_confirmed_violations_threshold_honored(self):
        """P5: Assessment with max_confirmed_violations=4 requires 4 strong signals before disqualifying."""
        self.published_assessment.max_confirmed_violations = 4
        self.published_assessment.save(update_fields=['max_confirmed_violations'])

        # Violations 1, 2, 3
        for _ in range(3):
            ProctoringRiskService.record_event(
                session=self.session,
                event_type='TAB_SWITCH',
                bypass_cooldown=True,
            )
            self.attempt.refresh_from_db()
            assert self.attempt.status == AttemptStatus.IN_PROGRESS
            assert self.attempt.is_disqualified is False

        # 4th Violation -> Disqualifies
        ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
        )
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        assert self.session.status == ProctoringSessionStatus.TERMINATED
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert "(4/4)" in self.attempt.disqualification_reason

    def test_objective_4_raw_vs_confirmed_detection(self):
        """
        Objective 4:
        raw PHONE_DETECTED -> no strike
        unconfirmed MULTIPLE_FACES -> no strike
        supporting FACE_NOT_DETECTED -> no strike
        supporting WINDOW_BLUR -> no strike
        confirmed PHONE_DETECTED -> one strong strike
        confirmed MULTIPLE_FACES -> one strong strike
        """
        # 1. raw PHONE_DETECTED -> no strike
        ev_raw_phone = ProctoringRiskService.record_event(
            session=self.session,
            event_type='PHONE_DETECTED',
            bypass_cooldown=True,
            metadata={'raw': True}
        )
        assert ev_raw_phone is not None
        assert ev_raw_phone.is_confirmed is False
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 0
        assert self.session.status == ProctoringSessionStatus.ACTIVE

        # 2. unconfirmed MULTIPLE_FACES -> no strike
        ev_unconfirmed_faces = ProctoringRiskService.record_event(
            session=self.session,
            event_type='MULTIPLE_FACES',
            bypass_cooldown=True,
            is_confirmed=False
        )
        assert ev_unconfirmed_faces is not None
        assert ev_unconfirmed_faces.is_confirmed is False
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 0

        # 3. supporting FACE_NOT_DETECTED -> no strike
        ev_face_loss = ProctoringRiskService.record_event(
            session=self.session,
            event_type='FACE_NOT_DETECTED',
            bypass_cooldown=True
        )
        assert ev_face_loss is not None
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 0

        # 4. supporting WINDOW_BLUR -> no strike
        ev_blur = ProctoringRiskService.record_event(
            session=self.session,
            event_type='WINDOW_BLUR',
            bypass_cooldown=True
        )
        assert ev_blur is not None
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 0

        # 5. confirmed PHONE_DETECTED -> one strong strike (Warning 1)
        ev_conf_phone = ProctoringRiskService.record_event(
            session=self.session,
            event_type='PHONE_DETECTED',
            bypass_cooldown=True,
            is_confirmed=True
        )
        assert ev_conf_phone is not None
        assert ev_conf_phone.is_confirmed is True
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 1

        # 6. confirmed MULTIPLE_FACES -> one strong strike (Warning 2 / Final Warning)
        ev_conf_faces = ProctoringRiskService.record_event(
            session=self.session,
            event_type='MULTIPLE_FACES',
            bypass_cooldown=True,
            is_confirmed=True
        )
        assert ev_conf_faces is not None
        assert ev_conf_faces.is_confirmed is True
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 2
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    def test_objective_6_test_a_supporting_signals(self):
        """
        Objective 6: TEST A — SUPPORTING SIGNALS
        Generate: WINDOW_BLUR, GAZE_DEVIATION, FACE_NOT_DETECTED, HEAD_MOVEMENT
        Expected: 0 strong strikes, no disqualification
        """
        for evt in ['WINDOW_BLUR', 'GAZE_DEVIATION', 'FACE_NOT_DETECTED', 'HEAD_MOVEMENT']:
            ev = ProctoringRiskService.record_event(
                session=self.session,
                event_type=evt,
                bypass_cooldown=True,
            )
            assert ev is not None

        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        assert self.session.total_warnings_count == 0
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS
        assert self.attempt.is_disqualified is False

    def test_objective_6_test_b_mixed_strong_signals(self):
        """
        Objective 6: TEST B — MIXED STRONG SIGNALS
        Generate confirmed: TAB_SWITCH, PHONE_DETECTED, MULTIPLE_FACES
        Expected: #1 -> Warning, #2 -> Final Warning, #3 -> Disqualification
        """
        # #1 TAB_SWITCH
        ev1 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            bypass_cooldown=True,
            is_confirmed=True,
        )
        assert ev1.is_confirmed is True
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 1
        assert self.session.status == ProctoringSessionStatus.ACTIVE

        # #2 PHONE_DETECTED
        ev2 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='PHONE_DETECTED',
            bypass_cooldown=True,
            is_confirmed=True,
        )
        assert ev2.is_confirmed is True
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 2
        assert self.session.status == ProctoringSessionStatus.ACTIVE

        # #3 MULTIPLE_FACES
        ev3 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='MULTIPLE_FACES',
            bypass_cooldown=True,
            is_confirmed=True,
        )
        assert ev3.is_confirmed is True
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()

        assert self.session.status == ProctoringSessionStatus.TERMINATED
        assert self.attempt.status == AttemptStatus.CANCELLED
        assert self.attempt.is_disqualified is True
        assert "THREE_STRONG_PROCTORING_VIOLATIONS" in self.attempt.disqualification_reason
        assert self.attempt.disqualified_at is not None

    def test_objective_6_test_c_single_blur(self):
        """
        Objective 6: TEST C — SINGLE BLUR
        Expected: no strike, no disqualification
        """
        ev = ProctoringRiskService.record_event(
            session=self.session,
            event_type='WINDOW_BLUR',
            bypass_cooldown=True,
        )
        assert ev is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.total_warnings_count == 0
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    def test_objective_6_test_d_face_loss(self):
        """
        Objective 6: TEST D — FACE LOSS
        Expected: supporting signal only, no strike, no disqualification
        """
        for evt in ['FACE_MISSING', 'FACE_NOT_DETECTED']:
            ev = ProctoringRiskService.record_event(
                session=self.session,
                event_type=evt,
                bypass_cooldown=True,
            )
            assert ev is not None
        self.session.refresh_from_db()
        self.attempt.refresh_from_db()
        assert self.session.total_warnings_count == 0
        assert self.session.status == ProctoringSessionStatus.ACTIVE
        assert self.attempt.status == AttemptStatus.IN_PROGRESS

    def test_objective_6_test_e_disqualification_resume_blocked(self):
        """
        Objective 6: TEST E — DISQUALIFICATION RESUME
        After disqualification:
        attempt cannot resume, exam room remains locked, answers remain frozen.
        """
        # Trigger disqualification
        for evt in ['TAB_SWITCH', 'FULLSCREEN_EXIT', 'PHONE_DETECTED']:
            ProctoringRiskService.record_event(
                session=self.session,
                event_type=evt,
                bypass_cooldown=True,
                is_confirmed=True,
            )
        self.attempt.refresh_from_db()
        assert self.attempt.is_disqualified is True
        assert self.attempt.status == AttemptStatus.CANCELLED

        # 1. Attempt cannot resume via start_attempt
        with pytest.raises(DRFValidationError) as exc_start:
            AttemptService.start_attempt(
                student=self.student,
                assessment_id=str(self.published_assessment.id),
                actor=self.student,
            )
        assert "CANDIDATE_DISQUALIFIED" in str(exc_start.value)

        # 2. Answers remain frozen
        snapshot_q = self.attempt.assessment_snapshot.snapshot_questions.first()
        with pytest.raises(DRFValidationError) as exc_save:
            AttemptService.save_answer(
                student=self.student,
                attempt_id=str(self.attempt.id),
                snapshot_question_id=snapshot_q.snapshot_question_id,
                answer_data={"selected_options": ["A"]},
            )
        assert "Cannot save answer to attempt in CANCELLED status" in str(exc_save.value)

        # 3. Submit is blocked
        with pytest.raises(DRFValidationError) as exc_sub:
            AttemptService.submit_attempt(
                student=self.student,
                attempt_id=str(self.attempt.id),
            )
        assert "Cannot submit a cancelled or disqualified" in str(exc_sub.value)


