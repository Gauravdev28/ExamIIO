"""
Targeted Verification Tests for C Language Code Execution via Piston.
"""
import pytest
from apps.evaluator.execution import (
    CanonicalLanguage,
    CodeExecutionService,
    ExecutionRequest,
    ExecutionStatus,
    PistonAdapter,
)


@pytest.mark.live_judge0
@pytest.mark.django_db
class TestCLanguageExecution:
    """
    Comprehensive tests for C language execution, error classification, limits, and mappings.
    """

    def test_c_language_normalization(self):
        for lang_str in ['c', 'C', 'gcc', 'GCC', 'c11', 'C11', 'c99', 'C99', 'clang', 'CLANG']:
            assert CanonicalLanguage.normalize(lang_str) == CanonicalLanguage.C.value

    def test_c_exact_program_stdout(self):
        source = """#include <stdio.h>

int main() {
    printf("Hello from C");
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="Hello from C",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "Hello from C"
        assert not res.stderr
        assert res.compile_output is None
        assert not res.infrastructure_error

    def test_c_stdin_addition(self):
        source = """#include <stdio.h>

int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d", a + b);
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="5 7",
            expected_output="12",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "12"
        assert not res.stderr

    def test_c_compilation_error(self):
        source = """#include <stdio.h>

int main() {
    printf("Hello"
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.COMPILATION_ERROR.value
        assert res.compile_output is not None
        assert "error:" in res.compile_output.lower() or "expected" in res.compile_output.lower()
        assert not res.infrastructure_error

    def test_c_runtime_error_division_by_zero(self):
        source = """#include <stdio.h>

int main() {
    int x = 1 / 0;
    printf("%d", x);
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.RUNTIME_ERROR.value
        assert not res.infrastructure_error

    def test_c_timeout_infinite_loop(self):
        source = """#include <stdio.h>

int main() {
    while (1) {}
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.TIME_LIMIT.value
        assert not res.infrastructure_error

    def test_c_empty_output(self):
        source = """#include <stdio.h>

int main() {
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout == ""
        assert not res.stderr

    def test_admin_c_sandbox_run_api(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User, Role

        admin = User.objects.create_user(
            email="admin_c_test@codeguard.test",
            password="AdminPassword123!",
            role=Role.ADMIN
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        payload = {
            "source_code": '#include <stdio.h>\nint main() { int a, b; scanf("%d %d", &a, &b); printf("%d\\n", a + b); return 0; }',
            "language": "C",
            "stdin": "10 25",
            "expected_output": "35",
            "time_limit_ms": 2000,
            "memory_limit_mb": 256
        }
        resp = client.post("/api/v1/admin/questions/run-sandbox/", data=payload, format="json")
        assert resp.status_code == 200
        data = resp.json().get('data', {})
        assert data.get('status') == 'SUCCESS'
        assert data.get('passed') is True
        assert data.get('stdout').strip() == '35'

    def test_student_c_run_code_api(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User, Role, StudentProfile
        from apps.questions.models import Question, QuestionVersion, QuestionType, Difficulty, VersionStatus, CodingQuestionConfig, TestCase
        from apps.assessments.models import Assessment, AssessmentStatus, AssessmentQuestion, AssessmentAssignment, TestAttempt, AttemptStatus
        from apps.assessments.services import AssessmentSnapshotService
        from datetime import timedelta
        from django.utils import timezone

        admin = User.objects.create_user(email="admin_c_q@codeguard.test", password="Pass", role=Role.ADMIN)
        student = User.objects.create_user(email="student_c_q@codeguard.test", password="Pass", role=Role.STUDENT)
        StudentProfile.objects.create(user=student, roll_number="C-001", first_login_required=False)

        q = Question.objects.create(created_by=admin)
        v = QuestionVersion.objects.create(
            question=q,
            version_number=1,
            title="C Sum",
            description="Add two numbers",
            question_type=QuestionType.CODING,
            difficulty=Difficulty.EASY,
            status=VersionStatus.PUBLISHED,
            points=10,
            created_by=admin
        )
        cc = CodingQuestionConfig.objects.create(
            question_version=v,
            problem_statement="Sum",
            allowed_languages=['C', 'PYTHON'],
            time_limit_ms=2000,
            memory_limit_mb=256
        )
        TestCase.objects.create(
            coding_config=cc,
            input_data="4 6\n",
            expected_output="10\n",
            points=10,
            is_hidden=False,
            execution_order=1
        )

        now = timezone.now()
        assessment = Assessment.objects.create(
            title="C Exam",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            status=AssessmentStatus.DRAFT,
            created_by=admin
        )
        AssessmentQuestion.objects.create(assessment=assessment, question_version=v, order=1, points=10)
        snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin)
        assessment.status = AssessmentStatus.PUBLISHED
        assessment.published_at = now
        assessment.save()
        AssessmentAssignment.objects.create(assessment=assessment, student=student, assigned_by=admin)

        attempt = TestAttempt.objects.create(
            assessment=assessment,
            assessment_snapshot=snapshot,
            student=student,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now
        )

        client = APIClient()
        client.force_authenticate(user=student)

        snap_q = snapshot.snapshot_questions.first()
        run_payload = {
            "source_code": '#include <stdio.h>\nint main() { int a, b; scanf("%d %d", &a, &b); printf("%d\\n", a + b); return 0; }',
            "language": "C",
        }
        resp = client.post(
            f"/api/v1/student/attempts/{attempt.id}/questions/{snap_q.snapshot_question_id}/run/",
            data=run_payload,
            format="json"
        )
        assert resp.status_code == 202
        sub_id = resp.json().get('data', {}).get('submission_id')
        assert sub_id is not None

        # Retrieve submission detail
        detail_resp = client.get(f"/api/v1/student/submissions/{sub_id}/")
        assert detail_resp.status_code == 200
        sub_data = detail_resp.json().get('data', {})
        assert sub_data.get('status') == 'COMPLETED'
        assert sub_data.get('verdict') == 'ACCEPTED'

