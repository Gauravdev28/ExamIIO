import ast
import pytest
from apps.questions.services import QuestionService
from apps.questions.models import QuestionType, CodingLanguage
from apps.evaluator.services import CodeExecutionService, ExecutionRequest, ExecutionStatus

EXPECTED_PYTHON_DEFAULT_STARTER = "def solve():\n    pass\n"
EXPECTED_CPP_DEFAULT_STARTER = "#include <bits/stdc++.h>\n"
EXPECTED_JAVA_DEFAULT_STARTER = "import java.io.*;\n"
EXPECTED_C_DEFAULT_STARTER = "#include <stdio.h>\n"


class TestStarterCodesRegression:
    """Regression tests for default starter codes, syntax validity, and custom preservation."""

    def test_default_python_starter_syntax_and_exact_content(self):
        """1. Default Python starter must be exact string 'def solve():\\n    pass\\n' and syntactically valid."""
        # Check AST parsing - must not raise SyntaxError or IndentationError
        parsed_ast = ast.parse(EXPECTED_PYTHON_DEFAULT_STARTER)
        assert len(parsed_ast.body) == 1
        func_def = parsed_ast.body[0]
        assert isinstance(func_def, ast.FunctionDef)
        assert func_def.name == "solve"
        assert len(func_def.body) == 1
        assert isinstance(func_def.body[0], ast.Pass)

        # Check Python compilation
        compiled = compile(EXPECTED_PYTHON_DEFAULT_STARTER, "<test>", "exec")
        assert compiled is not None

        # Check execution does not raise IndentationError
        namespace = {}
        exec(compiled, namespace)
        assert "solve" in namespace
        assert callable(namespace["solve"])
        assert namespace["solve"]() is None

    @pytest.mark.django_db
    def test_supported_languages_api_returns_correct_default_starters(self, admin_user, api_client):
        """2. Supported languages API endpoint returns updated Python starter and existing C/C++/Java starters."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/admin/questions/languages/")
        assert response.status_code == 200

        data = response.json()["data"]
        langs = {lang["key"]: lang["default_starter_code"] for lang in data["languages"]}

        assert langs["PYTHON"] == EXPECTED_PYTHON_DEFAULT_STARTER
        assert langs["CPP"] == EXPECTED_CPP_DEFAULT_STARTER
        assert langs["JAVA"] == EXPECTED_JAVA_DEFAULT_STARTER
        assert langs["C"] == EXPECTED_C_DEFAULT_STARTER

    @pytest.mark.django_db
    def test_question_service_uses_default_starters_when_unspecified(self, admin_user):
        """3. QuestionService assigns default starter templates when not provided by author."""
        q, v1 = QuestionService.create_question(
            actor=admin_user,
            question_type=QuestionType.CODING,
            title="Auto Starter Question",
            description="Testing default starters injection",
            points=10,
            coding_config_data={
                "problem_statement": "Testing default starters",
                "allowed_languages": ["PYTHON", "CPP", "JAVA", "C"],
                # starter_codes left completely empty
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "examples": []
            },
            test_cases_data=[
                {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
            ]
        )

        starter_codes = v1.coding_config.starter_codes
        assert starter_codes["PYTHON"] == EXPECTED_PYTHON_DEFAULT_STARTER
        assert starter_codes["CPP"] == EXPECTED_CPP_DEFAULT_STARTER
        assert starter_codes["JAVA"] == EXPECTED_JAVA_DEFAULT_STARTER
        assert starter_codes["C"] == EXPECTED_C_DEFAULT_STARTER

    @pytest.mark.django_db
    def test_existing_custom_python_starter_preserved(self, admin_user):
        """4. Custom starter codes authored by users must be preserved verbatim and not overwritten."""
        custom_python = "# Custom Author Template\ndef solve(nums):\n    # TODO: solve\n    return sum(nums)\n"
        custom_c = "/* Custom C */\n#include <stdio.h>\nint main() { return 0; }\n"

        q, v1 = QuestionService.create_question(
            actor=admin_user,
            question_type=QuestionType.CODING,
            title="Custom Starter Question",
            description="Testing custom starter preservation",
            points=10,
            coding_config_data={
                "problem_statement": "Testing custom starters",
                "allowed_languages": ["PYTHON", "C"],
                "starter_codes": {
                    "PYTHON": custom_python,
                    "C": custom_c
                },
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "examples": []
            },
            test_cases_data=[
                {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
            ]
        )

        assert v1.coding_config.starter_codes["PYTHON"] == custom_python
        assert v1.coding_config.starter_codes["C"] == custom_c

        # Update draft without touching starter codes - must still preserve custom code
        updated_v = QuestionService.update_draft_version(
            version=v1,
            title="Custom Starter Question (Renamed)",
            description="Updated description",
            coding_config_data={
                "problem_statement": "Testing custom starters updated",
                "allowed_languages": ["PYTHON", "C"],
                "starter_codes": {
                    "PYTHON": custom_python,
                    "C": custom_c
                },
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "examples": []
            },
            test_cases_data=[
                {"name": "TC01", "input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False, "is_example": True}
            ],
            actor=admin_user
        )

        assert updated_v.coding_config.starter_codes["PYTHON"] == custom_python
        assert updated_v.coding_config.starter_codes["C"] == custom_c

    def test_python_candidate_program_execution_with_default_starter(self):
        """5. Candidate program built on default starter code executes cleanly without IndentationError."""
        # Candidate code appends logic below or inside solve
        candidate_code = EXPECTED_PYTHON_DEFAULT_STARTER + "\nprint('Gaurav Agarwal')\n"

        req = ExecutionRequest(
            language="PYTHON",
            source_code=candidate_code,
            stdin="",
            expected_output="Gaurav Agarwal",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )

        res = CodeExecutionService.execute(req)
        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout.strip() == "Gaurav Agarwal"
