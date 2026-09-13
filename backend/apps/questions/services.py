import copy
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User
from apps.accounts.services import AuditService
from .models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    QuestionStatus,
    CodingLanguage,
    CodingQuestionConfig,
    TestCase,
    SQLQuestionConfig,
    Tag,
)

logger = logging.getLogger(__name__)

class QuestionValidationService:
    """
    Validation engine ensuring structural correctness, integrity, and scoring invariants
    across all 6 supported question types.
    """

    @classmethod
    def validate_for_publish(cls, version: QuestionVersion) -> None:
        """
        Validates complete question configuration prior to publication.
        Raises DRFValidationError if any invariant is violated.
        """
        errors: Dict[str, Any] = {}

        # 1. Base Metadata Validation
        if not version.title or not version.title.strip():
            errors['title'] = "Question title cannot be empty."

        if not version.description or not version.description.strip():
            errors['description'] = "Problem statement/description cannot be empty."

        if version.points < 1:
            errors['points'] = "Total points must be at least 1."

        if version.negative_marking_enabled:
            if version.negative_points < 0:
                errors['negative_points'] = "Negative points cannot be less than 0."
            elif version.negative_points > version.points:
                errors['negative_points'] = f"Negative marking penalty ({version.negative_points}) cannot exceed total question points ({version.points})."

        # 2. Invariant: question_type consistency
        if version.question_type != version.question.question_type:
            errors['question_type'] = (
                f"QuestionVersion type '{version.question_type}' must match parent Question type '{version.question.question_type}'."
            )

        # 3. Type-Specific Validation
        type_config = version.type_config or {}

        if version.question_type == QuestionType.MCQ:
            cls._validate_mcq(type_config, errors)

        elif version.question_type == QuestionType.MULTI_SELECT:
            cls._validate_multi_select(type_config, errors)

        elif version.question_type == QuestionType.TRUE_FALSE:
            cls._validate_true_false(type_config, errors)

        elif version.question_type == QuestionType.SHORT_ANSWER:
            cls._validate_short_answer(type_config, errors)

        elif version.question_type == QuestionType.CODING:
            cls._validate_coding(version, errors)

        elif version.question_type == QuestionType.SQL:
            cls._validate_sql(version, errors)

        if errors:
            raise DRFValidationError(errors)

    @staticmethod
    def _validate_mcq(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        options = type_config.get('options', [])
        correct_options = type_config.get('correct_options', [])

        if not isinstance(options, list) or len(options) < 2:
            errors['options'] = "MCQ questions must provide at least 2 options."
            return

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or not opt.get('id') or not str(opt.get('text', '')).strip():
                errors['options'] = f"Option at index {idx} must have non-empty 'id' and 'text'."
                return
            opt_id = str(opt['id']).strip()
            if opt_id in option_ids:
                errors['options'] = f"Duplicate option ID '{opt_id}' detected."
                return
            option_ids.add(opt_id)

        if not isinstance(correct_options, list) or len(correct_options) != 1:
            errors['correct_options'] = "MCQ questions must have exactly one correct option selected."
            return

        selected_id = str(correct_options[0]).strip()
        if selected_id not in option_ids:
            errors['correct_options'] = f"Selected correct option '{selected_id}' does not exist in options."

    @staticmethod
    def _validate_multi_select(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        options = type_config.get('options', [])
        correct_options = type_config.get('correct_options', [])

        if not isinstance(options, list) or len(options) < 2:
            errors['options'] = "Multi-Select questions must provide at least 2 options."
            return

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or not opt.get('id') or not str(opt.get('text', '')).strip():
                errors['options'] = f"Option at index {idx} must have non-empty 'id' and 'text'."
                return
            opt_id = str(opt['id']).strip()
            if opt_id in option_ids:
                errors['options'] = f"Duplicate option ID '{opt_id}' detected."
                return
            option_ids.add(opt_id)

        if not isinstance(correct_options, list) or len(correct_options) < 1:
            errors['correct_options'] = "Multi-Select questions must specify at least one correct option."
            return

        for corr_id in correct_options:
            if str(corr_id).strip() not in option_ids:
                errors['correct_options'] = f"Selected correct option '{corr_id}' does not exist in options."
                return

    @staticmethod
    def _validate_true_false(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        if 'correct_answer' not in type_config or not isinstance(type_config['correct_answer'], bool):
            errors['correct_answer'] = "True/False questions must have 'correct_answer' set to true or false."

    @staticmethod
    def _validate_short_answer(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        accepted = type_config.get('accepted_answers', [])
        if not isinstance(accepted, list) or len(accepted) < 1:
            errors['accepted_answers'] = "Short Answer questions must provide at least one accepted answer string."
            return

        for item in accepted:
            if not isinstance(item, str) or not item.strip():
                errors['accepted_answers'] = "Accepted answer tokens cannot be empty."
                return

    @staticmethod
    def _validate_coding(version: QuestionVersion, errors: Dict[str, Any]) -> None:
        if not hasattr(version, 'coding_config') or version.coding_config is None:
            errors['coding_config'] = "Coding question is missing coding configuration."
            return

        config = version.coding_config
        if not config.problem_statement or not config.problem_statement.strip():
            errors['problem_statement'] = "Coding problem statement cannot be empty."

        allowed = config.allowed_languages or []
        valid_langs = [c[0] for c in CodingLanguage.choices]
        if not isinstance(allowed, list) or len(allowed) < 1:
            errors['allowed_languages'] = f"At least one allowed language must be specified from {valid_langs}."
        else:
            invalid = [l for l in allowed if l not in valid_langs]
            if invalid:
                errors['allowed_languages'] = f"Invalid languages specified: {invalid}. Supported: {valid_langs}."

        test_cases = list(config.test_cases.all())
        if not test_cases:
            errors['test_cases'] = "Coding question must have at least one test case before publication."
            return

        # Critical Invariant: SUM(test_cases.points) == version.points
        total_tc_points = sum(tc.points for tc in test_cases)
        if total_tc_points != version.points:
            errors['test_cases'] = (
                f"Sum of test case points ({total_tc_points}) must equal total question points ({version.points})."
            )

        # Check for empty expected outputs
        for tc in test_cases:
            if tc.expected_output is None or not str(tc.expected_output).strip():
                errors['expected_outputs'] = f"Test case at execution order {tc.execution_order} has empty expected output."
                break

        # Duplicate inputs check using canonical normalization
        is_no_input = CodingQuestionValidationService.is_no_input_question(config, test_cases)
        from apps.questions.canonical import normalize_input_for_duplicate_check
        seen_inputs = {}
        for tc in test_cases:
            norm_in = normalize_input_for_duplicate_check(tc.input_data)
            if is_no_input and norm_in == "":
                continue
            if norm_in in seen_inputs:
                errors['duplicate_inputs'] = "Duplicate test case input detected."
                break
            seen_inputs[norm_in] = tc.id

        # Backward compatibility handling at the publish boundary for legacy test data
        is_legacy = (
            not config.reference_solutions
            and not config.starter_codes
            and not config.examples
            and not any(tc.is_verified for tc in test_cases)
            and not any(tc.name for tc in test_cases)
        )

        if not is_legacy:
            # Check for unverified test cases
            unverified = [tc for tc in test_cases if not tc.is_verified]
            if unverified:
                errors['expected_output_verification'] = (
                    f"{len(unverified)} test case(s) require explicit expected output verification before publication."
                )

            # Model A: If reference solution is configured, it must be verified and not stale
            has_ref = bool(config.reference_solutions and isinstance(config.reference_solutions, dict) and any(str(v).strip() for v in config.reference_solutions.values()))
            if has_ref:
                if not config.reference_solution_verified:
                    errors['reference_solution'] = (
                        "Reference solution must be verified against all test cases before publication."
                    )
                elif not config.is_reference_solution_current():
                    errors['reference_solution'] = (
                        "Reference solution verification is stale; source or language changed. Re-execution and reverification required."
                    )

    @staticmethod
    def _validate_sql(version: QuestionVersion, errors: Dict[str, Any]) -> None:
        if not hasattr(version, 'sql_config') or version.sql_config is None:
            errors['sql_config'] = "SQL question is missing SQL configuration."
            return

        config = version.sql_config
        if not config.problem_statement or not config.problem_statement.strip():
            errors['problem_statement'] = "SQL problem statement cannot be empty."

        if not config.schema_setup_sql or not config.schema_setup_sql.strip():
            errors['schema_setup_sql'] = "SQL schema setup DDL/DML cannot be empty."

        if not config.expected_result_definition or not config.expected_result_definition.strip():
            errors['expected_result_definition'] = "SQL expected result definition cannot be empty."

        if config.allowed_dialect != "MYSQL":
            errors['allowed_dialect'] = "Currently only 'MYSQL' dialect is supported."


class CodingQuestionValidationService:
    """
    Central authoritative Question Health & Pre-Publish Validation service.
    Evaluates exactly 12 deterministic checks across authoring models A and B.
    """
    @classmethod
    def is_no_input_question(cls, config, test_cases=None) -> bool:
        """
        Determines if a coding question is a NO-INPUT question (takes no stdin).
        Evaluates constraints, input_description, problem_statement, test cases, and examples.
        """
        if not config:
            return False

        tcs = test_cases if test_cases is not None else (list(config.test_cases.all()) if hasattr(config, 'test_cases') else [])

        # If any test case has non-empty input, it is definitively an INPUT-BASED question
        if tcs and any(tc.input_data and str(tc.input_data).strip() != "" for tc in tcs):
            return False

        constraints = str(getattr(config, 'constraints', '') or '').lower()
        input_desc = str(getattr(config, 'input_description', '') or '').lower()
        problem_stmt = str(getattr(config, 'problem_statement', '') or '').lower()

        no_input_indicators = [
            'no input',
            'no stdin',
            'input is not required',
            'no input is required',
            'without input',
            'takes no input',
            'does not take any input',
            'does not require input',
            'does not require any input',
        ]

        for ind in no_input_indicators:
            if ind in constraints or ind in input_desc or ind in problem_stmt:
                return True

        # Check if all test cases have empty input and non-empty expected output
        if tcs and all(not tc.input_data or str(tc.input_data).strip() == "" for tc in tcs) and any(tc.expected_output and str(tc.expected_output).strip() != "" for tc in tcs):
            return True

        return False

    @classmethod
    def get_health_status(cls, version: QuestionVersion) -> Dict[str, Any]:
        from apps.evaluator.services import CodeExecutionService, OutputComparisonService

        checks = []
        errors = []

        if version.question_type != QuestionType.CODING:
            return {
                "is_ready": False,
                "status": version.status,
                "passed_checks": 0,
                "total_checks": 12,
                "checks": [],
                "errors": ["Question is not a CODING question."]
            }

        config = getattr(version, 'coding_config', None)
        if not config:
            return {
                "is_ready": False,
                "status": "DRAFT_INCOMPLETE",
                "passed_checks": 0,
                "total_checks": 12,
                "checks": [],
                "errors": ["Missing CodingQuestionConfig."]
            }

        test_cases = list(config.test_cases.all())
        is_no_input = cls.is_no_input_question(config, test_cases)

        # 1. Problem Statement (DATA)
        p_passed = bool(version.title and version.title.strip() and (config.problem_statement and config.problem_statement.strip() or version.description and version.description.strip()))
        p_msg = "Problem statement is complete" if p_passed else "Title or problem statement cannot be empty"
        p_action = "" if p_passed else "Add a question title and complete problem statement."
        checks.append({
            "key": "problem_statement",
            "display_name": "Problem Statement",
            "category": "DATA",
            "passed": p_passed,
            "status": "PASS" if p_passed else "ERROR",
            "message": p_msg,
            "suggested_action": p_action
        })
        if not p_passed:
            errors.append(p_msg)

        # 2. Examples (DATA)
        ex_list = config.examples if isinstance(config.examples, list) else []
        if is_no_input:
            ex_valid = len(ex_list) >= 1 and all(
                isinstance(ex, dict) and str(ex.get('output', '')).strip() != ""
                for ex in ex_list
            )
            ex_msg = f"{len(ex_list)} example(s) configured" if ex_valid else "No valid example with expected output was found."
            ex_action = "" if ex_valid else "Add at least one example with expected output in Problem Statement & Examples."
        else:
            ex_valid = len(ex_list) >= 1 and all(
                isinstance(ex, dict) and str(ex.get('input', '')).strip() != "" and str(ex.get('output', '')).strip() != ""
                for ex in ex_list
            )
            ex_msg = f"{len(ex_list)} example(s) configured" if ex_valid else "No valid example with both input and output was found."
            ex_action = "" if ex_valid else "Add at least one example with non-empty input and output in Problem Statement & Examples."

        checks.append({
            "key": "examples",
            "display_name": "Examples",
            "category": "DATA",
            "passed": ex_valid,
            "status": "PASS" if ex_valid else "ERROR",
            "message": ex_msg,
            "suggested_action": ex_action
        })
        if not ex_valid:
            errors.append(ex_msg)

        # 3. Languages (DATA)
        allowed_langs = config.allowed_languages or []
        valid_langs = [c[0] for c in CodingLanguage.choices]
        lang_valid = len(allowed_langs) >= 1 and all(l in valid_langs for l in allowed_langs)
        lang_msg = f"{len(allowed_langs)} language(s) enabled" if lang_valid else "At least one valid supported language required"
        lang_action = "" if lang_valid else "Select at least one supported language in Languages & Starter Code."
        checks.append({
            "key": "languages",
            "display_name": "Languages",
            "category": "DATA",
            "passed": lang_valid,
            "status": "PASS" if lang_valid else "ERROR",
            "message": lang_msg,
            "suggested_action": lang_action
        })
        if not lang_valid:
            errors.append(lang_msg)

        # 4. Starter Code (DATA)
        sc_dict = config.starter_codes if isinstance(config.starter_codes, dict) else {}
        missing_langs = [l for l in allowed_langs if not str(sc_dict.get(l, '')).strip()]
        sc_valid = lang_valid and (len(missing_langs) == 0)
        if sc_valid:
            sc_msg = "Starter code provided for all enabled languages"
            sc_action = ""
        elif missing_langs:
            sc_msg = f"Starter code missing for {', '.join(missing_langs)}"
            sc_action = f"Add starter code for {', '.join(missing_langs)} in Languages & Starter Code."
        else:
            sc_msg = "Starter code missing for one or more enabled languages"
            sc_action = "Provide starter code for all enabled languages."
        checks.append({
            "key": "starter_code",
            "display_name": "Starter Code",
            "category": "DATA",
            "passed": sc_valid,
            "status": "PASS" if sc_valid else "ERROR",
            "message": sc_msg,
            "suggested_action": sc_action
        })
        if not sc_valid:
            errors.append(sc_msg)

        # 5. Sample Tests (DATA)
        sample_tcs = [tc for tc in test_cases if not tc.is_hidden]
        s_valid = len(sample_tcs) >= 1 and all(tc.expected_output and tc.expected_output.strip() != "" for tc in sample_tcs)
        s_msg = f"{len(sample_tcs)} sample test(s) configured" if s_valid else "At least one sample test with expected output required"
        s_action = "" if s_valid else "Add at least one sample test case with expected output in Test Cases."
        checks.append({
            "key": "sample_tests",
            "display_name": "Sample Tests",
            "category": "DATA",
            "passed": s_valid,
            "status": "PASS" if s_valid else "ERROR",
            "message": s_msg,
            "suggested_action": s_action
        })
        if not s_valid:
            errors.append(s_msg)

        # 6. Hidden Tests (DATA)
        hidden_tcs = [tc for tc in test_cases if tc.is_hidden]
        h_valid = len(hidden_tcs) >= 1 and all(tc.expected_output and tc.expected_output.strip() != "" and tc.points >= 1 for tc in hidden_tcs)
        h_msg = f"{len(hidden_tcs)} hidden test(s) configured" if h_valid else "At least one hidden test with expected output and positive points required"
        h_action = "" if h_valid else "Add at least one hidden test case with expected output and at least 1 point in Test Cases."
        checks.append({
            "key": "hidden_tests",
            "display_name": "Hidden Tests",
            "category": "DATA",
            "passed": h_valid,
            "status": "PASS" if h_valid else "ERROR",
            "message": h_msg,
            "suggested_action": h_action
        })
        if not h_valid:
            errors.append(h_msg)

        # 7. Expected Output Verification (Check #7 - DATA)
        unverified_count = len([tc for tc in test_cases if not tc.is_verified])
        has_ref = bool(config.reference_solutions and isinstance(config.reference_solutions, dict) and any(str(v).strip() for v in config.reference_solutions.values()))

        if has_ref:
            # Model A
            if not config.reference_solution_verified:
                v_passed = False
                if config.reference_solution_hash:
                    v_msg = "Reference solution verification is stale; re-execution and review required"
                else:
                    v_msg = "Reference solution not verified against test cases"
                v_action = "Execute and verify reference solution against all test cases."
            elif not config.is_reference_solution_current():
                v_passed = False
                v_msg = "Reference solution verification is stale; re-execution and review required"
                v_action = "Re-execute reference solution to refresh verification hash."
            elif unverified_count > 0:
                v_passed = False
                v_msg = f"{unverified_count} test case(s) require verification"
                v_action = "Verify expected outputs for unverified test cases."
            else:
                v_passed = True
                v_msg = "Reference solution verified"
                v_action = ""
        else:
            # Model B
            if test_cases and unverified_count == 0:
                v_passed = True
                v_msg = "All expected outputs manually verified"
                v_action = ""
            else:
                v_passed = False
                v_msg = f"{unverified_count} test case(s) require manual verification" if test_cases else "No test cases to verify"
                v_action = "Verify all test cases or provide a reference solution to verify automatically."

        checks.append({
            "key": "expected_output_verification",
            "display_name": "Expected Output Verification",
            "category": "DATA",
            "passed": v_passed,
            "status": "PASS" if v_passed else "ERROR",
            "message": v_msg,
            "suggested_action": v_action
        })
        if not v_passed:
            errors.append(v_msg)

        # 8. Expected Outputs (DATA)
        eo_valid = len(test_cases) > 0 and all(tc.expected_output and str(tc.expected_output).strip() != "" for tc in test_cases)
        eo_msg = "All test cases have non-empty expected outputs" if eo_valid else "One or more test cases missing expected output"
        eo_action = "" if eo_valid else "Ensure all test cases have non-empty expected outputs."
        checks.append({
            "key": "expected_outputs",
            "display_name": "Expected Outputs",
            "category": "DATA",
            "passed": eo_valid,
            "status": "PASS" if eo_valid else "ERROR",
            "message": eo_msg,
            "suggested_action": eo_action
        })
        if not eo_valid:
            errors.append(eo_msg)

        # 9. Execution Sandbox (ENVIRONMENT - Execution Infrastructure Health)
        sb_avail = CodeExecutionService.check_health()
        if sb_avail:
            sb_status = "PASS"
            sb_msg = "Code execution sandbox operational"
            sb_action = ""
        else:
            sb_status = "ENVIRONMENT"
            sb_msg = "Code execution sandbox is currently unreachable. Ensure the Piston execution engine is running at port 2000."
            sb_action = "Start or connect to the isolated Piston code execution sandbox."
        checks.append({
            "key": "sandbox_execution",
            "display_name": "Execution Sandbox",
            "category": "ENVIRONMENT",
            "passed": sb_avail,
            "status": sb_status,
            "message": sb_msg,
            "suggested_action": sb_action
        })
        if not sb_avail:
            errors.append(sb_msg)

        # 10. Scoring Configuration (DATA)
        sc_pts_valid = len(test_cases) > 0 and all(tc.points >= 1 for tc in test_cases) and config.time_limit_ms >= 100 and config.memory_limit_mb >= 16
        sc_pts_msg = "Scoring configuration valid" if sc_pts_valid else "Invalid scoring points or resource limits"
        sc_pts_action = "" if sc_pts_valid else "Ensure test case points are positive and execution limits are valid."
        checks.append({
            "key": "scoring_configuration",
            "display_name": "Scoring Configuration",
            "category": "DATA",
            "passed": sc_pts_valid,
            "status": "PASS" if sc_pts_valid else "ERROR",
            "message": sc_pts_msg,
            "suggested_action": sc_pts_action
        })
        if not sc_pts_valid:
            errors.append(sc_pts_msg)

        # 11. Point Sum Invariant (DATA)
        tc_pts = sum(tc.points for tc in test_cases)
        psi_valid = (tc_pts == version.points)
        psi_msg = f"Test case points sum ({tc_pts}) matches total points ({version.points})" if psi_valid else f"Test case points ({tc_pts}) do not equal question points ({version.points})"
        psi_action = "" if psi_valid else f"Adjust test case points so their sum matches total question points ({version.points})."
        checks.append({
            "key": "point_sum_invariant",
            "display_name": "Point Sum Invariant",
            "category": "DATA",
            "passed": psi_valid,
            "status": "PASS" if psi_valid else "ERROR",
            "message": psi_msg,
            "suggested_action": psi_action
        })
        if not psi_valid:
            errors.append(psi_msg)

        # 12. Duplicate Inputs (DATA)
        from apps.questions.canonical import normalize_input_for_duplicate_check
        seen_inputs = set()
        has_duplicate = False
        for tc in test_cases:
            norm_in = normalize_input_for_duplicate_check(tc.input_data)
            if is_no_input and norm_in == "":
                continue
            if norm_in in seen_inputs:
                has_duplicate = True
                break
            seen_inputs.add(norm_in)
        dup_valid = not has_duplicate
        dup_msg = "No duplicate test case inputs" if dup_valid else "Duplicate test case inputs detected"
        dup_action = "" if dup_valid else "Modify duplicate test case inputs to ensure unique evaluation vectors."
        checks.append({
            "key": "duplicate_inputs",
            "display_name": "Duplicate Inputs",
            "category": "DATA",
            "passed": dup_valid,
            "status": "PASS" if dup_valid else "ERROR",
            "message": dup_msg,
            "suggested_action": dup_action
        })
        if not dup_valid:
            errors.append(dup_msg)

        # Separate 11 DATA checks from 1 ENVIRONMENT check
        data_checks = [c for c in checks if c["category"] == "DATA"]
        passed_data_checks = sum(1 for c in data_checks if c["passed"])
        total_data_checks = len(data_checks)  # exactly 11
        is_data_ready = (passed_data_checks == total_data_checks)
        environment_ready = bool(sb_avail)

        passed_count = sum(1 for c in checks if c["passed"])
        is_ready = (passed_count == 12)

        if version.status == VersionStatus.PUBLISHED:
            calc_status = "PUBLISHED"
        elif version.status == VersionStatus.ARCHIVED:
            calc_status = "ARCHIVED"
        elif is_ready:
            calc_status = "DRAFT_READY"
        elif is_data_ready:
            calc_status = "DRAFT_DATA_READY"
        else:
            calc_status = "DRAFT_INCOMPLETE"

        return {
            "is_ready": is_ready,
            "is_data_ready": is_data_ready,
            "environment_ready": environment_ready,
            "status": calc_status,
            "passed_checks": passed_count,
            "total_checks": 12,
            "passed_data_checks": passed_data_checks,
            "total_data_checks": total_data_checks,
            "checks": checks,
            "errors": errors
        }


class QuestionService:
    """
    Domain service orchestrating Question and QuestionVersion lifecycles,
    deep cloning, publishing transactions, and immutability guarantees.
    """

    @classmethod
    def create_question(
        cls,
        question_type: str,
        title: str,
        description: str,
        instructions: str = "",
        points: int = 10,
        negative_marking_enabled: bool = False,
        negative_points: int = 0,
        difficulty: str = Difficulty.MEDIUM,
        tags: Optional[List[str]] = None,
        type_config: Optional[Dict[str, Any]] = None,
        coding_config_data: Optional[Dict[str, Any]] = None,
        test_cases_data: Optional[List[Dict[str, Any]]] = None,
        sql_config_data: Optional[Dict[str, Any]] = None,
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[Question, QuestionVersion]:
        """
        Atomically creates a new logical Question and its initial Version 1 Draft.
        """
        valid_types = [t[0] for t in QuestionType.choices]
        if question_type not in valid_types:
            raise DRFValidationError({"question_type": f"Invalid question type '{question_type}'. Supported: {valid_types}"})

        valid_diffs = [d[0] for d in Difficulty.choices]
        if difficulty not in valid_diffs:
            raise DRFValidationError({"difficulty": f"Invalid difficulty '{difficulty}'. Supported: {valid_diffs}"})

        if points < 1:
            raise DRFValidationError({"points": "Total points must be at least 1."})

        if negative_marking_enabled and (negative_points < 0 or negative_points > points):
            raise DRFValidationError({"negative_points": f"Negative points ({negative_points}) cannot exceed total points ({points})."})

        # Fallback to type_config for test_cases or coding parameters if not passed separately
        if type_config:
            if not test_cases_data and 'test_cases' in type_config:
                test_cases_data = type_config.get('test_cases')
            if not coding_config_data:
                coding_config_data = {
                    k: v for k, v in type_config.items() if k not in ['test_cases', 'tags', 'options']
                }

        # Shared Canonical Validation for MCQ and CODING
        if question_type in [QuestionType.MCQ, QuestionType.CODING]:
            from apps.questions.canonical import (
                CanonicalQuestionDTO,
                CanonicalOptionDTO,
                CanonicalCodingConfigDTO,
                CanonicalTestCaseDTO,
                validate_and_normalize_canonical_question
            )
            raw_options = []
            if question_type == QuestionType.MCQ and type_config and 'options' in type_config:
                corr_list = type_config.get('correct_options', [])
                corr_single = type_config.get('correct_option', '')
                for o in type_config['options']:
                    o_id = o.get('id') or o.get('key')
                    is_c = bool(o.get('is_correct') or (o_id in corr_list) or (o_id == corr_single))
                    raw_options.append(CanonicalOptionDTO(
                        option_key=str(o_id),
                        option_text=str(o.get('text', '')),
                        is_correct=is_c
                    ))

            raw_coding = None
            raw_tcs = []
            statement_val = description
            if question_type == QuestionType.CODING:
                c_d = coding_config_data or {}
                if c_d.get('problem_statement'):
                    statement_val = c_d.get('problem_statement')

                allowed_langs = c_d.get('allowed_languages', ['PYTHON', 'CPP', 'JAVA', 'C'])
                default_starters = {
                    "PYTHON": "def solve():\n    pass\n",
                    "CPP": "#include <bits/stdc++.h>\n",
                    "JAVA": "import java.io.*;\n",
                    "C": "#include <stdio.h>\n"
                }
                final_starters = dict(c_d.get('starter_codes') or {})
                for l in allowed_langs:
                    l_upper = str(l).strip().upper()
                    if l_upper not in final_starters and l_upper.lower() not in final_starters:
                        final_starters[l_upper] = default_starters.get(l_upper, f"// Starter code for {l_upper}\n")

                raw_coding = CanonicalCodingConfigDTO(
                    languages=allowed_langs,
                    starter_codes=final_starters,
                    constraints=c_d.get('constraints', ''),
                    execution_time_ms=c_d.get('time_limit_ms', 2000),
                    memory_mb=c_d.get('memory_limit_mb', 256),
                    examples=c_d.get('examples', [])
                )
                for idx, tc in enumerate(test_cases_data or []):
                    is_ver = tc.get('is_verified')
                    if is_ver is None:
                        is_ver = True
                    inp_val = tc.get('input_data') if tc.get('input_data') is not None else tc.get('input', '')
                    raw_tcs.append(CanonicalTestCaseDTO(
                        case_id=tc.get('name') or f"TC{idx+1:02d}",
                        visibility="HIDDEN" if tc.get('is_hidden') else "SAMPLE",
                        input=inp_val,
                        expected_output=tc.get('expected_output', ''),
                        points=tc.get('points', 1),
                        is_example=bool(tc.get('is_example', False)),
                        is_verified=bool(is_ver)
                    ))

            clean_title = (title or "").strip() or "Untitled Question"
            clean_statement = (statement_val or "").strip() or "Draft question statement"

            canon_dto = CanonicalQuestionDTO(
                question_id="MANUAL",
                title=clean_title,
                type=question_type,
                statement=clean_statement,
                instructions=instructions or "",
                difficulty=difficulty,
                points=points,
                negative_points=negative_points if negative_marking_enabled else 0,
                options=raw_options,
                coding=raw_coding,
                test_cases=raw_tcs
            )
            norm_dto, c_errors, c_warnings = validate_and_normalize_canonical_question(canon_dto)
            draft_allowed_patterns = [
                "Question title is required and cannot be empty",
                "Question statement/prompt is required and cannot be empty",
                "none was marked correct",
                "MCQ question requires at least 2 options",
                "Coding question must have at least one test case",
                "Coding question must have at least one hidden test case",
                "All test cases must be verified",
                "At least one hidden test case",
                "Coding question configuration is missing",
            ]
            real_errors = [
                e for e in c_errors
                if not any(pattern in e for pattern in draft_allowed_patterns)
            ]
            if real_errors:
                raise DRFValidationError({"detail": real_errors[0], "errors": real_errors})

            title = norm_dto.title if norm_dto else clean_title
            description = norm_dto.statement if norm_dto else clean_statement
            instructions = norm_dto.instructions if norm_dto else (instructions or "")
            difficulty = norm_dto.difficulty if norm_dto else difficulty
            points = norm_dto.points if norm_dto else points
            negative_points = norm_dto.negative_points if norm_dto else negative_points

            if question_type == QuestionType.MCQ:
                final_opts = (norm_dto.options if norm_dto and norm_dto.options else raw_options)
                type_config = {
                    "options": [
                        {"id": opt.option_key, "text": opt.option_text, "is_correct": opt.is_correct}
                        for opt in final_opts
                    ],
                    "correct_options": [opt.option_key for opt in final_opts if opt.is_correct],
                    "correct_option": next((opt.option_key for opt in final_opts if opt.is_correct), "")
                }
            elif question_type == QuestionType.CODING:
                if coding_config_data is None:
                    coding_config_data = {}
                coding_config_data['problem_statement'] = norm_dto.statement if norm_dto else clean_statement
                coding_config_data['constraints'] = norm_dto.coding.constraints if (norm_dto and norm_dto.coding) else ''
                coding_config_data['allowed_languages'] = norm_dto.coding.languages if (norm_dto and norm_dto.coding) else ['PYTHON']
                coding_config_data['time_limit_ms'] = norm_dto.coding.execution_time_ms if (norm_dto and norm_dto.coding) else 2000
                coding_config_data['memory_limit_mb'] = norm_dto.coding.memory_mb if (norm_dto and norm_dto.coding) else 256
                coding_config_data['starter_codes'] = norm_dto.coding.starter_codes if (norm_dto and norm_dto.coding) else {}
                coding_config_data['examples'] = norm_dto.coding.examples if (norm_dto and norm_dto.coding) else []

                orig_points_map = {}
                for idx, tc_in in enumerate(test_cases_data or []):
                    c_id = tc_in.get('name') or f"TC{idx+1:02d}"
                    if 'points' in tc_in:
                        orig_points_map[c_id] = tc_in['points']

                tcs_source = norm_dto.test_cases if (norm_dto and norm_dto.test_cases) else raw_tcs
                test_cases_data = [
                    {
                        "name": tc.case_id,
                        "input_data": tc.input,
                        "expected_output": tc.expected_output,
                        "points": orig_points_map.get(tc.case_id, tc.points),
                        "is_hidden": (tc.visibility == "HIDDEN"),
                        "is_verified": tc.is_verified,
                        "is_example": tc.is_example,
                        "execution_order": i + 1
                    }
                    for i, tc in enumerate(tcs_source)
                ]

        with transaction.atomic():
            question = Question.objects.create(
                question_type=question_type,
                status=QuestionStatus.ACTIVE,
                created_by=actor
            )

            version = QuestionVersion.objects.create(
                question=question,
                version_number=1,
                question_type=question_type,
                title=(title or "Untitled Question").strip() or "Untitled Question",
                description=(description or "").strip(),
                instructions=instructions.strip() if instructions else "",
                points=points,
                negative_marking_enabled=negative_marking_enabled,
                negative_points=negative_points,
                difficulty=difficulty,
                status=VersionStatus.DRAFT,
                type_config=type_config or {},
                created_by=actor
            )

            # Assign tags
            if tags:
                tag_objs = cls._resolve_tags(tags)
                version.tags.set(tag_objs)

            # Type-specific child configs
            if question_type == QuestionType.CODING:
                c_data = coding_config_data or {}
                coding_config = CodingQuestionConfig.objects.create(
                    question_version=version,
                    problem_statement=c_data.get('problem_statement', description),
                    input_description=c_data.get('input_description', ''),
                    output_description=c_data.get('output_description', ''),
                    constraints=c_data.get('constraints', ''),
                    allowed_languages=c_data.get('allowed_languages', [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA, CodingLanguage.C]),
                    time_limit_ms=c_data.get('time_limit_ms', 2000),
                    memory_limit_mb=c_data.get('memory_limit_mb', 256),
                    starter_codes=c_data.get('starter_codes', {}),
                    examples=c_data.get('examples', []),
                    reference_solutions=c_data.get('reference_solutions', {}),
                    reference_solution_language=c_data.get('reference_solution_language', ''),
                    reference_solution_hash=c_data.get('reference_solution_hash', ''),
                    reference_solution_verified=c_data.get('reference_solution_verified', False),
                    reference_solution_verified_at=c_data.get('reference_solution_verified_at')
                )

                if test_cases_data:
                    for tc_idx, tc_item in enumerate(test_cases_data, start=1):
                        exp_out = tc_item.get('expected_output', '')
                        is_ver = tc_item.get('is_verified')
                        if is_ver is None:
                            is_ver = bool(exp_out and str(exp_out).strip())
                        TestCase.objects.create(
                            coding_config=coding_config,
                            name=tc_item.get('name', ''),
                            input_data=tc_item.get('input_data', ''),
                            expected_output=exp_out,
                            points=tc_item.get('points', 1),
                            is_hidden=tc_item.get('is_hidden', False),
                            is_verified=is_ver,
                            execution_order=tc_item.get('execution_order', tc_idx),
                            time_limit_override_ms=tc_item.get('time_limit_override_ms'),
                            memory_limit_override_mb=tc_item.get('memory_limit_override_mb')
                        )

            elif question_type == QuestionType.SQL:
                s_data = sql_config_data or {}
                SQLQuestionConfig.objects.create(
                    question_version=version,
                    problem_statement=s_data.get('problem_statement', description),
                    schema_setup_sql=s_data.get('schema_setup_sql', ''),
                    expected_result_definition=s_data.get('expected_result_definition', ''),
                    allowed_dialect=s_data.get('allowed_dialect', 'MYSQL'),
                    time_limit_ms=s_data.get('time_limit_ms', 3000)
                )

            AuditService.log(
                action="QUESTION_CREATED",
                actor=actor,
                target_type="Question",
                target_id=str(question.id),
                metadata={
                    "question_id": str(question.id),
                    "version_number": 1,
                    "question_type": question_type,
                    "title": version.title,
                    "points": version.points
                },
                request=request
            )

        return question, version

    @classmethod
    def update_draft_version(
        cls,
        version: QuestionVersion,
        title: Optional[str] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        points: Optional[int] = None,
        negative_marking_enabled: Optional[bool] = None,
        negative_points: Optional[int] = None,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
        type_config: Optional[Dict[str, Any]] = None,
        coding_config_data: Optional[Dict[str, Any]] = None,
        test_cases_data: Optional[List[Dict[str, Any]]] = None,
        sql_config_data: Optional[Dict[str, Any]] = None,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Updates an existing DRAFT version. Rejects edits if version is PUBLISHED or ARCHIVED.
        """
        if version.status != VersionStatus.DRAFT:
            raise PermissionDenied(f"Cannot edit question version in '{version.status}' status. Only DRAFT versions can be modified.")

        with transaction.atomic():
            if title is not None:
                version.title = title.strip()
            if description is not None:
                version.description = description.strip()
            if instructions is not None:
                version.instructions = instructions.strip()
            if points is not None:
                if points < 1:
                    raise DRFValidationError({"points": "Total points must be at least 1."})
                version.points = points
            if negative_marking_enabled is not None:
                version.negative_marking_enabled = negative_marking_enabled
            if negative_points is not None:
                version.negative_points = negative_points
            if difficulty is not None:
                version.difficulty = difficulty
            if type_config is not None:
                version.type_config = type_config

            if version.negative_marking_enabled and (version.negative_points < 0 or version.negative_points > version.points):
                raise DRFValidationError({"negative_points": f"Negative penalty ({version.negative_points}) cannot exceed total points ({version.points})."})

            version.save()

            if tags is not None:
                tag_objs = cls._resolve_tags(tags)
                version.tags.set(tag_objs)

            # Update child configs
            if version.question_type == QuestionType.CODING:
                if coding_config_data is not None or test_cases_data is not None:
                    c_conf, _ = CodingQuestionConfig.objects.get_or_create(question_version=version)
                    if coding_config_data:
                        if 'problem_statement' in coding_config_data:
                            c_conf.problem_statement = coding_config_data['problem_statement']
                        if 'input_description' in coding_config_data:
                            c_conf.input_description = coding_config_data['input_description']
                        if 'output_description' in coding_config_data:
                            c_conf.output_description = coding_config_data['output_description']
                        if 'constraints' in coding_config_data:
                            c_conf.constraints = coding_config_data['constraints']
                        if 'allowed_languages' in coding_config_data:
                            c_conf.allowed_languages = coding_config_data['allowed_languages']
                        if 'time_limit_ms' in coding_config_data:
                            c_conf.time_limit_ms = coding_config_data['time_limit_ms']
                        if 'memory_limit_mb' in coding_config_data:
                            c_conf.memory_limit_mb = coding_config_data['memory_limit_mb']
                        if 'starter_codes' in coding_config_data:
                            c_conf.starter_codes = coding_config_data['starter_codes']
                        if 'examples' in coding_config_data:
                            c_conf.examples = coding_config_data['examples']
                        if 'reference_solutions' in coding_config_data:
                            c_conf.reference_solutions = coding_config_data['reference_solutions']
                        if 'reference_solution_language' in coding_config_data:
                            c_conf.reference_solution_language = coding_config_data['reference_solution_language']
                        if 'reference_solution_hash' in coding_config_data:
                            c_conf.reference_solution_hash = coding_config_data['reference_solution_hash']
                        if 'reference_solution_verified' in coding_config_data:
                            c_conf.reference_solution_verified = coding_config_data['reference_solution_verified']
                        if 'reference_solution_verified_at' in coding_config_data:
                            c_conf.reference_solution_verified_at = coding_config_data['reference_solution_verified_at']
                        c_conf.save()

                    if test_cases_data is not None:
                        # Replace draft test cases atomically
                        c_conf.test_cases.all().delete()
                        for tc_idx, tc_item in enumerate(test_cases_data, start=1):
                            exp_out = tc_item.get('expected_output', '')
                            is_ver = tc_item.get('is_verified')
                            if is_ver is None:
                                is_ver = bool(exp_out and str(exp_out).strip())
                            TestCase.objects.create(
                                coding_config=c_conf,
                                name=tc_item.get('name', ''),
                                input_data=tc_item.get('input_data', ''),
                                expected_output=exp_out,
                                points=tc_item.get('points', 1),
                                is_hidden=tc_item.get('is_hidden', False),
                                is_verified=is_ver,
                                execution_order=tc_item.get('execution_order', tc_idx),
                                time_limit_override_ms=tc_item.get('time_limit_override_ms'),
                                memory_limit_override_mb=tc_item.get('memory_limit_override_mb')
                            )

            elif version.question_type == QuestionType.SQL and sql_config_data is not None:
                s_conf, _ = SQLQuestionConfig.objects.get_or_create(question_version=version)
                if 'problem_statement' in sql_config_data:
                    s_conf.problem_statement = sql_config_data['problem_statement']
                if 'schema_setup_sql' in sql_config_data:
                    s_conf.schema_setup_sql = sql_config_data['schema_setup_sql']
                if 'expected_result_definition' in sql_config_data:
                    s_conf.expected_result_definition = sql_config_data['expected_result_definition']
                if 'allowed_dialect' in sql_config_data:
                    s_conf.allowed_dialect = sql_config_data['allowed_dialect']
                if 'time_limit_ms' in sql_config_data:
                    s_conf.time_limit_ms = sql_config_data['time_limit_ms']
                s_conf.save()

            AuditService.log(
                action="QUESTION_UPDATED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(version.question.id),
                    "version_number": version.version_number,
                    "title": version.title
                },
                request=request
            )

        return version

    @classmethod
    def create_new_version(
        cls,
        question: Union[Question, str],
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Creates a new sequential DRAFT version by performing a deep independent clone of the latest version.
        """
        if isinstance(question, str):
            question = Question.objects.get(id=question)

        with transaction.atomic():
            # Lock parent question row to prevent concurrent version number collision
            locked_question = Question.objects.select_for_update().get(id=question.id)
            latest_version = locked_question.versions.order_by('-version_number').first()

            if not latest_version:
                raise DRFValidationError("Cannot create a new version for a question without an existing version.")

            next_version_num = latest_version.version_number + 1

            # 1. Deep clone QuestionVersion row
            new_version = QuestionVersion.objects.create(
                question=locked_question,
                version_number=next_version_num,
                question_type=locked_question.question_type,
                title=latest_version.title,
                description=latest_version.description,
                instructions=latest_version.instructions,
                points=latest_version.points,
                negative_marking_enabled=latest_version.negative_marking_enabled,
                negative_points=latest_version.negative_points,
                difficulty=latest_version.difficulty,
                status=VersionStatus.DRAFT,
                type_config=copy.deepcopy(latest_version.type_config),
                created_by=actor
            )

            # Copy Tag relations
            new_version.tags.set(latest_version.tags.all())

            # 2. Deep clone Coding config & TestCases
            if locked_question.question_type == QuestionType.CODING and hasattr(latest_version, 'coding_config'):
                old_c = latest_version.coding_config
                new_c = CodingQuestionConfig.objects.create(
                    question_version=new_version,
                    problem_statement=old_c.problem_statement,
                    input_description=old_c.input_description,
                    output_description=old_c.output_description,
                    constraints=old_c.constraints,
                    allowed_languages=copy.deepcopy(old_c.allowed_languages),
                    time_limit_ms=old_c.time_limit_ms,
                    memory_limit_mb=old_c.memory_limit_mb,
                    starter_codes=copy.deepcopy(old_c.starter_codes or {}),
                    examples=copy.deepcopy(old_c.examples or []),
                    reference_solutions=copy.deepcopy(old_c.reference_solutions or {}),
                    reference_solution_language=old_c.reference_solution_language,
                    reference_solution_hash=old_c.reference_solution_hash,
                    reference_solution_verified=old_c.reference_solution_verified,
                    reference_solution_verified_at=old_c.reference_solution_verified_at
                )
                for tc in old_c.test_cases.all():
                    TestCase.objects.create(
                        coding_config=new_c,
                        name=tc.name,
                        input_data=tc.input_data,
                        expected_output=tc.expected_output,
                        points=tc.points,
                        is_hidden=tc.is_hidden,
                        is_verified=tc.is_verified,
                        execution_order=tc.execution_order,
                        time_limit_override_ms=tc.time_limit_override_ms,
                        memory_limit_override_mb=tc.memory_limit_override_mb
                    )

            # 3. Deep clone SQL config
            elif locked_question.question_type == QuestionType.SQL and hasattr(latest_version, 'sql_config'):
                old_s = latest_version.sql_config
                SQLQuestionConfig.objects.create(
                    question_version=new_version,
                    problem_statement=old_s.problem_statement,
                    schema_setup_sql=old_s.schema_setup_sql,
                    expected_result_definition=old_s.expected_result_definition,
                    allowed_dialect=old_s.allowed_dialect,
                    time_limit_ms=old_s.time_limit_ms
                )

            AuditService.log(
                action="QUESTION_VERSION_CREATED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(new_version.id),
                metadata={
                    "question_id": str(locked_question.id),
                    "version_number": next_version_num,
                    "cloned_from_version": latest_version.version_number
                },
                request=request
            )

        return new_version

    @classmethod
    def publish_version(
        cls,
        version_or_question_id: Any = None,
        version_number: Optional[int] = None,
        actor: Optional[User] = None,
        request=None,
        version: Optional[QuestionVersion] = None,
        **kwargs
    ) -> QuestionVersion:
        """
        Validates invariants and atomically publishes the question version.
        Accepts either a QuestionVersion instance or (question_id, version_number).
        Transitions any previous PUBLISHED version to ARCHIVED.
        """
        v_target = version if version is not None else (version_or_question_id if version_or_question_id is not None else kwargs.get('version'))
        if isinstance(v_target, QuestionVersion):
            target_version = v_target
        else:
            qid = str(v_target)
            v_num = version_number if version_number is not None else 1
            target_version = QuestionVersion.objects.get(question_id=qid, version_number=v_num)

        act = actor or kwargs.get('actor')

        if target_version.status != VersionStatus.DRAFT:
            raise DRFValidationError(f"Cannot publish question version in '{target_version.status}' status. Only DRAFT versions can be published.")

        # Full invariant validation
        QuestionValidationService.validate_for_publish(target_version)

        version = target_version
        actor = act

        with transaction.atomic():
            question = Question.objects.select_for_update().get(id=version.question_id)

            # Atomically archive any currently active published version
            currently_published = question.versions.filter(status=VersionStatus.PUBLISHED)
            for prev_pub in currently_published:
                prev_pub.status = VersionStatus.ARCHIVED
                prev_pub.save(update_fields=['status', 'updated_at'])

            version.status = VersionStatus.PUBLISHED
            version.published_at = timezone.now()
            version.save(update_fields=['status', 'published_at', 'updated_at'])

            AuditService.log(
                action="QUESTION_PUBLISHED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(question.id),
                    "version_number": version.version_number,
                    "points": version.points,
                    "question_type": version.question_type
                },
                request=request
            )

        return version

    @classmethod
    def archive_version(
        cls,
        version: QuestionVersion,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Transitions a PUBLISHED version to ARCHIVED.
        """
        if version.status != VersionStatus.PUBLISHED:
            raise DRFValidationError(f"Cannot archive question version in '{version.status}' status. Only PUBLISHED versions can be archived.")

        with transaction.atomic():
            version.status = VersionStatus.ARCHIVED
            version.save(update_fields=['status', 'updated_at'])

            AuditService.log(
                action="QUESTION_ARCHIVED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(version.question.id),
                    "version_number": version.version_number
                },
                request=request
            )

        return version

    @classmethod
    def archive_question(
        cls,
        question: Union[Question, str],
        actor: Optional[User] = None,
        request=None
    ) -> Question:
        """
        Logically archives a logical Question and all its active versions.
        """
        if isinstance(question, str):
            question = Question.objects.get(id=question)

        with transaction.atomic():
            question.status = QuestionStatus.ARCHIVED
            question.save(update_fields=['status', 'updated_at'])

            for v in question.versions.filter(status=VersionStatus.PUBLISHED):
                v.status = VersionStatus.ARCHIVED
                v.save(update_fields=['status', 'updated_at'])

            AuditService.log(
                action="QUESTION_ARCHIVED",
                actor=actor,
                target_type="Question",
                target_id=str(question.id),
                metadata={"question_id": str(question.id)},
                request=request
            )

        return question

    @classmethod
    def get_or_create_draft_version(
        cls,
        question: Question,
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[QuestionVersion, bool]:
        """
        If an existing editable DRAFT version already exists for the question, returns it.
        If the question has a PUBLISHED or ARCHIVED version, raises DRFValidationError.
        Returns (version, created: bool).
        """
        existing_draft = question.versions.filter(status=VersionStatus.DRAFT).order_by('-version_number').first()
        if existing_draft:
            return existing_draft, False
        if question.versions.filter(status__in=[VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]).exists():
            raise DRFValidationError("Published questions are permanently immutable and cannot have new draft versions created.")
        new_version = cls.create_new_version(question=question, actor=actor, request=request)
        return new_version, True

    @classmethod
    def duplicate_question(
        cls,
        question: Union[Question, str],
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[Question, QuestionVersion]:
        """
        Duplicates an existing question (draft or published) into a completely NEW Question identity in DRAFT status.
        Never links as a version of the original question.
        """
        if isinstance(question, str):
            question = Question.objects.get(id=question)

        latest_v = question.versions.order_by('-version_number').first()
        if not latest_v:
            raise DRFValidationError("Cannot duplicate a question without versions.")

        coding_conf_data = None
        test_cases_data = None
        if question.question_type == QuestionType.CODING and hasattr(latest_v, 'coding_config'):
            c = latest_v.coding_config
            coding_conf_data = {
                'problem_statement': c.problem_statement,
                'input_description': c.input_description,
                'output_description': c.output_description,
                'constraints': c.constraints,
                'allowed_languages': c.allowed_languages,
                'time_limit_ms': c.time_limit_ms,
                'memory_limit_mb': c.memory_limit_mb,
                'starter_codes': copy.deepcopy(c.starter_codes) if c.starter_codes else {},
                'examples': copy.deepcopy(c.examples) if c.examples else [],
                'reference_solutions': copy.deepcopy(c.reference_solutions) if c.reference_solutions else {},
                'reference_solution_language': c.reference_solution_language or '',
            }
            test_cases_data = [
                {
                    'name': tc.name,
                    'input_data': tc.input_data,
                    'expected_output': tc.expected_output,
                    'points': tc.points,
                    'is_hidden': tc.is_hidden,
                    'is_verified': tc.is_verified,
                    'execution_order': tc.execution_order,
                    'time_limit_override_ms': tc.time_limit_override_ms,
                    'memory_limit_override_mb': tc.memory_limit_override_mb,
                }
                for tc in c.test_cases.order_by('execution_order')
            ]

        sql_conf_data = None
        if question.question_type == QuestionType.SQL and hasattr(latest_v, 'sql_config'):
            s = latest_v.sql_config
            sql_conf_data = {
                'problem_statement': s.problem_statement,
                'schema_setup_sql': s.schema_setup_sql,
                'expected_result_definition': s.expected_result_definition,
                'allowed_dialect': s.allowed_dialect,
                'time_limit_ms': s.time_limit_ms,
            }

        new_question, new_version = cls.create_question(
            question_type=question.question_type,
            title=f"{latest_v.title} (Copy)",
            description=latest_v.description,
            instructions=latest_v.instructions,
            points=latest_v.points,
            negative_marking_enabled=latest_v.negative_marking_enabled,
            negative_points=latest_v.negative_points,
            difficulty=latest_v.difficulty,
            tags=[t.name for t in latest_v.tags.all()],
            type_config=copy.deepcopy(latest_v.type_config) if latest_v.type_config else {},
            coding_config_data=coding_conf_data,
            test_cases_data=test_cases_data,
            sql_config_data=sql_conf_data,
            actor=actor,
            request=request
        )

        AuditService.log(
            action="QUESTION_DUPLICATED",
            actor=actor,
            target_type="Question",
            target_id=str(new_question.id),
            metadata={
                "original_question_id": str(question.id),
                "new_question_id": str(new_question.id),
                "title": new_version.title
            },
            request=request
        )

        return new_question, new_version

    @classmethod
    def get_question_usage(cls, question: Question) -> Dict[str, Any]:
        """
        Dependency-aware usage check across assessments, snapshots, attempts, results,
        and legal holds/retention records.
        """
        from apps.assessments.models import AssessmentQuestion, AssessmentSnapshotQuestion, AttemptAnswer, Assessment
        from apps.retention.models import LegalHold, LegalHoldStatus

        assessment_qs = Assessment.objects.filter(
            assessment_questions__question_version__question=question
        ).distinct()

        using_assessments = [
            {
                "id": str(a.id),
                "title": a.title,
                "status": a.status,
                "total_points": a.total_points,
            }
            for a in assessment_qs
        ]
        assessment_count = len(using_assessments)
        snapshot_count = AssessmentSnapshotQuestion.objects.filter(question_version__question=question).count()
        attempt_answers_count = AttemptAnswer.objects.filter(snapshot_question__question_version__question=question).count()

        has_legal_hold = False
        if assessment_qs.exists():
            has_legal_hold = LegalHold.objects.filter(
                attempt__assessment__in=assessment_qs,
                status=LegalHoldStatus.ACTIVE
            ).exists()

        is_deletable = (
            assessment_count == 0
            and snapshot_count == 0
            and attempt_answers_count == 0
            and not has_legal_hold
        )

        reasons = []
        if assessment_count > 0:
            reasons.append(f"{assessment_count} assessments/exams")
        if snapshot_count > 0:
            reasons.append(f"{snapshot_count} snapshot(s)")
        if attempt_answers_count > 0:
            reasons.append(f"{attempt_answers_count} recorded student answer(s)")
        if has_legal_hold:
            reasons.append("an active legal hold")

        if not is_deletable:
            deps_desc = ", ".join(reasons) if reasons else "active assessment dependencies"
            reason_str = (
                f"Cannot delete question: Cannot delete this question because it is used in {assessment_count} assessment{'s' if assessment_count != 1 else ''}."
                if assessment_count > 0
                else f"Cannot delete question: This question cannot be permanently deleted because it is used by {deps_desc}."
            )
        else:
            reason_str = ""

        latest_v = question.versions.order_by('-version_number').first()

        return {
            "question_id": str(question.id),
            "title": latest_v.title if latest_v else "Unknown Question",
            "question_type": question.question_type,
            "version_count": question.versions.count(),
            "latest_version_number": latest_v.version_number if latest_v else 1,
            "status": question.status,
            "assessment_count": assessment_count,
            "assessments_count": assessment_count,
            "assessments": using_assessments,
            "snapshot_count": snapshot_count,
            "snapshots_count": snapshot_count,
            "attempt_answers_count": attempt_answers_count,
            "answers_count": attempt_answers_count,
            "has_legal_hold": has_legal_hold,
            "legal_holds_count": 1 if has_legal_hold else 0,
            "is_deletable": is_deletable,
            "reason_blocked": reason_str,
            "reasons": reasons,
        }

    @classmethod
    def delete_draft_question(
        cls,
        question: Union[Question, str],
        actor: Optional[User] = None,
        request=None
    ) -> None:
        """
        Hard-deletes a logical question if it has never been attached to an assessment.
        If assessment or examination dependencies exist, hard delete is blocked.
        """
        if isinstance(question, str):
            question = Question.objects.get(id=question)

        usage = cls.get_question_usage(question)
        if not usage["is_deletable"]:
            raise DRFValidationError({
                "detail": usage["reason_blocked"],
                "code": "HARD_DELETE_BLOCKED",
                "assessments": usage.get("assessments", [])
            })

        with transaction.atomic():
            q_id = str(question.id)
            title = usage["title"]
            q_type = usage["question_type"]
            v_count = usage["version_count"]

            question.delete()

            AuditService.log(
                action="QUESTION_DELETED",
                actor=actor,
                target_type="Question",
                target_id=q_id,
                metadata={
                    "question_id": q_id,
                    "title": title,
                    "question_type": q_type,
                    "version_count": v_count,
                    "reason": "Administrative deletion of unused question."
                },
                request=request
            )

    delete_question = delete_draft_question

    @staticmethod
    def _resolve_tags(tag_names: List[str]) -> List[Tag]:
        from django.utils.text import slugify
        tag_objs = []
        for name in tag_names:
            clean = name.strip()
            if clean:
                target_slug = slugify(clean)[:64]
                tag = Tag.objects.filter(slug=target_slug).first() or Tag.objects.filter(name__iexact=clean).first()
                if not tag:
                    tag, _ = Tag.objects.get_or_create(
                        slug=target_slug,
                        defaults={'name': clean}
                    )
                tag_objs.append(tag)
        return tag_objs
