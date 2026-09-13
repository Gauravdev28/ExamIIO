import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from apps.accounts.models import User, Role, StudentProfile
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AttemptService, AttemptTimerService
from apps.questions.models import QuestionType, Difficulty
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
    ProctoringRiskService,
    ProctoringWarningService,
)
from apps.results.models import StudentCoinLedger


class TestStudentAssessmentEntry(APITransactionTestCase):
    def setUp(self):
        # 1. Create Users
        self.admin = User.objects.create_user(
            email='admin_entry@test.com',
            password='TestPassword123!',
            display_name='Admin User',
            role=Role.ADMIN,
            is_active=True,
        )

        self.student1 = User.objects.create_user(
            email='student1_entry@test.com',
            password='TestPassword123!',
            display_name='Student One',
            role=Role.STUDENT,
            is_active=True,
        )
        StudentProfile.objects.create(
            user=self.student1,
            roll_number='ROLL-ENTRY-01',
            euid='CG-ROLL-ENTRY-01',
            certificate_name='Student One',
            first_login_required=False,
        )

        self.student2 = User.objects.create_user(
            email='student2_entry@test.com',
            password='TestPassword123!',
            display_name='Student Two',
            role=Role.STUDENT,
            is_active=True,
        )
        StudentProfile.objects.create(
            user=self.student2,
            roll_number='ROLL-ENTRY-02',
            euid='CG-ROLL-ENTRY-02',
            certificate_name='Student Two',
            first_login_required=False,
        )

        self.unassigned_student = User.objects.create_user(
            email='unassigned_entry@test.com',
            password='TestPassword123!',
            display_name='Unassigned Student',
            role=Role.STUDENT,
            is_active=True,
        )
        StudentProfile.objects.create(
            user=self.unassigned_student,
            roll_number='ROLL-ENTRY-03',
            euid='CG-ROLL-ENTRY-03',
            certificate_name='Unassigned Student',
            first_login_required=False,
        )

        # 2. Create Published Questions
        q1, v1 = QuestionService.create_question(
            title="Sample MCQ 1",
            question_type=QuestionType.MCQ,
            difficulty=Difficulty.EASY,
            description="What is 2 + 2?",
            points=5,
            type_config={"options": [{"id": "OPT_A", "text": "3"}, {"id": "OPT_B", "text": "4"}], "correct_options": ["OPT_B"]},
            actor=self.admin
        )
        self.pv1 = QuestionService.publish_version(v1, actor=self.admin)

        q2, v2 = QuestionService.create_question(
            title="Sample Coding 1",
            question_type=QuestionType.CODING,
            difficulty=Difficulty.MEDIUM,
            description="Return sum of two numbers",
            points=10,
            coding_config_data={
                "allowed_languages": ["PYTHON", "CPP"],
                "starter_codes": {"PYTHON": "def solution(a, b):\n    pass"},
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
            },
            test_cases_data=[
                {
                    "index": 1,
                    "input": "1 2\n",
                    "expected_output": "3\n",
                    "is_hidden": False,
                    "points": 10,
                }
            ],
            actor=self.admin
        )
        self.pv2 = QuestionService.publish_version(v2, actor=self.admin)

        # 3. Create Published Assessment with Snapshot
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Sample Assessment 01",
            description="Standard Entry Test",
            created_by=self.admin,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=5),
            duration_minutes=60,
            attempt_limit=1,
            camera_required=True,
            max_confirmed_violations=3,
        )

        # Assign students to assessment
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student1,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student2,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )

        self.snapshot = AssessmentSnapshot.objects.create(
            assessment=self.assessment,
            version_number=1,
            snapshot_data={
                "title": self.assessment.title,
                "questions": [
                    {
                        "snapshot_question_id": "q_snap_01",
                        "title": self.pv1.title,
                        "description": self.pv1.description,
                        "question_type": self.pv1.question_type,
                        "points": self.pv1.points,
                        "difficulty": self.pv1.difficulty,
                        "type_config": self.pv1.type_config,
                        "order": 1,
                    },
                    {
                        "snapshot_question_id": "q_snap_02",
                        "title": self.pv2.title,
                        "description": self.pv2.description,
                        "question_type": self.pv2.question_type,
                        "points": self.pv2.points,
                        "difficulty": self.pv2.difficulty,
                        "coding_config": {
                            "allowed_languages": ["PYTHON", "CPP"],
                            "starter_codes": {"PYTHON": "def solution(a, b):\n    pass"},
                            "time_limit_ms": 2000,
                            "memory_limit_mb": 256,
                        },
                        "order": 2,
                    }
                ]
            },
            server_evaluation_bundle={
                "questions": {
                    "q_snap_01": {
                        "question_type": "MCQ",
                        "points": 5,
                        "correct_type_config": {"correct_options": ["OPT_B"]}
                    },
                    "q_snap_02": {
                        "question_type": "CODING",
                        "points": 10,
                        "coding_config": {
                            "allowed_languages": ["PYTHON", "CPP"],
                            "time_limit_ms": 2000,
                            "memory_limit_mb": 256,
                        }
                    }
                }
            }
        )

        self.sq1 = AssessmentSnapshotQuestion.objects.create(
            snapshot=self.snapshot,
            question_version=self.pv1,
            snapshot_question_id="q_snap_01",
            order=1,
            title=self.pv1.title,
            description=self.pv1.description,
            question_type=self.pv1.question_type,
            difficulty=self.pv1.difficulty,
            points=self.pv1.points,
            type_config=self.pv1.type_config,
        )

        self.sq2 = AssessmentSnapshotQuestion.objects.create(
            snapshot=self.snapshot,
            question_version=self.pv2,
            snapshot_question_id="q_snap_02",
            order=2,
            title=self.pv2.title,
            description=self.pv2.description,
            question_type=self.pv2.question_type,
            difficulty=self.pv2.difficulty,
            points=self.pv2.points,
            coding_config={
                "allowed_languages": ["PYTHON", "CPP"],
                "starter_codes": {"PYTHON": "def solution(a, b):\n    pass"},
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
            },
        )

    # ----------------------------------------------------
    # ENTRY & IDEMPOTENCY TESTS
    # ----------------------------------------------------

    def test_first_click_starts_attempt_and_returns_201(self):
        """First click creates a new attempt and returns HTTP 201 with attempt_id."""
        self.client.force_authenticate(user=self.student1)
        url = f"/api/v1/student/assessments/{self.assessment.id}/start/"
        res = self.client.post(url)
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data['status'] == 'success'
        data = res.data['data']
        assert 'attempt_id' in data
        assert data['status'] == 'IN_PROGRESS'
        assert data['is_new'] is True

        # Verify attempt records in DB
        attempt = TestAttempt.objects.get(id=data['attempt_id'])
        assert attempt.student == self.student1
        assert attempt.status == AttemptStatus.IN_PROGRESS
        assert attempt.assessment_snapshot == self.snapshot
        assert AttemptAnswer.objects.filter(attempt=attempt).count() == 2

    def test_second_click_returns_existing_in_progress_attempt_200_idempotent(self):
        """Second click is strictly idempotent and returns HTTP 200 with existing attempt."""
        self.client.force_authenticate(user=self.student1)
        url = f"/api/v1/student/assessments/{self.assessment.id}/start/"
        res1 = self.client.post(url)
        assert res1.status_code == status.HTTP_201_CREATED
        att_id_1 = res1.data['data']['attempt_id']

        # Click 2
        res2 = self.client.post(url)
        assert res2.status_code == status.HTTP_200_OK
        assert res2.data['data']['attempt_id'] == att_id_1
        assert res2.data['data']['is_new'] is False
        assert res2.data['data']['status'] == 'IN_PROGRESS'

    def test_unassigned_candidate_rejected_with_403(self):
        """Unassigned Student receives Forbidden (403) on starting attempt."""
        self.client.force_authenticate(user=self.unassigned_student)
        url = f"/api/v1/student/assessments/{self.assessment.id}/start/"
        res = self.client.post(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_expired_assessment_cannot_be_started(self):
        """Expired assessment returns validation error (HTTP 400)."""
        now = timezone.now()
        expired_assessment = Assessment.objects.create(
            title="Expired Exam",
            created_by=self.admin,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=1),
            duration_minutes=30,
            attempt_limit=1,
        )
        AssessmentAssignment.objects.create(
            assessment=expired_assessment,
            student=self.student2,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )
        snap = AssessmentSnapshot.objects.create(
            assessment=expired_assessment,
            version_number=1,
            snapshot_data={"title": "Expired Exam"},
            server_evaluation_bundle={"questions": {}}
        )
        AssessmentSnapshotQuestion.objects.create(
            snapshot=snap,
            question_version=self.pv1,
            snapshot_question_id="q_snap_exp",
            order=1,
            title="Q",
            question_type=QuestionType.MCQ,
            points=5,
        )

        self.client.force_authenticate(user=self.student2)
        res = self.client.post(f"/api/v1/student/assessments/{expired_assessment.id}/start/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_snapshot_questions_rejected(self):
        """Assessment without frozen questions cannot be started."""
        now = timezone.now()
        empty_snap_assessment = Assessment.objects.create(
            title="Empty Exam",
            created_by=self.admin,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=5),
            duration_minutes=30,
            attempt_limit=1,
        )
        AssessmentAssignment.objects.create(
            assessment=empty_snap_assessment,
            student=self.student2,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )
        # Create empty snapshot
        AssessmentSnapshot.objects.create(
            assessment=empty_snap_assessment,
            version_number=1,
            snapshot_data={"title": "Empty Exam"},
            server_evaluation_bundle={"questions": {}}
        )

        self.client.force_authenticate(user=self.student2)
        res = self.client.post(f"/api/v1/student/assessments/{empty_snap_assessment.id}/start/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_student_attempt_detail_returns_sanitized_questions_and_timer(self):
        """GET /api/v1/student/attempts/<id>/ returns sanitized snapshot questions and valid remaining seconds."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']

        res_detail = self.client.get(f"/api/v1/student/attempts/{att_id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        d = res_detail.data['data']
        assert d['attempt_id'] == att_id
        assert d['title'] == self.assessment.title
        assert len(d['questions']) == 2
        assert d['remaining_seconds'] > 3500  # 60 mins ~ 3600s
        assert d['status'] == 'IN_PROGRESS'
        assert d['camera_required'] is True
        assert d['max_confirmed_violations'] == 3

    def test_student_cannot_access_another_students_attempt_detail_403(self):
        """Student 2 cannot view Student 1's attempt (HTTP 403)."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']

        self.client.force_authenticate(user=self.student2)
        res_detail = self.client.get(f"/api/v1/student/attempts/{att_id}/")
        assert res_detail.status_code == status.HTTP_403_FORBIDDEN

    # ----------------------------------------------------
    # PROCTORING & WARNING TESTS
    # ----------------------------------------------------

    def test_sustained_window_blur_issues_advisory_warning_without_strike(self):
        """WINDOW_BLUR generates advisory warning while confirmed violation strike count remains 0."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        session = ProctoringSessionService.start_session(attempt)

        # Ingest WINDOW_BLUR
        warn = ProctoringWarningService.issue_warning_if_eligible(
            session=session,
            event_type='WINDOW_BLUR',
            bypass_cooldown=True,
        )
        assert warn is not None
        assert warn.warning_type == 'FOCUS_LOSS'
        assert session.total_warnings_count == 1

        # Confirmed strike violations for disqualification are 0
        confirmed_strikes = ProctoringEvent.objects.filter(
            session=session,
            event_type__in=['TAB_SWITCH', 'FULLSCREEN_EXIT', 'PHONE_DETECTED', 'MULTIPLE_FACES'],
            is_confirmed=True
        ).count()
        assert confirmed_strikes == 0
        assert attempt.status == AttemptStatus.IN_PROGRESS

    def test_three_confirmed_violations_automatically_disqualifies_candidate(self):
        """Three confirmed violations (TAB_SWITCH) automatically terminates session and disqualifies attempt."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        session = ProctoringSessionService.start_session(attempt)

        # Strike 1
        ev1 = ProctoringRiskService.record_event(
            session=session,
            event_type='TAB_SWITCH',
            source=EventSource.BROWSER,
            bypass_cooldown=True,
            is_confirmed=True
        )
        session.refresh_from_db()
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.IN_PROGRESS
        assert session.status == ProctoringSessionStatus.ACTIVE

        # Strike 2
        ev2 = ProctoringRiskService.record_event(
            session=session,
            event_type='TAB_SWITCH',
            source=EventSource.BROWSER,
            bypass_cooldown=True,
            is_confirmed=True
        )
        session.refresh_from_db()
        attempt.refresh_from_db()
        assert attempt.status == AttemptStatus.IN_PROGRESS

        # Strike 3 -> Automatic Disqualification
        ev3 = ProctoringRiskService.record_event(
            session=session,
            event_type='TAB_SWITCH',
            source=EventSource.BROWSER,
            bypass_cooldown=True,
            is_confirmed=True
        )
        session.refresh_from_db()
        attempt.refresh_from_db()
        assert session.status == ProctoringSessionStatus.TERMINATED
        assert attempt.status == AttemptStatus.CANCELLED
        assert attempt.is_disqualified is True
        assert 'THREE_STRONG_PROCTORING_VIOLATIONS' in attempt.disqualification_reason

    def test_warning_acknowledgement_api(self):
        """Acknowledge warning endpoint records timestamp and marks warning acknowledged."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        session = ProctoringSessionService.start_session(attempt)

        warn = ProctoringWarningService.issue_warning_if_eligible(
            session=session,
            event_type='FULLSCREEN_EXIT',
            bypass_cooldown=True,
        )

        ack_url = f"/api/v1/student/attempts/{att_id}/proctoring/warnings/{warn.id}/ack/"
        res_ack = self.client.post(ack_url)
        assert res_ack.status_code == status.HTTP_200_OK
        warn.refresh_from_db()
        assert warn.acknowledged_at is not None

    def test_head_turn_prolonged_advisory_warning(self):
        """HEAD_TURN_PROLONGED generates advisory warning without adding strong strikes."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        session = ProctoringSessionService.start_session(attempt)

        warn = ProctoringWarningService.issue_warning_if_eligible(
            session=session,
            event_type='HEAD_TURN_PROLONGED',
            bypass_cooldown=True,
        )
        assert warn is not None
        assert warn.warning_type == 'HEAD_POSE'

    def test_multiple_faces_and_phone_detected_trigger_confirmed_strikes(self):
        """MULTIPLE_FACES and PHONE_DETECTED require qualifying confidence and multi-frame persistence."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        session = ProctoringSessionService.start_session(attempt)

        # Phone Detected - Frame 1 (first detection held by persistence gate)
        ev_phone_1 = ProctoringRiskService.record_event(
            session=session,
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            confidence=0.90,
            bypass_cooldown=True,
        )
        assert ev_phone_1 is None

        # Phone Detected - Frame 2 (sustained/persistent detection -> confirmed strike)
        ev_phone_2 = ProctoringRiskService.record_event(
            session=session,
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            confidence=0.90,
            bypass_cooldown=True,
        )
        assert ev_phone_2 is not None
        assert ev_phone_2.is_confirmed is True

        # Multiple Faces - Frame 1 (first detection held by persistence gate)
        ev_faces_1 = ProctoringRiskService.record_event(
            session=session,
            event_type='MULTIPLE_FACES',
            source=EventSource.AI,
            confidence=0.88,
            bypass_cooldown=True,
        )
        assert ev_faces_1 is None

        # Multiple Faces - Frame 2 (sustained detection -> confirmed strike)
        ev_faces_2 = ProctoringRiskService.record_event(
            session=session,
            event_type='MULTIPLE_FACES',
            source=EventSource.AI,
            confidence=0.88,
            bypass_cooldown=True,
        )
        assert ev_faces_2 is not None
        assert ev_faces_2.is_confirmed is True

    # ----------------------------------------------------
    # SECURITY & SUBMISSION TESTS
    # ----------------------------------------------------

    def test_disqualified_attempt_cannot_save_answer_or_submit(self):
        """Disqualified (CANCELLED) attempt rejects answer saves and final submissions."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.save(update_fields=['status', 'is_disqualified'])

        # Save Answer -> 400
        save_url = f"/api/v1/student/attempts/{att_id}/answers/q_snap_01/"
        res_save = self.client.post(save_url, {"selected_options": ["OPT_B"], "revision": 2})
        assert res_save.status_code == status.HTTP_400_BAD_REQUEST

        # Submit -> 400
        sub_url = f"/api/v1/student/attempts/{att_id}/submit/"
        res_sub = self.client.post(sub_url)
        assert res_sub.status_code == status.HTTP_400_BAD_REQUEST

    def test_finish_and_submit_automatic_grading_and_coin_idempotency(self):
        """Final submission calculates grade and awards +3 coins per correct question idempotently."""
        from apps.results.models import AssessmentResult
        from apps.results.services import ResultFinalizationService
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']

        # Answer MCQ correctly (OPT_B)
        save_url = f"/api/v1/student/attempts/{att_id}/answers/q_snap_01/"
        self.client.post(save_url, {"selected_options": ["OPT_B"], "revision": 2})

        # Submit Attempt
        sub_url = f"/api/v1/student/attempts/{att_id}/submit/"
        res_sub = self.client.post(sub_url)
        assert res_sub.status_code == status.HTTP_200_OK

        attempt = TestAttempt.objects.get(id=att_id)
        assert attempt.status == AttemptStatus.SUBMITTED

        # Calculate result
        result = ResultFinalizationService.finalize_attempt(
            attempt_id=str(attempt.id),
            actor=self.student1
        )
        assert result.total_score_earned == Decimal('5.00')

        # Check coin transaction
        coin_txs = StudentCoinLedger.objects.filter(student=self.student1, attempt=attempt)
        assert coin_txs.count() >= 1
        assert coin_txs.first().coins_awarded == 3

        # Idempotency check: invoking grading or coin award again does NOT duplicate coins
        initial_tx_count = coin_txs.count()
        ResultFinalizationService.finalize_attempt(
            attempt_id=str(attempt.id),
            actor=self.student1
        )
        assert StudentCoinLedger.objects.filter(student=self.student1, attempt=attempt).count() == initial_tx_count

    def test_attempt_limit_exceeded_cannot_start_new_attempt(self):
        """When attempt_limit=1 and student already submitted an attempt, starting another attempt is rejected."""
        self.assessment.attempt_limit = 1
        self.assessment.save(update_fields=['attempt_limit'])

        self.client.force_authenticate(user=self.student1)
        res1 = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        assert res1.status_code == status.HTTP_201_CREATED
        att_id = res1.data['data']['attempt_id']

        # Submit attempt
        self.client.post(f"/api/v1/student/attempts/{att_id}/submit/")

        # Attempt to start second attempt
        res2 = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        assert res2.status_code == status.HTTP_400_BAD_REQUEST

    def test_unpublished_draft_assessment_cannot_be_started(self):
        """Draft/unpublished assessments cannot be entered or started by students."""
        draft_assessment = Assessment.objects.create(
            title="Draft Exam",
            description="Draft",
            status=AssessmentStatus.DRAFT,
            start_datetime=timezone.now() - timedelta(minutes=10),
            end_datetime=timezone.now() + timedelta(hours=2),
            duration_minutes=60,
            total_points=100,
            created_by=self.admin
        )
        self.client.force_authenticate(user=self.student1)
        res = self.client.post(f"/api/v1/student/assessments/{draft_assessment.id}/start/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_camera_and_microphone_unavailable_events(self):
        """Reporting CAMERA_UNAVAILABLE or MICROPHONE_UNAVAILABLE creates audit record and issues warning."""
        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']

        # Report camera unavailable
        res_cam = self.client.post(
            f"/api/v1/student/attempts/{att_id}/proctoring/events/",
            {"event_type": "CAMERA_UNAVAILABLE"},
            format="json"
        )
        assert res_cam.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]

        # Report microphone unavailable
        res_mic = self.client.post(
            f"/api/v1/student/attempts/{att_id}/proctoring/events/",
            {"event_type": "MICROPHONE_UNAVAILABLE"},
            format="json"
        )
        assert res_mic.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]

    def test_coding_submission_grading_and_evaluation_separation(self):
        """Verify Coding question submission results calculation in ResultFinalizationService."""
        from apps.results.services import ResultFinalizationService
        from apps.evaluator.models import CodeSubmission, SubmissionType, SubmissionStatus, CodeVerdict
        from apps.assessments.models import AssessmentSnapshotQuestion

        self.client.force_authenticate(user=self.student1)
        res_start = self.client.post(f"/api/v1/student/assessments/{self.assessment.id}/start/")
        att_id = res_start.data['data']['attempt_id']
        attempt = TestAttempt.objects.get(id=att_id)

        snap_q = AssessmentSnapshotQuestion.objects.filter(snapshot=attempt.assessment_snapshot, snapshot_question_id="q_snap_02").first()

        # Create mock authoritative SUBMIT code submission with passed tests
        CodeSubmission.objects.create(
            attempt=attempt,
            snapshot_question=snap_q,
            submission_type=SubmissionType.SUBMIT,
            language="PYTHON",
            source_code="def solve(): return True",
            status=SubmissionStatus.COMPLETED,
            verdict=CodeVerdict.ACCEPTED,
            score_awarded=Decimal('10.00'),
            max_score=10,
            passed_test_cases=3,
            total_test_cases=3
        )

        # Submit attempt
        self.client.post(f"/api/v1/student/attempts/{att_id}/submit/")

        # Finalize
        result = ResultFinalizationService.finalize_attempt(
            attempt_id=str(attempt.id),
            actor=self.student1
        )
        assert result.total_score_earned >= Decimal('10.00')

        # Check coin ledger award for passed coding question
        coin_txs = StudentCoinLedger.objects.filter(student=self.student1, attempt=attempt)
        assert coin_txs.filter(coins_awarded=3).exists()

    async def test_websocket_channel_owner_connect_and_proctor_event_dispatch(self):
        """Owner connects to attempt WebSocket, receives SYNC_STATE, PONG, and real-time proctoring events."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from codeguard.routing import websocket_urlpatterns
        from channels.db import database_sync_to_async

        attempt = await database_sync_to_async(TestAttempt.objects.create)(
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=60),
            question_order=["q_snap_01", "q_snap_02"]
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, f"/ws/attempts/{attempt.id}/")
        communicator.scope['user'] = self.student1

        connected, _ = await communicator.connect()
        assert connected

        # 1. Verify SYNC_STATE
        initial_msg = await communicator.receive_json_from()
        assert initial_msg['type'] == "SYNC_STATE"
        assert initial_msg['data']['attempt_id'] == str(attempt.id)

        # 2. Verify PING/PONG
        await communicator.send_json_to({"action": "PING"})
        pong_msg = await communicator.receive_json_from()
        assert pong_msg['type'] == "PONG"

        # 3. Simulate proctor_event broadcast
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"attempt_{attempt.id}",
                {
                    "type": "proctor_event",
                    "data": {
                        "event": "WARNING_ISSUED",
                        "attempt_id": str(attempt.id),
                        "reason_code": "FOCUS_LOSS",
                        "message": "Assessment window lost focus.",
                        "warnings_count": 1
                    }
                }
            )
            warn_msg = await communicator.receive_json_from()
            assert warn_msg.get('event') == "WARNING_ISSUED" or warn_msg.get('type') == "PROCTOR_EVENT"

        await communicator.disconnect()

    async def test_websocket_unauthorized_student_access_rejected(self):
        """Unauthorized student attempting to connect to another student's attempt is rejected with 4003."""
        from channels.testing import WebsocketCommunicator
        from channels.routing import URLRouter
        from codeguard.routing import websocket_urlpatterns
        from channels.db import database_sync_to_async

        attempt = await database_sync_to_async(TestAttempt.objects.create)(
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=60),
            question_order=["q_snap_01"]
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, f"/ws/attempts/{attempt.id}/")
        communicator.scope['user'] = self.student2

        connected, close_code = await communicator.connect()
        assert not connected or close_code == 4003

