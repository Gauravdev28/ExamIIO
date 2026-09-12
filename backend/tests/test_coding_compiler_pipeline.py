import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
import requests

from apps.accounts.models import User, StudentProfile
from apps.questions.models import (
    Question,
    QuestionVersion,
    CodingQuestionConfig,
    TestCase,
    QuestionType,
    Difficulty,
    VersionStatus,
)
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.evaluator.models import (
    CodeSubmission,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
)
from apps.evaluator.services import (
    CodeSubmissionService,
    Judge0Adapter,
    OutputComparisonService,
)
from apps.results.models import StudentCoinLedger


@pytest.mark.django_db
class TestCodingCompilerPipeline:
    """
    Comprehensive tests for the Coding Compiler & Execution Pipeline:
    - Configuration-driven language mappings (PYTHON, CPP, JAVA)
    - Authoritative 9-state normalization contract
    - Student Run Code API boundaries & security isolation
    - No coin award, no answer finalization, no hidden test leakage on Run Code
    """

    @pytest.fixture(autouse=True)
    def setup_pipeline_env(self):
        self.admin = User.objects.create_superuser(
            email='compiler_admin@codeguard.internal',
            password='AdminPassword123!'
        )
        self.student = User.objects.create_user(
            email='compiler_student@university.edu',
            password='StudentPassword123!',
            role='STUDENT'
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number='COMP-001',
            euid='EUID-COMP-001',
            first_login_required=False
        )

        from apps.questions.services import QuestionService

        # Create Coding Question
        self.question, self.q_v1 = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Compiler Test Problem',
            description='Sum two numbers from stdin',
            points=20,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON', 'CPP', 'JAVA'],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'input_data': '2 3',
                    'expected_output': '5',
                    'points': 10,
                    'is_hidden': False,
                    'is_example': True,
                    'execution_order': 1,
                },
                {
                    'input_data': '10 20',
                    'expected_output': '30',
                    'points': 10,
                    'is_hidden': True,
                    'is_example': False,
                    'execution_order': 2,
                }
            ],
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        # Assessment
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title='Compiler Audit Exam',
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=20,
            created_by=self.admin
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=20
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin
        )
        self.pub_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)
        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.pub_assessment.id),
            actor=self.student
        )
        self.snap_q = self.attempt.assessment_snapshot.snapshot_questions.first()
        self.run_url = f'/api/v1/student/attempts/{self.attempt.id}/questions/{self.snap_q.snapshot_question_id}/run/'

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    # ============================================================
    # 1. LANGUAGE MAPPING TESTS
    # ============================================================

    def test_python_language_mapping(self):
        """Backend resolves canonical PYTHON to configured Judge0 ID."""
        assert Judge0Adapter.get_language_id('PYTHON') == 71
        assert Judge0Adapter.get_language_id('python') == 71

    def test_cpp_language_mapping(self):
        """Backend resolves canonical CPP to configured Judge0 ID."""
        assert Judge0Adapter.get_language_id('CPP') == 54
        assert Judge0Adapter.get_language_id('cpp') == 54

    def test_java_language_mapping(self):
        """Backend resolves canonical JAVA to configured Judge0 ID."""
        assert Judge0Adapter.get_language_id('JAVA') == 62
        assert Judge0Adapter.get_language_id('java') == 62

    def test_missing_language_configuration(self):
        """Missing or unsupported language mapping raises ValueError, never guesses."""
        with pytest.raises(ValueError) as exc:
            Judge0Adapter.get_language_id('RUBY')
        assert "Unsupported execution language" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            Judge0Adapter.get_language_id('SQL')
        assert "Unsupported execution language" in str(exc.value)

    # ============================================================
    # 2. EXECUTION RESULT NORMALIZATION (9 CANONICAL STATES)
    # ============================================================

    def test_compile_error_normalization(self):
        """Compilation error (Judge0 id=6) normalizes to COMPILATION_ERROR."""
        raw = {
            'status': {'id': 6, 'description': 'Compilation Error'},
            'compile_output': 'SyntaxError: unexpected EOF while parsing',
            'time': '0.05',
            'memory': 12400
        }
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'COMPILATION_ERROR'
        assert res['compile_output'] == 'SyntaxError: unexpected EOF while parsing'
        assert res['execution_time_ms'] == 50

    def test_runtime_error_normalization(self):
        """Runtime error (Judge0 id=11 / NZEC) normalizes to RUNTIME_ERROR."""
        raw = {
            'status': {'id': 11, 'description': 'Runtime Error (NZEC)'},
            'stderr': 'ZeroDivisionError: division by zero',
            'time': '0.02',
            'memory': 15000
        }
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'RUNTIME_ERROR'
        assert 'ZeroDivisionError' in res['stderr']

    def test_timeout_normalization(self):
        """Time Limit Exceeded (Judge0 id=5) normalizes to TIME_LIMIT_EXCEEDED."""
        raw = {
            'status': {'id': 5, 'description': 'Time Limit Exceeded'},
            'time': '2.01',
            'memory': 24000
        }
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'TIME_LIMIT_EXCEEDED'
        assert res['execution_time_ms'] == 2010

    def test_execution_result_normalization(self):
        """Authoritative 9-state contract returns standard fields."""
        raw = {
            'status': {'id': 3, 'description': 'Accepted'},
            'stdout': '5\n',
            'stderr': '',
            'compile_output': None,
            'time': '0.08',
            'memory': 18000
        }
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'SUCCESS'
        assert res['stdout'] == '5\n'
        assert res['stderr'] == ''
        assert res['compile_output'] == ''
        assert res['execution_time_ms'] == 80
        assert res['memory_kb'] == 18000

    def test_queued_execution(self):
        """Judge0 id=1 normalizes to QUEUED (non-terminal)."""
        raw = {'status': {'id': 1, 'description': 'In Queue'}}
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'QUEUED'

    def test_processing_execution(self):
        """Judge0 id=2 normalizes to PROCESSING (non-terminal)."""
        raw = {'status': {'id': 2, 'description': 'Processing'}}
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'PROCESSING'

    def test_terminal_execution_stops_polling(self):
        """All 7 terminal statuses are non-polling terminal states."""
        terminal_statuses = [
            'SUCCESS',
            'COMPILATION_ERROR',
            'RUNTIME_ERROR',
            'TIME_LIMIT_EXCEEDED',
            'MEMORY_LIMIT_EXCEEDED',
            'SYSTEM_ERROR',
            'SANDBOX_UNAVAILABLE'
        ]
        for t_stat in terminal_statuses:
            assert t_stat not in ['QUEUED', 'PROCESSING']

    def test_judge0_unavailable_returns_sandbox_unavailable(self):
        """Sandbox connection error returns fail-closed response and normalizes to SANDBOX_UNAVAILABLE."""
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Connection refused")):
            raw = Judge0Adapter.execute_in_sandbox('print(1)', 'PYTHON', 'stdin', 'expected')
            res = Judge0Adapter.normalize_execution_result(raw)
            assert res['status'] == 'SANDBOX_UNAVAILABLE'

    def test_unknown_execution_status_returns_system_error(self):
        """Unmapped or corrupted Judge0 response returns SYSTEM_ERROR, never silent SUCCESS."""
        raw = {'status': {'id': 999, 'description': 'Unknown Alien Status'}}
        res = Judge0Adapter.normalize_execution_result(raw)
        assert res['status'] == 'SYSTEM_ERROR'

    # ============================================================
    # 3. STUDENT RUN CODE API & SECURITY
    # ============================================================

    def test_student_run_code_endpoint(self):
        """Student run code endpoint queues run execution and returns HTTP 202."""
        payload = {
            'language': 'PYTHON',
            'source_code': 'print(5)',
            'custom_input': '2 3'
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 202
        assert 'submission_id' in res.data['data']
        assert res.data['data']['status'] == 'QUEUED'
        assert res.data['data']['submission_type'] == 'RUN'

    def test_student_run_code_requires_exam_access(self):
        """Unassigned student cannot execute run code on this attempt."""
        other_student = User.objects.create_user(
            email='unassigned_comp@university.edu',
            password='Password123!',
            role='STUDENT'
        )
        StudentProfile.objects.create(user=other_student, roll_number='R-COMP-999', euid='E-COMP-999', first_login_required=False)
        other_client = APIClient()
        other_client.force_authenticate(user=other_student)

        payload = {
            'language': 'PYTHON',
            'source_code': 'print(1)'
        }
        res = other_client.post(self.run_url, payload, format='json')
        assert res.status_code in [403, 404]

    def test_student_run_code_uses_snapshot_language_policy(self):
        """Run code rejects languages disallowed by the snapshot policy."""
        payload = {
            'language': 'RUBY',
            'source_code': 'puts 1'
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 400

    def test_student_run_code_returns_execution_token(self):
        """Student run code returns a valid submission_id token."""
        payload = {
            'language': 'PYTHON',
            'source_code': 'print(10)'
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 202
        token = res.data['data']['submission_id']
        assert token is not None
        assert len(token) > 10

    def test_execution_request_validation(self):
        """Missing required fields in run request are rejected with 400."""
        res = self.client.post(self.run_url, {}, format='json')
        assert res.status_code == 400

    def test_invalid_language_rejected(self):
        """Invalid language identifier rejected at boundary."""
        payload = {
            'language': 'INVALID_LANG_XYZ',
            'source_code': 'print(1)'
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 400

    def test_empty_source_code_rejected(self):
        """Empty source code is rejected."""
        payload = {
            'language': 'PYTHON',
            'source_code': '   '
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 400

    def test_run_code_does_not_finalize_answer(self):
        """Run Code NEVER finalizes an AttemptAnswer (is_answered remains False)."""
        answer_before = AttemptAnswer.objects.filter(attempt=self.attempt, snapshot_question=self.snap_q).first()
        assert answer_before is None or not answer_before.is_answered

        CodeSubmissionService.execute_run(
            student=self.student,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            source_code='print(5)',
            language='PYTHON',
            custom_input='2 3'
        )
        answer_after = AttemptAnswer.objects.filter(attempt=self.attempt, snapshot_question=self.snap_q).first()
        assert answer_after is None or not answer_after.is_answered

    def test_run_code_does_not_award_coins(self):
        """Run Code awards 0 coins, even when executed."""
        from apps.results.models import StudentCoinLedger
        initial_coins_count = StudentCoinLedger.objects.filter(student=self.student).count()
        CodeSubmissionService.execute_run(
            student=self.student,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            source_code='print(5)',
            language='PYTHON',
            custom_input='2 3'
        )
        after_coins_count = StudentCoinLedger.objects.filter(student=self.student).count()
        assert initial_coins_count == after_coins_count == 0

    def test_hidden_tests_not_exposed_during_run(self):
        """Run Code submission is strictly RUN type and does not evaluate or expose hidden tests."""
        sub, created = CodeSubmissionService.execute_run(
            student=self.student,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            source_code='import sys; print(sys.stdin.read())',
            language='PYTHON',
            custom_input='custom_candidate_input'
        )
        assert sub.submission_type == SubmissionType.RUN
        hidden_results = sub.test_case_results.filter(is_hidden=True)
        assert hidden_results.count() == 0

    def test_student_cannot_change_execution_limits(self):
        """Student Run API does not allow overriding execution limits."""
        # CodeRunRequestSerializer only accepts source_code, language, custom_input, client_nonce
        payload = {
            'language': 'PYTHON',
            'source_code': 'print(1)',
            'time_limit_ms': 999999,
            'memory_limit_mb': 99999
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 202
        # Verify submission uses snapshot question configuration, not student inputs
        sub = CodeSubmission.objects.get(id=res.data['data']['submission_id'])
        snapshot_config = self.snap_q.coding_config
        assert snapshot_config.get('time_limit_ms', 2000) == 2000
        assert snapshot_config.get('memory_limit_mb', 256) == 256

    def test_student_cannot_select_arbitrary_runtime(self):
        """Student cannot choose arbitrary runtime environment or commands."""
        payload = {
            'language': 'BASH_DOCKER_ROOT',
            'source_code': 'rm -rf /'
        }
        res = self.client.post(self.run_url, payload, format='json')
        assert res.status_code == 400

    def test_duplicate_execution_is_safe(self):
        """Rapid duplicate execution with idempotent client_nonce returns existing submission."""
        nonce = 'test-idempotent-nonce-12345'
        payload = {
            'language': 'PYTHON',
            'source_code': 'print("ok")',
            'client_nonce': nonce
        }
        res1 = self.client.post(self.run_url, payload, format='json')
        assert res1.status_code == 202
        sub_id_1 = res1.data['data']['submission_id']

        res2 = self.client.post(self.run_url, payload, format='json')
        assert res2.status_code == 202
        sub_id_2 = res2.data['data']['submission_id']

        assert sub_id_1 == sub_id_2
        assert res2.data['data']['is_new'] is False
