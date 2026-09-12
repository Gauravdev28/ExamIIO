"""
Comprehensive Tests for C Language Question Lifecycle, Multi-Language Execution Parity,
Evaluation Limits, and Existing Question Data Preservation.
"""
import json
import uuid
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role, StudentProfile
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    QuestionStatus,
    CodingLanguage,
    CodingQuestionConfig,
    TestCase,
)
from apps.questions.canonical import (
    CanonicalQuestionDTO,
    CanonicalCodingConfigDTO,
    CanonicalTestCaseDTO,
    SUPPORTED_CODING_LANGUAGES,
    validate_and_normalize_canonical_question,
)
from django.core.exceptions import PermissionDenied
from apps.questions.services import QuestionService, CodingQuestionValidationService
from apps.questions.services_platform_import import CodingQuestionPayloadNormalizer
from apps.evaluator.services import OutputComparisonService
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSnapshot,
    AssessmentStatus,
    TestAttempt,
)
from apps.assessments.services import (
    AssessmentService,
    AssessmentSnapshotService,
)
from apps.evaluator.execution import (
    CanonicalLanguage,
    CodeExecutionService,
    ExecutionRequest,
    ExecutionStatus,
)

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="c_admin@codeguard.local",
        password="AdminSecurePass123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="c_student@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT,
        first_login_required=False
    )
    StudentProfile.objects.create(
        user=user,
        roll_number=f"CS-C-{uuid.uuid4().hex[:6]}",
        first_login_required=False
    )
    return user


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestCLanguageValidation:
    """1. Language Validation Tests"""

    def test_supported_languages_includes_c(self):
        assert "C" in SUPPORTED_CODING_LANGUAGES
        assert "PYTHON" in SUPPORTED_CODING_LANGUAGES
        assert "CPP" in SUPPORTED_CODING_LANGUAGES
        assert "JAVA" in SUPPORTED_CODING_LANGUAGES
        assert CodingLanguage.C == "C"

    def test_canonical_dto_accepts_c(self):
        dto = CanonicalCodingConfigDTO(
            languages=["C"],
            starter_codes={"C": "#include <stdio.h>\n"},
            constraints="1 <= N <= 100",
            execution_time_ms=2000,
            memory_mb=256,
            examples=[]
        )
        assert "C" in dto.languages
        assert dto.starter_codes["C"] == "#include <stdio.h>\n"

    def test_canonical_dto_rejects_unsupported_language(self):
        dto = CanonicalQuestionDTO(
            question_id="Q-TEST-01",
            title="Invalid Language Question",
            type="CODING",
            statement="Testing language validation",
            instructions="",
            points=10,
            coding=CanonicalCodingConfigDTO(
                languages=["RUST"],
                starter_codes={"RUST": "fn main() {}"},
                constraints="",
                execution_time_ms=2000,
                memory_mb=256,
                examples=[]
            )
        )
        norm_dto, errors, _ = validate_and_normalize_canonical_question(dto)
        assert len(errors) > 0
        assert any("Unsupported coding language 'RUST'" in str(e) for e in errors)

    def test_admin_supported_languages_api(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/admin/questions/languages/")
        assert res.status_code == 200
        data = res.json()["data"]
        langs = [l["key"] for l in data.get("languages", [])]
        assert "C" in langs
        assert "PYTHON" in langs
        assert "CPP" in langs
        assert "JAVA" in langs

        c_detail = next((d for d in data.get("languages", []) if d.get("key") == "C"), None)
        assert c_detail is not None
        assert c_detail["monaco_lang"] == "c"
        assert c_detail["default_starter_code"] == "#include <stdio.h>\n"

        py_detail = next((d for d in data.get("languages", []) if d.get("key") == "PYTHON"), None)
        assert py_detail is not None
        assert py_detail["default_starter_code"] == "def solve():\n    pass\n"

        cpp_detail = next((d for d in data.get("languages", []) if d.get("key") == "CPP"), None)
        assert cpp_detail is not None
        assert cpp_detail["default_starter_code"] == "#include <bits/stdc++.h>\n"

        java_detail = next((d for d in data.get("languages", []) if d.get("key") == "JAVA"), None)
        assert java_detail is not None
        assert java_detail["default_starter_code"] == "import java.io.*;\n"


@pytest.mark.django_db
class TestCQuestionLifecycle:
    """2. Full Question Lifecycle with C Language"""

    def test_full_lifecycle_create_edit_publish_snapshot(self, admin_user, student_user, api_client):
        # A. Create question with C
        q, v1 = QuestionService.create_question(
            actor=admin_user,
            question_type=QuestionType.CODING,
            title="C Two Sum Problem",
            description="Given two integers, compute their sum.",
            instructions="Output sum of two integers.",
            points=10,
            coding_config_data={
                "problem_statement": "Given two integers, compute their sum.",
                "constraints": "1 <= a, b <= 10^4",
                "allowed_languages": ["C", "PYTHON"],
                "starter_codes": {
                    "C": "#include <stdio.h>\n",
                    "PYTHON": "def solve():\n"
                },
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "examples": [{"input": "2 3", "output": "5", "explanation": "2+3=5"}]
            },
            test_cases_data=[
                {"case_id": "TC01", "name": "TC01", "input_data": "2 3", "expected_output": "5", "points": 5, "is_hidden": False, "is_example": True},
                {"case_id": "TC02", "name": "TC02", "input_data": "10 20", "expected_output": "30", "points": 5, "is_hidden": True, "is_example": False}
            ]
        )

        assert q.question_type == QuestionType.CODING
        assert v1.status == VersionStatus.DRAFT
        c_cfg = v1.coding_config
        assert "C" in c_cfg.allowed_languages
        assert c_cfg.starter_codes["C"] == "#include <stdio.h>\n"
        assert c_cfg.test_cases.count() == 2

        # B. Edit draft question
        QuestionService.update_draft_version(
            version=v1,
            title="C Two Sum Problem (Updated)",
            description="Given two integers A and B, print A + B.",
            coding_config_data={
                "problem_statement": "Given two integers A and B, print A + B.",
                "constraints": "-10^5 <= a, b <= 10^5",
                "allowed_languages": ["C", "PYTHON", "CPP"],
                "starter_codes": {
                    "C": "#include <stdio.h>\n",
                    "PYTHON": "def solve():\n",
                    "CPP": "#include <bits/stdc++.h>\n"
                },
                "time_limit_ms": 1500,
                "memory_limit_mb": 128,
                "examples": [{"input": "4 6", "output": "10", "explanation": ""}]
            },
            test_cases_data=[
                {"name": "TC01", "input_data": "4 6", "expected_output": "10", "points": 5, "is_hidden": False, "is_example": True},
                {"name": "TC02", "input_data": "-5 5", "expected_output": "0", "points": 5, "is_hidden": True, "is_example": False}
            ],
            actor=admin_user
        )
        v1.refresh_from_db()
        assert v1.title == "C Two Sum Problem (Updated)"
        assert "CPP" in v1.coding_config.allowed_languages
        assert "C" in v1.coding_config.allowed_languages
        assert v1.coding_config.time_limit_ms == 1500

        # C. Health check passes 11/11 DATA checks
        health = CodingQuestionValidationService.get_health_status(v1)
        assert health["is_data_ready"] is True
        assert health["passed_data_checks"] == 11
        assert health["total_data_checks"] == 11
        assert len(health["errors"]) == 0

        # D. Publish Question Version
        QuestionService.publish_version(version=v1, actor=admin_user)
        v1.refresh_from_db()
        assert v1.status == VersionStatus.PUBLISHED

        # E. Immutability verification
        with pytest.raises(PermissionDenied) as excinfo:
            QuestionService.update_draft_version(
                version=v1,
                title="Attempt Mutation",
                actor=admin_user
            )
        assert "Only DRAFT versions can be modified" in str(excinfo.value)

        # F. Assessment Snapshot creation
        assessment = Assessment.objects.create(
            title="C Programming Assessment",
            duration_minutes=60,
            total_points=10,
            passing_percentage=40,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timedelta(hours=2),
            created_by=admin_user,
            status=AssessmentStatus.DRAFT
        )
        AssessmentService.add_question_to_assessment(str(assessment.id), str(v1.id), points=10, actor=admin_user)
        snapshot = AssessmentSnapshotService.create_snapshot(assessment=assessment, actor=admin_user)
        assessment.active_snapshot = snapshot
        assessment.status = AssessmentStatus.PUBLISHED
        assessment.save()

        # Snapshot contains C starter code and public test case, but NO hidden test case
        snap_q = snapshot.snapshot_data["questions"][0]
        assert snap_q["title"] == "C Two Sum Problem (Updated)"
        coding_conf = snap_q["coding_config"]
        assert "C" in coding_conf["allowed_languages"]
        assert coding_conf["starter_codes"]["C"] == "#include <stdio.h>\n"

        # Public tests exposed, hidden tests excluded
        public_tcs = coding_conf.get("public_test_cases", [])
        assert len(public_tcs) == 1
        assert public_tcs[0]["input_data"] == "4 6"
        assert "hidden" not in public_tcs[0] or public_tcs[0].get("is_hidden") is False


@pytest.mark.live_judge0
@pytest.mark.django_db
class TestMultiLanguageCompleteProgramExecutionParity:
    """3. Multi-Language Complete Program Execution Parity (A + B Problem)"""

    def test_c_complete_program_execution(self):
        c_code = """#include <stdio.h>

int main() {
    int a, b;
    if (scanf("%d %d", &a, &b) == 2) {
        printf("%d\\n", a + b);
    }
    return 0;
}
"""
        req = ExecutionRequest(
            language="C",
            source_code=c_code,
            stdin="15 27",
            expected_output="42",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "42"

    def test_python_complete_program_execution(self):
        py_code = """import sys

def solve():
    parts = sys.stdin.read().split()
    if len(parts) >= 2:
        print(int(parts[0]) + int(parts[1]))

if __name__ == '__main__':
    solve()
"""
        req = ExecutionRequest(
            language="PYTHON",
            source_code=py_code,
            stdin="15 27",
            expected_output="42",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "42"

    def test_cpp_complete_program_execution(self):
        cpp_code = """#include <iostream>
using namespace std;

int main() {
    int a, b;
    if (cin >> a >> b) {
        cout << (a + b) << endl;
    }
    return 0;
}
"""
        req = ExecutionRequest(
            language="CPP",
            source_code=cpp_code,
            stdin="15 27",
            expected_output="42",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "42"

    def test_java_complete_program_execution(self):
        java_code = """import java.util.Scanner;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNextInt()) {
            int a = sc.nextInt();
            int b = sc.nextInt();
            System.out.println(a + b);
        }
    }
}
"""
        req = ExecutionRequest(
            language="JAVA",
            source_code=java_code,
            stdin="15 27",
            expected_output="42",
            cpu_time_limit_ms=3000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "42"


@pytest.mark.live_judge0
@pytest.mark.django_db
class TestCEvaluationAndLimits:
    """4. C Evaluation & Limits (ACCEPTED, WRONG_ANSWER, COMPILATION_ERROR, RUNTIME_ERROR, TIME_LIMIT_EXCEEDED)"""

    def test_c_accepted_verdict(self):
        source = """#include <stdio.h>
int main() {
    printf("Correct output\\n");
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="Correct output",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "Correct output"

    def test_c_wrong_answer_verdict(self, admin_user, api_client):
        api_client.force_authenticate(user=admin_user)
        res = api_client.post(
            "/api/v1/admin/questions/run-sandbox/",
            data={
                "language": "c",
                "source_code": '#include <stdio.h>\nint main() { printf("Wrong output\\n"); return 0; }',
                "stdin": "",
                "expected_output": "Expected something else",
                "time_limit_ms": 2000,
                "memory_limit_mb": 256
            },
            format="json"
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "SUCCESS"
        assert data["passed"] is False
        assert OutputComparisonService.compare(data["stdout"], "Expected something else") is False

    def test_c_compilation_error_verdict(self):
        source = """#include <stdio.h>
int main() {
    this_is_a_syntax_error;
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
        assert "error:" in res.compile_output

    def test_c_runtime_error_verdict(self):
        source = """#include <stdio.h>
int main() {
    int x = 0;
    int y = 10 / x;
    printf("%d\\n", y);
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

    def test_c_time_limit_exceeded_verdict(self):
        source = """#include <stdio.h>
int main() {
    while (1) {
        // infinite loop
    }
    return 0;
}"""
        req = ExecutionRequest(
            language="c",
            source_code=source,
            stdin="",
            expected_output="",
            cpu_time_limit_ms=1000,
            memory_limit_mb=128
        )
        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.TIME_LIMIT.value


@pytest.mark.django_db
class TestExistingQuestionPreservation:
    """5. Existing vs New Question Language Defaults Preservation"""

    def test_existing_question_preserves_allowed_languages_without_c(self, admin_user, api_client):
        # Create an existing question that only has PYTHON, CPP, JAVA
        q, v1 = QuestionService.create_question(
            actor=admin_user,
            question_type=QuestionType.CODING,
            title="Existing Legacy Question",
            description="Created prior to standalone C support",
            points=10,
            coding_config_data={
                "problem_statement": "Created prior to standalone C support",
                "allowed_languages": ["PYTHON", "CPP", "JAVA"],
                "starter_codes": {
                    "PYTHON": "def solve():\n",
                    "CPP": "#include <bits/stdc++.h>\n",
                    "JAVA": "import java.io.*;\n"
                },
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "examples": []
            },
            test_cases_data=[
                {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
            ]
        )

        api_client.force_authenticate(user=admin_user)
        detail_res = api_client.get(f"/api/v1/admin/questions/{q.id}/versions/{v1.version_number}/")
        assert detail_res.status_code == 200
        coding_cfg = detail_res.json()["data"]["coding_config"]
        # Strictly preserves original allowed_languages; C is NOT injected
        assert coding_cfg["allowed_languages"] == ["PYTHON", "CPP", "JAVA"]
        assert "C" not in coding_cfg["allowed_languages"]

        # Save an edit keeping the existing languages
        update_res = api_client.put(
            f"/api/v1/admin/questions/{q.id}/versions/{v1.version_number}/",
            data={
                "question_type": "CODING",
                "title": "Existing Legacy Question (Edited)",
                "description": "Still no C injected",
                "points": 10,
                "coding_config": {
                    "problem_statement": "Still no C injected",
                    "allowed_languages": ["PYTHON", "CPP", "JAVA"],
                    "starter_codes": {
                        "PYTHON": "def solve():\n",
                        "CPP": "#include <bits/stdc++.h>\n",
                        "JAVA": "import java.io.*;\n"
                    },
                    "time_limit_ms": 2000,
                    "memory_limit_mb": 256,
                    "examples": []
                },
                "test_cases": [
                    {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
                ]
            },
            format="json"
        )
        assert update_res.status_code == 200
        v1.refresh_from_db()
        assert v1.coding_config.allowed_languages == ["PYTHON", "CPP", "JAVA"]
        assert "C" not in v1.coding_config.allowed_languages

    def test_new_question_defaults_include_c(self, admin_user):
        # Create a brand new question with no explicit coding_config allowed_languages
        q, v1 = QuestionService.create_question(
            actor=admin_user,
            question_type=QuestionType.CODING,
            title="Brand New Question",
            description="Defaults should include C",
            points=10,
            coding_config_data={},
            test_cases_data=[
                {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
            ]
        )
        assert "C" in v1.coding_config.allowed_languages
        assert "PYTHON" in v1.coding_config.allowed_languages
        assert "CPP" in v1.coding_config.allowed_languages
        assert "JAVA" in v1.coding_config.allowed_languages


@pytest.mark.django_db
class TestPlatformImportNormalization:
    """6. Safe Platform Import Normalization for C Language"""

    def test_unambiguous_c_keys_normalized_to_c(self):
        for key in ("C", "c", "c99", "C99", "c11", "C11", "c_lang", "C_LANG"):
            langs, starters = CodingQuestionPayloadNormalizer.normalize_starter_codes_and_languages(
                raw_languages=[key],
                starter_data={key: "#include <stdio.h>\nint main() { return 0; }"}
            )
            assert CodingLanguage.C in langs
            assert CodingLanguage.C in starters
            assert starters[CodingLanguage.C] == "#include <stdio.h>\nint main() { return 0; }"

    def test_generic_toolchain_keys_not_mapped_to_c(self):
        for generic_key in ("gcc", "GCC", "clang", "CLANG", "toolchain"):
            langs, starters = CodingQuestionPayloadNormalizer.normalize_starter_codes_and_languages(
                raw_languages=[generic_key],
                starter_data={generic_key: "generic code"}
            )
            # Generic toolchains are NOT mapped to C
            assert CodingLanguage.C not in starters
