"""
Canonical Question Architecture for CODEGUARD Assessment & Proctoring Platform.
Defines:
1. Canonical DTOs (CanonicalQuestionDTO, CanonicalOptionDTO, CanonicalCodingConfigDTO, CanonicalTestCaseDTO)
2. Shared Validation & Normalization Engine (used identically by Excel and Manual Authoring)
3. Canonical Excel Template Generator (CODEGUARD_Question_Import_Template_v1.xlsx)
4. Canonical Excel Parser (strict 6-sheet schema, template versioning, all-or-nothing validation)
5. Transactional Importer (atomic persistence into Question=ACTIVE and QuestionVersion=DRAFT)
"""

import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

# Template Identifiers
TEMPLATE_NAME = "CODEGUARD_QUESTION_IMPORT"
TEMPLATE_VERSION = 1

SUPPORTED_QUESTION_TYPES = {"MCQ", "CODING"}
SUPPORTED_CODING_LANGUAGES = {"PYTHON", "JAVA", "CPP", "C"}
SUPPORTED_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
INVALID_OUTPUT_PLACEHOLDERS = {"TODO", "TBD", "?", "[PLACEHOLDER]", "PLACEHOLDER", "NONE", "NULL"}


@dataclass
class CanonicalOptionDTO:
    option_key: str
    option_text: str
    is_correct: bool


@dataclass
class CanonicalTestCaseDTO:
    case_id: str
    visibility: str  # 'SAMPLE' | 'HIDDEN'
    input: str
    expected_output: str
    points: int = 1
    is_example: bool = False
    is_verified: bool = True


@dataclass
class CanonicalCodingConfigDTO:
    languages: List[str]
    starter_codes: Dict[str, str]
    constraints: str = ""
    execution_time_ms: int = 2000
    memory_mb: int = 256
    examples: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class CanonicalQuestionDTO:
    question_id: str
    title: str
    type: str  # 'MCQ' | 'CODING'
    statement: str
    instructions: str = ""
    difficulty: str = "MEDIUM"
    points: int = 10
    negative_points: int = 0
    options: List[CanonicalOptionDTO] = field(default_factory=list)
    coding: Optional[CanonicalCodingConfigDTO] = None
    test_cases: List[CanonicalTestCaseDTO] = field(default_factory=list)


def normalize_input_for_duplicate_check(input_text: str) -> str:
    """
    Normalizes test case input for duplicate detection WITHOUT altering internal whitespace.
    - Normalizes CRLF/CR to LF line endings.
    - Trims surrounding leading/trailing whitespace.
    """
    if not input_text:
        return ""
    text = str(input_text).replace('\r\n', '\n').replace('\r', '\n')
    return text.strip()


def is_no_input_coding_dto(dto: CanonicalQuestionDTO) -> bool:
    """
    Determines if a canonical question DTO represents a NO-INPUT coding question.
    """
    if not dto or str(dto.type).strip().upper() != "CODING":
        return False

    raw_test_cases = dto.test_cases or []
    if raw_test_cases and any(tc.input and str(tc.input).strip() != "" for tc in raw_test_cases):
        return False

    constraints = str(getattr(dto.coding, 'constraints', '') or '').lower() if dto.coding else ""
    statement = str(dto.statement or '').lower()
    instructions = str(dto.instructions or '').lower()

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
        if ind in constraints or ind in statement or ind in instructions:
            return True

    if raw_test_cases and all(not tc.input or str(tc.input).strip() == "" for tc in raw_test_cases) and any(tc.expected_output and str(tc.expected_output).strip() != "" for tc in raw_test_cases):
        return True

    return False


def validate_and_normalize_canonical_question(
    dto: CanonicalQuestionDTO
) -> Tuple[CanonicalQuestionDTO, List[str], List[str]]:
    """
    Shared validation and normalization pipeline.
    Must be executed by both Excel Import and Manual Authoring.
    Returns: (normalized_dto, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Base Metadata Validation
    q_id = str(dto.question_id).strip() if dto.question_id else ""
    if not q_id:
        errors.append("Question ID is required.")

    title = str(dto.title).strip() if dto.title else ""
    if not title:
        errors.append("Question title is required and cannot be empty.")

    q_type = str(dto.type).strip().upper() if dto.type else ""
    if q_type not in SUPPORTED_QUESTION_TYPES:
        errors.append(
            f"Unsupported question type '{dto.type}'. Supported types for v1 are: {sorted(list(SUPPORTED_QUESTION_TYPES))}."
        )

    statement = str(dto.statement).strip() if dto.statement else ""
    if not statement:
        errors.append("Question statement/prompt is required and cannot be empty.")

    difficulty = str(dto.difficulty).strip().upper() if dto.difficulty else "MEDIUM"
    if difficulty not in SUPPORTED_DIFFICULTIES:
        errors.append(f"Invalid difficulty '{dto.difficulty}'. Must be one of: {sorted(list(SUPPORTED_DIFFICULTIES))}.")
        difficulty = "MEDIUM"

    try:
        points = int(dto.points)
        if points < 1:
            errors.append(f"Question points must be an integer >= 1 (got {points}).")
            points = 1
    except (ValueError, TypeError):
        errors.append(f"Invalid points value '{dto.points}'. Must be an integer >= 1.")
        points = 1

    try:
        neg_points = int(dto.negative_points or 0)
        if neg_points < 0:
            errors.append(f"Negative points cannot be negative (got {neg_points}).")
            neg_points = 0
    except (ValueError, TypeError):
        errors.append(f"Invalid negative_points value '{dto.negative_points}'. Must be an integer >= 0.")
        neg_points = 0

    instructions = str(dto.instructions or "").strip()

    # 2. Type-Specific Validation
    normalized_options: List[CanonicalOptionDTO] = []
    normalized_coding: Optional[CanonicalCodingConfigDTO] = None
    normalized_test_cases: List[CanonicalTestCaseDTO] = []

    if q_type == "MCQ":
        if not dto.options or len(dto.options) < 2:
            warnings.append("MCQ question requires at least 2 options before publishing.")
        else:
            seen_keys: Set[str] = set()
            correct_count = 0
            for idx, opt in enumerate(dto.options):
                opt_key = str(opt.option_key).strip().upper() if opt.option_key else f"OPT_{idx+1}"
                opt_text = str(opt.option_text).strip() if opt.option_text else ""
                is_corr = bool(opt.is_correct)

                if not opt_text:
                    errors.append(f"Option '{opt_key}' text cannot be empty.")
                if opt_key in seen_keys:
                    errors.append(f"Duplicate option key '{opt_key}' detected.")
                seen_keys.add(opt_key)

                if is_corr:
                    correct_count += 1

                normalized_options.append(
                    CanonicalOptionDTO(option_key=opt_key, option_text=opt_text, is_correct=is_corr)
                )

            if correct_count == 0:
                errors.append("MCQ question must have exactly one correct option (none was marked correct).")
            elif correct_count > 1:
                errors.append(f"MCQ question must have exactly one correct option (found {correct_count} correct options).")

    elif q_type == "CODING":
        coding = dto.coding
        is_no_input = is_no_input_coding_dto(dto)
        if not coding:
            errors.append("Coding question configuration is missing.")
            coding = CanonicalCodingConfigDTO(languages=["PYTHON"], starter_codes={})

        # Validate languages
        raw_langs = coding.languages or []
        norm_langs = []
        for l in raw_langs:
            clean_l = str(l).strip().upper()
            if clean_l in SUPPORTED_CODING_LANGUAGES:
                if clean_l not in norm_langs:
                    norm_langs.append(clean_l)
            else:
                errors.append(
                    f"Unsupported coding language '{l}'. Supported for v1: {sorted(list(SUPPORTED_CODING_LANGUAGES))}."
                )

        if not norm_langs:
            errors.append(
                f"Coding question must enable at least one supported language ({sorted(list(SUPPORTED_CODING_LANGUAGES))})."
            )
            norm_langs = ["PYTHON"]

        # Validate starter codes synchronization
        starter_codes = coding.starter_codes or {}
        norm_starters: Dict[str, str] = {}
        for l in norm_langs:
            code = starter_codes.get(l) or starter_codes.get(l.lower()) or ""
            code_str = str(code).strip()
            if not code_str:
                errors.append(f"Language '{l}' is enabled but starter code is missing or empty.")
            norm_starters[l] = str(code)

        # Validate test cases
        raw_test_cases = dto.test_cases or []
        normalized_test_cases: List[CanonicalTestCaseDTO] = []
        derived_examples: List[Dict[str, str]] = []
        if not raw_test_cases:
            warnings.append("Coding question has no test cases. At least one test case is required before publishing.")
        else:
            seen_case_ids: Set[str] = set()
            sample_count = 0
            hidden_count = 0
            normalized_inputs_seen: Set[str] = set()

            for idx, tc in enumerate(raw_test_cases):
                case_id = str(tc.case_id).strip() if tc.case_id else f"TC{idx+1:02d}"
                if case_id in seen_case_ids:
                    errors.append(f"Duplicate test case ID '{case_id}' detected for question '{q_id}'.")
                seen_case_ids.add(case_id)

                vis = str(tc.visibility).strip().upper() if tc.visibility else "SAMPLE"
                if vis not in {"SAMPLE", "HIDDEN"}:
                    errors.append(f"Invalid visibility '{tc.visibility}' for test case '{case_id}'. Must be 'SAMPLE' or 'HIDDEN'.")
                    vis = "SAMPLE"

                if vis == "SAMPLE":
                    sample_count += 1
                else:
                    hidden_count += 1

                # Strict is_example rule
                is_ex = bool(tc.is_example)
                if vis == "HIDDEN" and is_ex:
                    errors.append("Hidden test cases cannot be marked as examples.")
                    is_ex = False

                inp = str(tc.input or "")
                out = str(tc.expected_output or "")

                if not out.strip():
                    errors.append(f"Test case '{case_id}' has empty expected output.")
                    is_ver = False
                elif out.strip().upper() in INVALID_OUTPUT_PLACEHOLDERS:
                    warnings.append(f"Test case '{case_id}' has placeholder output '{out.strip()}'. Requires manual verification.")
                    is_ver = False
                else:
                    is_ver = bool(tc.is_verified)

                # Duplicate input detection
                norm_inp = normalize_input_for_duplicate_check(inp)
                if is_no_input and norm_inp == "":
                    pass
                elif norm_inp in normalized_inputs_seen:
                    warnings.append(f"Test case '{case_id}' has duplicate normalized input.")
                else:
                    normalized_inputs_seen.add(norm_inp)

                try:
                    tc_pts = int(tc.points)
                    if tc_pts < 1:
                        tc_pts = 1
                except (ValueError, TypeError):
                    tc_pts = 1

                normalized_test_cases.append(
                    CanonicalTestCaseDTO(
                        case_id=case_id,
                        visibility=vis,
                        input=inp,
                        expected_output=out,
                        points=tc_pts,
                        is_example=is_ex,
                        is_verified=is_ver
                    )
                )

            if sample_count == 0:
                warnings.append("Coding question has no public SAMPLE test cases. At least 1 SAMPLE test case is required before publishing.")
            if hidden_count == 0:
                warnings.append("Coding question has no HIDDEN test cases. At least 1 HIDDEN test case is required before publishing.")

            # Points validation and deterministic normalization
            N = len(normalized_test_cases)
            P = points
            if N > 0:
                if P < N:
                    errors.append(
                        f"Question has {P} points but {N} scored test cases require at least 1 point each. "
                        f"Increase question points or reduce scored test cases."
                    )
                else:
                    # Deterministic point distribution check
                    current_sum = sum(tc.points for tc in normalized_test_cases)
                    if current_sum != P or any(tc.points < 1 for tc in normalized_test_cases):
                        base = P // N
                        rem = P % N
                        for i, tc in enumerate(normalized_test_cases):
                            tc.points = base + 1 if i < rem else base

            # Example derivation: TestCases are the authoritative source of truth for examples
            # Only SAMPLE + is_example=TRUE test cases become examples
            derived_examples: List[Dict[str, str]] = []
            for tc in normalized_test_cases:
                if tc.visibility == "SAMPLE" and tc.is_example and tc.expected_output and str(tc.expected_output).strip():
                    derived_examples.append({
                        "input": tc.input or "",
                        "output": tc.expected_output,
                        "explanation": ""
                    })

            # If no test case was explicitly marked as an example, use the first sample test as an example
            if not derived_examples:
                first_sample = next((tc for tc in normalized_test_cases if tc.visibility == "SAMPLE" and tc.expected_output and str(tc.expected_output).strip()), None)
                if first_sample:
                    first_sample.is_example = True
                    derived_examples.append({
                        "input": first_sample.input or "",
                        "output": first_sample.expected_output,
                        "explanation": ""
                    })

        normalized_coding = CanonicalCodingConfigDTO(
            languages=norm_langs,
            starter_codes=norm_starters,
            constraints=str(coding.constraints or "").strip(),
            execution_time_ms=int(coding.execution_time_ms or 2000),
            memory_mb=int(coding.memory_mb or 256),
            examples=derived_examples
        )

    normalized_dto = CanonicalQuestionDTO(
        question_id=q_id,
        title=title,
        type=q_type,
        statement=statement,
        instructions=instructions,
        difficulty=difficulty,
        points=points,
        negative_points=neg_points,
        options=normalized_options,
        coding=normalized_coding,
        test_cases=normalized_test_cases
    )

    return normalized_dto, errors, warnings


class CanonicalExcelTemplateGenerator:
    """
    Generates the official CODEGUARD_Question_Import_Template_v1.xlsx with 6 sheets.
    Canonical 3-question fixture:
    - Q001: Binary Search Complexity (MCQ)
    - Q002: Python List Operation (MCQ)
    - Q003: Find the Maximum Element (CODING)
    """
    @classmethod
    def generate_template_workbook(cls) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

        def style_header(ws, row=1, col_count=1):
            for c in range(1, col_count + 1):
                cell = ws.cell(row=row, column=c)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # -------------------------------------------------------------
        # 1. README (Documentation Sheet)
        # -------------------------------------------------------------
        ws_readme = wb.create_sheet(title="README")
        readme_lines = [
            ("Template Name", TEMPLATE_NAME),
            ("Template Version", str(TEMPLATE_VERSION)),
            ("Platform", "CODEGUARD / Craft Society At-Home Examination Platform"),
            ("Supported Question Types", "MCQ, CODING"),
            ("Relationship Key", "question_id links across all sheets"),
            ("", ""),
            ("SHEET GUIDELINES", ""),
            ("1. README", "Template documentation and instructions. Non-data sheet."),
            ("2. Questions", "Core metadata (question_id, title, type, statement, instructions, difficulty, points, negative_points). Authoritative question roster."),
            ("3. Options", "MCQ choices (question_id, option_key, option_text, is_correct). Exactly one correct option per MCQ."),
            ("4. Coding", "Language configurations and starter codes. Every enabled language MUST have valid starter code."),
            ("5. TestCases", "Coding test cases (visibility=SAMPLE or HIDDEN). Hidden tests must NOT be marked is_example=TRUE."),
            ("6. COLUMN_GUIDE", "Detailed column definitions, data types, and validation rules. Non-data sheet.")
        ]
        ws_readme.column_dimensions['A'].width = 28
        ws_readme.column_dimensions['B'].width = 80
        for r_idx, (k, v) in enumerate(readme_lines, start=1):
            c1 = ws_readme.cell(row=r_idx, column=1, value=k)
            c2 = ws_readme.cell(row=r_idx, column=2, value=v)
            if r_idx in (1, 2):
                c1.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
                c2.font = Font(name="Calibri", size=11, bold=True, color="0284C7")
            elif k == "SHEET GUIDELINES":
                c1.font = Font(name="Calibri", size=12, bold=True, color="1E293B")
            else:
                c1.font = Font(name="Calibri", size=10, bold=True)
                c2.font = Font(name="Calibri", size=10)

        # -------------------------------------------------------------
        # 2. Questions (Authoritative Question Roster)
        # -------------------------------------------------------------
        ws_q = wb.create_sheet(title="Questions")
        q_headers = ["question_id", "title", "type", "statement", "instructions", "difficulty", "points", "negative_points"]
        ws_q.append(q_headers)
        style_header(ws_q, 1, len(q_headers))
        q_rows = [
            ("Q001", "Binary Search Complexity", "MCQ", "What is the worst-case time complexity of binary search on a sorted array containing n elements?", "Select the single correct answer.", "EASY", 10, 0),
            ("Q002", "Python List Operation", "MCQ", "Which Python list method removes and returns the last element of a list?", "Select the single correct answer.", "EASY", 10, 0),
            ("Q003", "Find the Maximum Element", "CODING", "Given an array of integers, find and output the maximum element. Do not use the built-in max function.", "Read n followed by n integers and output the maximum value.", "MEDIUM", 20, 0),
        ]
        for row in q_rows:
            ws_q.append(row)

        # -------------------------------------------------------------
        # 3. Options (MCQ Options)
        # -------------------------------------------------------------
        ws_opt = wb.create_sheet(title="Options")
        opt_headers = ["question_id", "option_key", "option_text", "is_correct"]
        ws_opt.append(opt_headers)
        style_header(ws_opt, 1, len(opt_headers))
        opt_rows = [
            ("Q001", "A", "O(1)", "FALSE"),
            ("Q001", "B", "O(log n)", "TRUE"),
            ("Q001", "C", "O(n)", "FALSE"),
            ("Q001", "D", "O(n log n)", "FALSE"),
            ("Q002", "A", "remove()", "FALSE"),
            ("Q002", "B", "delete()", "FALSE"),
            ("Q002", "C", "pop()", "TRUE"),
            ("Q002", "D", "discard()", "FALSE"),
        ]
        for row in opt_rows:
            ws_opt.append(row)

        # -------------------------------------------------------------
        # 4. Coding (Coding Configurations)
        # -------------------------------------------------------------
        ws_coding = wb.create_sheet(title="Coding")
        coding_headers = ["question_id", "language", "starter_code", "constraints", "execution_time_ms", "memory_mb"]
        ws_coding.append(coding_headers)
        style_header(ws_coding, 1, len(coding_headers))
        coding_rows = [
            ("Q003", "PYTHON", "def solve():\n    import sys\n    tokens = sys.stdin.read().split()\n    if not tokens:\n        return\n    arr = [int(x) for x in tokens[1:]]\n    res = arr[0]\n    for x in arr[1:]:\n        if x > res:\n            res = x\n    print(res)\n\nif __name__ == '__main__':\n    solve()\n", "1 <= N <= 10^5\nElements fit in 32-bit signed integer", 2000, 256),
        ]
        for row in coding_rows:
            ws_coding.append(row)

        # -------------------------------------------------------------
        # 5. TestCases (Coding Test Cases)
        # -------------------------------------------------------------
        ws_tc = wb.create_sheet(title="TestCases")
        tc_headers = ["question_id", "case_id", "visibility", "input", "expected_output", "points", "is_example"]
        ws_tc.append(tc_headers)
        style_header(ws_tc, 1, len(tc_headers))
        tc_rows = [
            ("Q003", "TC001", "SAMPLE", "5\n1 7 3 9 2", "9", 5, "TRUE"),
            ("Q003", "TC002", "SAMPLE", "4\n-5 -2 -9 -1", "-1", 5, "TRUE"),
            ("Q003", "TC003", "HIDDEN", "6\n10 4 25 7 3 18", "25", 5, "FALSE"),
            ("Q003", "TC004", "HIDDEN", "3\n-10 -20 -3", "-3", 5, "FALSE"),
        ]
        for row in tc_rows:
            ws_tc.append(row)

        # -------------------------------------------------------------
        # 6. COLUMN_GUIDE (Documentation Sheet)
        # -------------------------------------------------------------
        ws_guide = wb.create_sheet(title="COLUMN_GUIDE")
        guide_headers = ["Sheet", "Column", "Required", "Data Type", "Allowed Values / Format", "Description"]
        ws_guide.append(guide_headers)
        style_header(ws_guide, 1, len(guide_headers))
        guide_rows = [
            ("Questions", "question_id", "YES", "String", "Alphanumeric (e.g. Q001)", "Stable unique question identifier linking all sheets."),
            ("Questions", "title", "YES", "String", "Non-empty string", "Human-readable question title."),
            ("Questions", "type", "YES", "Enum", "MCQ, CODING", "Question evaluation type."),
            ("Questions", "statement", "YES", "Markdown", "Non-empty markdown text", "Full question prompt or problem statement."),
            ("Questions", "instructions", "NO", "String", "Optional text", "Candidate-facing instructions."),
            ("Questions", "difficulty", "YES", "Enum", "EASY, MEDIUM, HARD", "Pedagogical difficulty level."),
            ("Questions", "points", "YES", "Integer", ">= 1", "Total question marks/points."),
            ("Questions", "negative_points", "NO", "Integer", ">= 0", "Deducted penalty points for incorrect answer."),
            ("Options", "question_id", "YES", "String", "Must exist in Questions", "References parent MCQ question."),
            ("Options", "option_key", "YES", "String", "A, B, C, D, ...", "Unique option identifier within question."),
            ("Options", "option_text", "YES", "String", "Non-empty string", "Option choice text displayed to candidate."),
            ("Options", "is_correct", "YES", "Boolean", "TRUE or FALSE", "Exactly one option must be marked TRUE per MCQ."),
            ("Coding", "question_id", "YES", "String", "Must exist in Questions", "References parent CODING question."),
            ("Coding", "language", "YES", "Enum", "PYTHON, JAVA, CPP, C", "Enabled programming language."),
            ("Coding", "starter_code", "YES", "Code Text", "Non-empty code string", "Code editor scaffold provided to candidate."),
            ("Coding", "constraints", "NO", "String", "Optional text", "Execution constraints and input bounds."),
            ("Coding", "execution_time_ms", "NO", "Integer", "500 to 10000 (default 2000)", "CPU time limit in milliseconds."),
            ("Coding", "memory_mb", "NO", "Integer", "64 to 1024 (default 256)", "Memory limit in megabytes."),
            ("TestCases", "question_id", "YES", "String", "Must exist in Questions", "References parent CODING question."),
            ("TestCases", "case_id", "YES", "String", "TC001, TC002, ...", "Unique case identifier within the question."),
            ("TestCases", "visibility", "YES", "Enum", "SAMPLE, HIDDEN", "SAMPLE is student-visible. HIDDEN is evaluator-only."),
            ("TestCases", "input", "NO", "String", "Standard input string", "Standard input fed into solution."),
            ("TestCases", "expected_output", "YES", "String", "Real expected output", "Expected standard output. Placeholders like TODO are rejected."),
            ("TestCases", "points", "YES", "Integer", ">= 1", "Points awarded if this test case passes. Normalized if sum != total."),
            ("TestCases", "is_example", "YES", "Boolean", "TRUE or FALSE", "If TRUE, appears in student examples. HIDDEN + TRUE is forbidden.")
        ]
        for row in guide_rows:
            ws_guide.append(row)

        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    val_str = str(cell.value or '')
                    if '\n' in val_str:
                        lines = val_str.split('\n')
                        line_len = max(len(l) for l in lines) if lines else 0
                        max_len = max(max_len, line_len)
                    else:
                        max_len = max(max_len, len(val_str))
                sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

        return wb

    @classmethod
    def generate_template_bytes(cls) -> bytes:
        wb = cls.generate_template_workbook()
        stream = io.BytesIO()
        wb.save(stream)
        return stream.getvalue()


class CanonicalExcelParser:
    """
    Parses and strictly validates the 6-sheet canonical Excel workbook.
    Ensures robust sheet discovery, non-empty header scanning, whitespace/case normalization,
    relationship resolution, and explicit error generation (no silent zero failures).
    """

    @staticmethod
    def _normalize_identifier(val: Any) -> str:
        if val is None:
            return ""
        return str(val).strip().lower().replace(" ", "").replace("_", "").replace("-", "")

    @staticmethod
    def _normalize_header(val: Any) -> str:
        if val is None:
            return ""
        cleaned = str(val).strip().lower()
        return re.sub(r'[\s\-]+', '_', cleaned)

    @classmethod
    def _extract_headers_and_data_rows(
        cls, ws: openpyxl.worksheet.worksheet.Worksheet
    ) -> Tuple[List[str], List[Tuple[int, List[Any]]]]:
        """
        Scans sheet to locate the first non-empty row as the header row,
        normalizes column headers, and returns (headers, [(row_number, row_values)]).
        """
        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            return [], []

        header_idx = -1
        headers: List[str] = []

        for idx, row in enumerate(all_rows):
            if not row:
                continue
            # Check if row has meaningful non-empty cell values
            non_empty_cells = [c for c in row if c is not None and str(c).strip() != ""]
            if non_empty_cells:
                header_idx = idx
                headers = [cls._normalize_header(c) for c in row]
                break

        if header_idx == -1:
            return [], []

        data_rows: List[Tuple[int, List[Any]]] = []
        for r_num, row in enumerate(all_rows[header_idx + 1:], start=header_idx + 2):
            # Check if row has any non-blank value
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            data_rows.append((r_num, list(row)))

        return headers, data_rows

    @classmethod
    def parse_workbook(cls, file_obj) -> Tuple[List[CanonicalQuestionDTO], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parses workbook and returns (canonical_dtos, errors, warnings).
        errors format: [{'question_id': str, 'type': str, 'message': str}]
        warnings format: [{'question_id': str, 'type': str, 'message': str}]
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        if isinstance(file_obj, openpyxl.Workbook):
            wb = file_obj
        else:
            try:
                # Seek to beginning if file-like object
                if hasattr(file_obj, 'seek') and callable(file_obj.seek):
                    file_obj.seek(0)
                wb = openpyxl.load_workbook(file_obj, data_only=True)
            except Exception as e:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "WORKBOOK",
                    "message": f"Unable to read Excel workbook: {str(e)}"
                })
                return [], errors, warnings

        # 1. Robust Sheet Discovery by Normalized Sheet Name
        sheet_map: Dict[str, str] = {}
        for name in wb.sheetnames:
            norm_name = cls._normalize_identifier(name)
            sheet_map[norm_name] = name

        # Validate README metadata if explicitly configured
        real_readme_name = sheet_map.get("readme")
        if real_readme_name:
            ws_readme = wb[real_readme_name]
            readme_dict = {}
            for row in ws_readme.iter_rows(values_only=True):
                if row and len(row) >= 2 and row[0]:
                    k = str(row[0]).strip().lower()
                    v = str(row[1]).strip() if row[1] is not None else ""
                    readme_dict[k] = v

            tmpl_name = readme_dict.get("template name", "")
            if tmpl_name and tmpl_name.upper() != TEMPLATE_NAME:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "TEMPLATE_VERSION",
                    "message": f"Invalid template: Workbook template name '{tmpl_name}' is not supported. Expected '{TEMPLATE_NAME}'."
                })

            tmpl_ver = readme_dict.get("template version", "")
            if tmpl_ver and tmpl_ver != str(TEMPLATE_VERSION):
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "TEMPLATE_VERSION",
                    "message": f"Unsupported template version {tmpl_ver}. Expected version {TEMPLATE_VERSION}."
                })

            if errors:
                return [], errors, warnings

        # Locate Questions sheet (authoritative question source)
        real_q_sheet_name = sheet_map.get("questions")
        if not real_q_sheet_name:
            errors.append({
                "question_id": "GLOBAL",
                "type": "QUESTIONS_SHEET",
                "message": "Questions sheet not found. Expected a sheet named Questions."
            })
            return [], errors, warnings

        ws_q = wb[real_q_sheet_name]
        headers_q, q_data_rows = cls._extract_headers_and_data_rows(ws_q)

        if not headers_q:
            errors.append({
                "question_id": "GLOBAL",
                "type": "QUESTIONS_SHEET",
                "message": "Questions sheet contains no headers or data rows."
            })
            return [], errors, warnings

        # Validate Required Headers in Questions sheet
        required_q_headers = ["question_id", "title", "type", "statement", "difficulty", "points"]
        for req_h in required_q_headers:
            if req_h not in headers_q:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "REQUIRED_HEADER",
                    "message": f"Questions sheet missing required column: {req_h}"
                })

        if errors:
            return [], errors, warnings

        reserved_q = {"question_id", "title", "type", "statement", "instructions", "difficulty", "points", "negative_points"}
        for h in headers_q:
            if h and h not in reserved_q:
                warnings.append({
                    "question_id": "GLOBAL",
                    "type": "COLUMN_WARNING",
                    "message": f"Questions sheet contains unrecognized column '{h}'. It will be ignored."
                })

        def get_val(row: List[Any], headers: List[str], key: str, default: Any = "") -> Any:
            if key in headers:
                col_idx = headers.index(key)
                if col_idx < len(row):
                    val = row[col_idx]
                    return val if val is not None else default
            return default

        # 2. Parse Question Rows
        questions_dict: Dict[str, Dict[str, Any]] = {}
        seen_q_ids: Set[str] = set()
        seen_titles: Set[str] = set()

        for r_num, row in q_data_rows:
            qid = str(get_val(row, headers_q, "question_id", "")).strip()
            title = str(get_val(row, headers_q, "title", "")).strip()
            raw_type_val = str(get_val(row, headers_q, "type", "")).strip()

            # Skip row if question_id, title, and type are all empty
            if not qid and not title and not raw_type_val:
                continue

            if not qid:
                errors.append({
                    "question_id": f"ROW_{r_num}",
                    "type": "METADATA",
                    "message": f"Row {r_num} in Questions sheet has missing question_id."
                })
                continue

            if qid in seen_q_ids:
                errors.append({
                    "question_id": qid,
                    "type": "DUPLICATE_ID",
                    "message": f"Duplicate question_id '{qid}' detected in Questions sheet."
                })
                continue
            seen_q_ids.add(qid)

            # Normalize Question Type
            q_type = raw_type_val.upper()
            if q_type not in SUPPORTED_QUESTION_TYPES:
                errors.append({
                    "question_id": qid,
                    "type": "UNSUPPORTED_TYPE",
                    "message": f"Unsupported question type '{raw_type_val}' for question '{qid}'. Supported types: ['CODING', 'MCQ']."
                })
                continue

            if not title:
                errors.append({
                    "question_id": qid,
                    "type": "METADATA",
                    "message": f"Question '{qid}' title is required and cannot be empty."
                })

            if title and title.lower() in seen_titles:
                warnings.append({
                    "question_id": qid,
                    "type": "DUPLICATE_TITLE",
                    "message": f"Question '{qid}' has a title '{title}' that matches another question in this workbook."
                })
            elif title:
                seen_titles.add(title.lower())

            statement = str(get_val(row, headers_q, "statement", "")).strip()
            instructions = str(get_val(row, headers_q, "instructions", "")).strip()
            difficulty = str(get_val(row, headers_q, "difficulty", "MEDIUM")).strip().upper()
            pts = get_val(row, headers_q, "points", 10)
            neg_pts = get_val(row, headers_q, "negative_points", 0)

            questions_dict[qid] = {
                "question_id": qid,
                "title": title,
                "type": q_type,
                "statement": statement,
                "instructions": instructions,
                "difficulty": difficulty,
                "points": pts,
                "negative_points": neg_pts,
                "options": [],
                "coding": None,
                "test_cases": []
            }

        if not questions_dict and not errors:
            errors.append({
                "question_id": "GLOBAL",
                "type": "QUESTIONS_SHEET",
                "message": "No question rows found in the Questions sheet."
            })
            return [], errors, warnings

        # 3. Parse Options Sheet (MCQ questions)
        has_mcq = any(q["type"] == "MCQ" for q in questions_dict.values())
        real_opt_sheet_name = sheet_map.get("options")

        if has_mcq and not real_opt_sheet_name:
            errors.append({
                "question_id": "GLOBAL",
                "type": "OPTIONS_SHEET",
                "message": "Options sheet not found. Expected a sheet named Options for MCQ questions."
            })
        elif real_opt_sheet_name:
            ws_opt = wb[real_opt_sheet_name]
            headers_opt, opt_data_rows = cls._extract_headers_and_data_rows(ws_opt)

            if has_mcq and not headers_opt:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "OPTIONS_SHEET",
                    "message": "Options sheet contains no headers or data rows."
                })
            elif headers_opt:
                # Validate required headers for Options
                required_opt_headers = ["question_id", "option_key", "option_text", "is_correct"]
                for req_h in required_opt_headers:
                    if req_h not in headers_opt:
                        errors.append({
                            "question_id": "GLOBAL",
                            "type": "REQUIRED_HEADER",
                            "message": f"Options sheet missing required column: {req_h}"
                        })

                if not any(e["type"] == "REQUIRED_HEADER" for e in errors):
                    for r_num, row in opt_data_rows:
                        qid = str(get_val(row, headers_opt, "question_id", "")).strip()
                        if not qid:
                            continue

                        if qid not in questions_dict:
                            errors.append({
                                "question_id": qid,
                                "type": "ORPHAN_OPTION",
                                "message": f"Row {r_num} in Options references non-existent question_id '{qid}'."
                            })
                            continue

                        if questions_dict[qid]["type"] != "MCQ":
                            errors.append({
                                "question_id": qid,
                                "type": "TYPE_MISMATCH",
                                "message": f"Question '{qid}' is type '{questions_dict[qid]['type']}' but options were provided."
                            })
                            continue

                        opt_key = str(get_val(row, headers_opt, "option_key", "")).strip().upper()
                        opt_text = str(get_val(row, headers_opt, "option_text", "")).strip()

                        raw_corr = get_val(row, headers_opt, "is_correct", False)
                        if isinstance(raw_corr, bool):
                            is_corr = raw_corr
                        else:
                            is_corr = str(raw_corr).strip().upper() in {"TRUE", "1", "YES", "T"}

                        questions_dict[qid]["options"].append(
                            CanonicalOptionDTO(option_key=opt_key, option_text=opt_text, is_correct=is_corr)
                        )

        # 4. Parse Coding Sheet (CODING questions)
        has_coding = any(q["type"] == "CODING" for q in questions_dict.values())
        real_coding_sheet_name = sheet_map.get("coding")
        coding_data_by_q: Dict[str, Dict[str, Any]] = {}

        if has_coding and not real_coding_sheet_name:
            errors.append({
                "question_id": "GLOBAL",
                "type": "CODING_SHEET",
                "message": "Coding sheet not found. Expected a sheet named Coding for CODING questions."
            })
        elif real_coding_sheet_name:
            ws_coding = wb[real_coding_sheet_name]
            headers_coding, coding_data_rows = cls._extract_headers_and_data_rows(ws_coding)

            if has_coding and not headers_coding:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "CODING_SHEET",
                    "message": "Coding sheet contains no headers or data rows."
                })
            elif headers_coding:
                if "question_id" not in headers_coding:
                    errors.append({
                        "question_id": "GLOBAL",
                        "type": "REQUIRED_HEADER",
                        "message": "Coding sheet missing required column: question_id"
                    })

                for r_num, row in coding_data_rows:
                    qid = str(get_val(row, headers_coding, "question_id", "")).strip()
                    if not qid:
                        continue

                    if qid not in questions_dict:
                        errors.append({
                            "question_id": qid,
                            "type": "ORPHAN_CODING",
                            "message": f"Row {r_num} in Coding sheet references non-existent question_id '{qid}'."
                        })
                        continue

                    if questions_dict[qid]["type"] != "CODING":
                        errors.append({
                            "question_id": qid,
                            "type": "TYPE_MISMATCH",
                            "message": f"Question '{qid}' is type '{questions_dict[qid]['type']}' but coding config was provided."
                        })
                        continue

                    allowed_langs_raw = str(get_val(row, headers_coding, "allowed_languages", "")).strip()
                    single_lang_raw = str(get_val(row, headers_coding, "language", "")).strip()
                    langs_str = allowed_langs_raw or single_lang_raw
                    row_langs = [l.strip().upper() for l in langs_str.split(",") if l.strip()] if langs_str else []

                    constraints = str(get_val(row, headers_coding, "constraints", ""))
                    exec_time = get_val(row, headers_coding, "execution_time_ms", get_val(row, headers_coding, "time_limit_ms", 2000))
                    mem_mb = get_val(row, headers_coding, "memory_mb", get_val(row, headers_coding, "memory_limit_mb", 256))

                    if qid not in coding_data_by_q:
                        coding_data_by_q[qid] = {
                            "languages": [],
                            "starter_codes": {},
                            "constraints": constraints,
                            "execution_time_ms": exec_time,
                            "memory_mb": mem_mb,
                        }

                    for l in row_langs:
                        if l not in coding_data_by_q[qid]["languages"]:
                            coding_data_by_q[qid]["languages"].append(l)

                        lang_key = l.lower()
                        starter_val = ""
                        if f"starter_code_{lang_key}" in headers_coding:
                            starter_val = str(get_val(row, headers_coding, f"starter_code_{lang_key}", ""))
                        elif "starter_code" in headers_coding:
                            if len(row_langs) == 1 or l == row_langs[0]:
                                starter_val = str(get_val(row, headers_coding, "starter_code", ""))

                        coding_data_by_q[qid]["starter_codes"][l] = starter_val

        # 5. Parse TestCases Sheet (CODING questions)
        real_tc_sheet_name = sheet_map.get("testcases") or sheet_map.get("testcase")
        if has_coding and not real_tc_sheet_name:
            errors.append({
                "question_id": "GLOBAL",
                "type": "TESTCASES_SHEET",
                "message": "TestCases sheet not found. Expected a sheet named TestCases for CODING questions."
            })
        elif real_tc_sheet_name:
            ws_tc = wb[real_tc_sheet_name]
            headers_tc, tc_data_rows = cls._extract_headers_and_data_rows(ws_tc)

            if has_coding and not headers_tc:
                errors.append({
                    "question_id": "GLOBAL",
                    "type": "TESTCASES_SHEET",
                    "message": "TestCases sheet contains no headers or data rows."
                })
            elif headers_tc:
                required_tc_headers = ["question_id", "case_id", "visibility", "expected_output"]
                for req_h in required_tc_headers:
                    if req_h not in headers_tc:
                        errors.append({
                            "question_id": "GLOBAL",
                            "type": "REQUIRED_HEADER",
                            "message": f"TestCases sheet missing required column: {req_h}"
                        })

                if not any(e["type"] == "REQUIRED_HEADER" for e in errors):
                    for r_num, row in tc_data_rows:
                        qid = str(get_val(row, headers_tc, "question_id", "")).strip()
                        if not qid:
                            continue

                        if qid not in questions_dict:
                            errors.append({
                                "question_id": qid,
                                "type": "ORPHAN_TEST_CASE",
                                "message": f"Row {r_num} in TestCases references non-existent question_id '{qid}'."
                            })
                            continue

                        if questions_dict[qid]["type"] != "CODING":
                            errors.append({
                                "question_id": qid,
                                "type": "TYPE_MISMATCH",
                                "message": f"Question '{qid}' is type '{questions_dict[qid]['type']}' but test cases were provided."
                            })
                            continue

                        case_id = str(get_val(row, headers_tc, "case_id", "")).strip()
                        vis = str(get_val(row, headers_tc, "visibility", "SAMPLE")).strip().upper()
                        inp = str(get_val(row, headers_tc, "input", ""))
                        out = str(get_val(row, headers_tc, "expected_output", ""))
                        pts = get_val(row, headers_tc, "points", 1)

                        raw_ex = get_val(row, headers_tc, "is_example", False)
                        if isinstance(raw_ex, bool):
                            is_ex = raw_ex
                        else:
                            is_ex = str(raw_ex).strip().upper() in {"TRUE", "1", "YES", "T"}

                        # Strict Phase 10 validation: Hidden test cases can never become examples
                        if vis == "HIDDEN" and is_ex:
                            errors.append({
                                "question_id": qid,
                                "type": "EXAMPLE_ERROR",
                                "message": f"Test case '{case_id}' for question '{qid}' is HIDDEN and cannot be marked as an example."
                            })

                        questions_dict[qid]["test_cases"].append(
                            CanonicalTestCaseDTO(
                                case_id=case_id,
                                visibility=vis,
                                input=inp,
                                expected_output=out,
                                points=pts,
                                is_example=is_ex
                            )
                        )

        # 6. Assemble into Canonical DTOs and execute shared validation
        final_dtos: List[CanonicalQuestionDTO] = []
        for qid, q_data in questions_dict.items():
            if q_data["type"] == "MCQ":
                if len(q_data["options"]) < 2:
                    errors.append({
                        "question_id": qid,
                        "type": "OPTIONS",
                        "message": f"MCQ question '{qid}' requires at least 2 options in Options sheet."
                    })
                correct_count = sum(1 for opt in q_data["options"] if opt.is_correct)
                if len(q_data["options"]) >= 2 and correct_count == 0:
                    errors.append({
                        "question_id": qid,
                        "type": "OPTIONS",
                        "message": f"MCQ question '{qid}' must have exactly one correct option (none was marked correct)."
                    })
                elif correct_count > 1:
                    errors.append({
                        "question_id": qid,
                        "type": "OPTIONS",
                        "message": f"MCQ question '{qid}' must have exactly one correct option (found {correct_count} correct options)."
                    })

            if q_data["type"] == "CODING":
                c_info = coding_data_by_q.get(qid, {
                    "languages": ["PYTHON"],
                    "starter_codes": {},
                    "constraints": "",
                    "execution_time_ms": 2000,
                    "memory_mb": 256
                })
                coding_dto = CanonicalCodingConfigDTO(
                    languages=c_info["languages"],
                    starter_codes=c_info["starter_codes"],
                    constraints=c_info["constraints"],
                    execution_time_ms=c_info["execution_time_ms"],
                    memory_mb=c_info["memory_mb"]
                )
            else:
                coding_dto = None

            raw_dto = CanonicalQuestionDTO(
                question_id=qid,
                title=q_data["title"],
                type=q_data["type"],
                statement=q_data["statement"],
                instructions=q_data["instructions"],
                difficulty=q_data["difficulty"],
                points=q_data["points"],
                negative_points=q_data["negative_points"],
                options=q_data["options"],
                coding=coding_dto,
                test_cases=q_data["test_cases"]
            )

            # Run Shared Validation & Normalization
            norm_dto, q_errs, q_warns = validate_and_normalize_canonical_question(raw_dto)
            for err in q_errs:
                # Avoid duplicate error messages
                if not any(e.get("message") == err and e.get("question_id") == qid for e in errors):
                    errors.append({"question_id": qid, "type": "VALIDATION_ERROR", "message": err})
            for warn in q_warns:
                if not any(w.get("message") == warn and w.get("question_id") == qid for w in warnings):
                    warnings.append({"question_id": qid, "type": "VALIDATION_WARNING", "message": warn})

            final_dtos.append(norm_dto)

        return final_dtos, errors, warnings


class CanonicalQuestionImporter:
    """
    Transactional All-or-Nothing Importer for validated CanonicalQuestionDTO collections.
    Creates Question (ACTIVE) + initial QuestionVersion (v1, DRAFT).
    """
    @classmethod
    def import_canonical_questions(
        cls,
        dtos: List[CanonicalQuestionDTO],
        actor: Optional[Any] = None,
        request=None
    ) -> Dict[str, Any]:
        from apps.questions.models import (
            Question,
            QuestionVersion,
            CodingQuestionConfig,
            TestCase,
            QuestionStatus,
            VersionStatus,
            QuestionType,
            Difficulty
        )
        from apps.accounts.services import AuditService

        if not dtos:
            raise DRFValidationError({"detail": "No questions provided for import."})

        # All-or-nothing check: validate all DTOs first before touching DB
        all_errors = []
        normalized_dtos = []
        for dto in dtos:
            norm_dto, errs, warns = validate_and_normalize_canonical_question(dto)
            if errs:
                all_errors.extend([f"[{dto.question_id}] {e}" for e in errs])
            normalized_dtos.append(norm_dto)

        if all_errors:
            raise DRFValidationError({
                "detail": "Import failed validation. Zero questions were created.",
                "errors": all_errors
            })

        created_questions = []

        with transaction.atomic():
            for dto in normalized_dtos:
                # 1. Create logical Question (ACTIVE)
                question = Question.objects.create(
                    question_type=dto.type,
                    status=QuestionStatus.ACTIVE,
                    created_by=actor
                )

                # 2. Compile type_config for MCQ
                type_config: Dict[str, Any] = {}
                if dto.type == "MCQ":
                    opts_list = [
                        {"id": opt.option_key, "text": opt.option_text, "is_correct": opt.is_correct}
                        for opt in dto.options
                    ]
                    correct_opts = [opt.option_key for opt in dto.options if opt.is_correct]
                    type_config = {
                        "options": opts_list,
                        "correct_options": correct_opts,
                        "correct_option": correct_opts[0] if correct_opts else ""
                    }

                # 3. Create initial QuestionVersion (v1, DRAFT)
                version = QuestionVersion.objects.create(
                    question=question,
                    version_number=1,
                    question_type=dto.type,
                    title=dto.title,
                    description=dto.statement,
                    instructions=dto.instructions,
                    points=dto.points,
                    negative_marking_enabled=(dto.negative_points > 0),
                    negative_points=dto.negative_points,
                    difficulty=dto.difficulty,
                    status=VersionStatus.DRAFT,
                    type_config=type_config,
                    created_by=actor
                )

                # 4. If CODING, create CodingQuestionConfig & TestCase records
                if dto.type == "CODING" and dto.coding:
                    coding_conf = CodingQuestionConfig.objects.create(
                        question_version=version,
                        problem_statement=dto.statement,
                        constraints=dto.coding.constraints,
                        allowed_languages=dto.coding.languages,
                        time_limit_ms=dto.coding.execution_time_ms,
                        memory_limit_mb=dto.coding.memory_mb,
                        starter_codes=dto.coding.starter_codes,
                        examples=dto.coding.examples
                    )

                    for idx, tc in enumerate(dto.test_cases):
                        TestCase.objects.create(
                            coding_config=coding_conf,
                            name=tc.case_id,
                            input_data=tc.input,
                            expected_output=tc.expected_output,
                            points=tc.points,
                            is_hidden=(tc.visibility == "HIDDEN"),
                            is_verified=tc.is_verified,
                            execution_order=idx + 1
                        )

                created_questions.append({
                    "question_id": str(question.id),
                    "version_id": str(version.id),
                    "import_id": dto.question_id,
                    "title": dto.title,
                    "type": dto.type,
                    "version_number": 1,
                    "status": "DRAFT"
                })

                AuditService.log(
                    action="QUESTION_IMPORTED_CANONICAL",
                    actor=actor,
                    target_type="Question",
                    target_id=str(question.id),
                    metadata={
                        "import_id": dto.question_id,
                        "title": dto.title,
                        "type": dto.type,
                        "points": dto.points,
                        "status": "DRAFT"
                    },
                    request=request
                )

        return {
            "created_count": len(created_questions),
            "questions": created_questions,
            "created_questions": created_questions,
            "message": f"Successfully imported {len(created_questions)} question(s) as Draft."
        }
