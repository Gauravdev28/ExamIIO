import io
import pytest
from PIL import Image
from django.utils import timezone
from apps.accounts.models import User, StudentProfile, Role
from apps.assessments.models import Assessment, AssessmentQuestion, AssessmentAssignment, AssessmentStatus
from apps.assessments.services import AssessmentService, AttemptService
from apps.questions.services import QuestionService
from apps.proctoring.models import ProctoringSession, ProctoringEvent, ProctoringWarning, ProctoringSessionStatus
from apps.proctoring.services import ProctoringSessionService, ProctoringRiskService, ProctoringAIService
from apps.proctoring.serializers import AdminProctoringSessionListSerializer

@pytest.mark.django_db
class TestIssue3ProctoringDetection:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.admin = User.objects.create(email="admin_issue3@example.com", role=Role.ADMIN)
        self.student = User.objects.create(email="student_issue3@example.com", role=Role.STUDENT)
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="ISSUE3-ROLL",
            euid="ISSUE3-EUID"
        )
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
            title="Proctoring Integrity Verification Assessment",
            description="Testing proctoring audit fixes",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timezone.timedelta(hours=1),
            end_datetime=now + timezone.timedelta(hours=2),
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
        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.published_assessment.id),
            actor=self.student
        )
        self.session = ProctoringSessionService.start_session(self.attempt)

    def test_tab_switch_focus_loss_and_strike_progression(self):
        """1. Ingest TAB_SWITCH: verified as strong violation, Strike 1 warning issued."""
        ev1 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            confidence=1.0,
            metadata={"client_detected_at": timezone.now().isoformat()}
        )
        assert ev1 is not None
        assert ev1.is_confirmed is True
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 1
        assert self.session.total_events_count == 1

        """2. Ingest WINDOW_BLUR: supporting signal, recorded as telemetry, NO false strike."""
        ev_blur = ProctoringRiskService.record_event(
            session=self.session,
            event_type='WINDOW_BLUR',
            confidence=1.0,
            metadata={"duration_ms": 1000}
        )
        assert ev_blur is not None
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 1
        assert self.session.total_events_count == 2

        """3. Ingest Strike 2 (TAB_SWITCH): FINAL WARNING issued, bypassing cooldown."""
        ev2 = ProctoringRiskService.record_event(
            session=self.session,
            event_type='TAB_SWITCH',
            confidence=1.0,
            bypass_cooldown=True
        )
        assert ev2 is not None
        self.session.refresh_from_db()
        assert self.session.total_warnings_count == 2
        latest_warning = ProctoringWarning.objects.filter(session=self.session).order_by('-issued_at').first()
        assert "FINAL WARNING" in latest_warning.message

        """4. Admin Proctoring API Serializer returns violation_count and latest_violation."""
        serializer = AdminProctoringSessionListSerializer(self.session)
        data = serializer.data
        assert data['violation_count'] == 3
        assert data['total_warnings_count'] == 2
        assert data['latest_violation'] == 'Tab Switch'
        assert data['student']['email'] == 'student_issue3@example.com'
        assert data['student']['euid'] == 'ISSUE3-EUID'

    def test_camera_dark_frame_obstruction_detection(self):
        """Camera AI frame analysis flags dark/covered lens as FACE_MISSING."""
        dark_img = Image.new('RGB', (100, 100), color=(0, 0, 0))
        buf = io.BytesIO()
        dark_img.save(buf, format='JPEG')
        dark_bytes = buf.getvalue()

        signals = ProctoringAIService.analyze_frame_data(self.session, dark_bytes, 1)
        assert len(signals) == 1
        assert signals[0]['event_type'] == 'FACE_MISSING'
        assert signals[0]['metadata']['reason'] == 'camera_obstructed_or_dark'
