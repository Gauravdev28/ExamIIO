import io
import json
import zipfile
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User
from .models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    CodingLanguage,
    VersionStatus,
)
from .services import QuestionService

logger = logging.getLogger(__name__)


class CodingQuestionPayloadNormalizer:
    """
    Authoritative normalizer for coding question payloads across all import sources
    (HackerRank, LeetCode, ZIP packages, JSON exports, etc.).
    Enforces deterministic contracts:
    - Language enablement synchronized with starter code (Option A).
    - Examples extracted strictly from explicit examples or public sample tests (never hidden tests).
    - Deterministic point distribution across test cases ensuring sum equals question points (P >= N).
    - Automatic verification for explicitly supplied, valid, non-placeholder expected outputs.
    """

    VALID_LANG_CHOICES = {c[0] for c in CodingLanguage.choices}
    PLACEHOLDER_OUTPUTS = {'TODO', 'TBD', '?', '[PLACEHOLDER]', 'NONE', 'NULL'}

    @classmethod
    def normalize_starter_codes_and_languages(
        cls,
        raw_languages: Any,
        starter_data: Any
    ) -> tuple[List[str], Dict[str, str]]:
        # 1. Normalize starter codes
        starter_codes: Dict[str, str] = {}
        if isinstance(starter_data, dict):
            for k, v in starter_data.items():
                k_up = str(k).upper()
                code_str = str(v) if v is not None else ""
                if not code_str.strip():
                    continue
                if 'PYTHON' in k_up or k_up == 'PY':
                    starter_codes[CodingLanguage.PYTHON] = code_str
                elif 'CPP' in k_up or 'C++' in k_up:
                    starter_codes[CodingLanguage.CPP] = code_str
                elif 'JAVA' in k_up:
                    starter_codes[CodingLanguage.JAVA] = code_str
                elif k_up in ('C', 'C99', 'C11', 'C_LANG'):
                    starter_codes[CodingLanguage.C] = code_str
        elif isinstance(starter_data, str) and starter_data.strip():
            starter_codes[CodingLanguage.PYTHON] = starter_data

        # 2. Normalize requested languages
        req_langs: List[str] = []
        if isinstance(raw_languages, list):
            for l in raw_languages:
                l_up = str(l).upper()
                if ('PYTHON' in l_up or l_up == 'PY') and CodingLanguage.PYTHON not in req_langs:
                    req_langs.append(CodingLanguage.PYTHON)
                elif ('CPP' in l_up or 'C++' in l_up) and CodingLanguage.CPP not in req_langs:
                    req_langs.append(CodingLanguage.CPP)
                elif 'JAVA' in l_up and CodingLanguage.JAVA not in req_langs:
                    req_langs.append(CodingLanguage.JAVA)
                elif l_up in ('C', 'C99', 'C11', 'C_LANG') and CodingLanguage.C not in req_langs:
                    req_langs.append(CodingLanguage.C)
        elif isinstance(raw_languages, str) and raw_languages.strip():
            for part in raw_languages.split(','):
                p_up = part.strip().upper()
                if ('PYTHON' in p_up or p_up == 'PY') and CodingLanguage.PYTHON not in req_langs:
                    req_langs.append(CodingLanguage.PYTHON)
                elif ('CPP' in p_up or 'C++' in p_up) and CodingLanguage.CPP not in req_langs:
                    req_langs.append(CodingLanguage.CPP)
                elif 'JAVA' in p_up and CodingLanguage.JAVA not in req_langs:
                    req_langs.append(CodingLanguage.JAVA)
                elif p_up in ('C', 'C99', 'C11', 'C_LANG') and CodingLanguage.C not in req_langs:
                    req_langs.append(CodingLanguage.C)

        if not req_langs:
            req_langs = [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA, CodingLanguage.C]

        # 3. Option A Enforcement: Only enable languages that actually have starter code
        # If starter codes exist for a subset of languages, restrict allowed_languages to those languages.
        # If no starter codes exist at all, keep requested languages so health check clearly reports missing starter code.
        if starter_codes:
            enabled_langs = [l for l in req_langs if l in starter_codes]
            if not enabled_langs:
                # If requested languages had no match with starter_codes keys, use the starter_codes keys
                enabled_langs = [l for l in starter_codes.keys() if l in cls.VALID_LANG_CHOICES]
            if not enabled_langs:
                enabled_langs = [CodingLanguage.PYTHON]
        else:
            enabled_langs = req_langs

        return enabled_langs, starter_codes

    @classmethod
    def normalize_test_cases(
        cls,
        payload_data: Dict[str, Any],
        total_points: int
    ) -> List[Dict[str, Any]]:
        raw_tests = []
        # Check test_cases / testCases
        if payload_data.get('test_cases') and isinstance(payload_data['test_cases'], list):
            raw_tests = payload_data['test_cases']
        elif payload_data.get('testCases') and isinstance(payload_data['testCases'], list):
            raw_tests = payload_data['testCases']
        else:
            # Check separate sample_tests and hidden_tests
            samples = payload_data.get('sample_tests') or payload_data.get('sampleTests') or []
            hiddens = payload_data.get('hidden_tests') or payload_data.get('hiddenTests') or []
            if isinstance(samples, list) and samples:
                for s in samples:
                    if isinstance(s, dict):
                        item = dict(s)
                        item['is_hidden'] = False
                        raw_tests.append(item)
            if isinstance(hiddens, list) and hiddens:
                for h in hiddens:
                    if isinstance(h, dict):
                        item = dict(h)
                        item['is_hidden'] = True
                        raw_tests.append(item)

        test_cases: List[Dict[str, Any]] = []
        for idx, tc in enumerate(raw_tests, start=1):
            if not isinstance(tc, dict):
                continue
            input_val = str(tc.get('input_data', tc.get('input', '')))
            output_val = str(tc.get('expected_output', tc.get('output', '')))
            is_hidden = bool(tc.get('is_hidden', tc.get('hidden', False)))

            # Verification rule: if expected output is valid non-empty non-placeholder, auto-verify
            clean_out = output_val.strip()
            if 'is_verified' in tc:
                is_verified = bool(tc['is_verified'])
            else:
                is_verified = bool(clean_out and clean_out.upper() not in cls.PLACEHOLDER_OUTPUTS)

            raw_pts = tc.get('points')
            pts = int(raw_pts) if raw_pts is not None and str(raw_pts).isdigit() else 1

            test_cases.append({
                "name": tc.get('name') or f"{'Hidden' if is_hidden else 'Sample'} Case {idx}",
                "input_data": input_val,
                "expected_output": output_val,
                "points": max(1, pts),
                "is_hidden": is_hidden,
                "is_verified": is_verified,
                "execution_order": idx
            })

        # Deterministic point normalization with safety condition (P >= N)
        n_tests = len(test_cases)
        if n_tests > 0:
            if total_points < n_tests:
                raise DRFValidationError({
                    "points": f"Question has {total_points} points but {n_tests} scored test cases require at least 1 point each. Increase question points or reduce scored test cases."
                })

            current_sum = sum(tc['points'] for tc in test_cases)
            if current_sum != total_points:
                base = total_points // n_tests
                rem = total_points % n_tests
                for idx, tc in enumerate(test_cases):
                    tc['points'] = base + 1 if idx < rem else base

        return test_cases

    @classmethod
    def normalize_examples(
        cls,
        payload_data: Dict[str, Any],
        test_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        raw_examples = payload_data.get('examples')
        examples: List[Dict[str, Any]] = []

        # Priority 1: Explicit examples
        if isinstance(raw_examples, list) and raw_examples:
            for ex in raw_examples:
                if isinstance(ex, dict):
                    in_val = str(ex.get('input', '')).strip()
                    out_val = str(ex.get('output', '')).strip()
                    if in_val != "" and out_val != "":
                        explanation = str(ex.get('explanation', '')).strip()
                        examples.append({
                            "input": in_val,
                            "output": out_val,
                            "explanation": explanation
                        })

        # Priority 2: Extract from public sample test cases ONLY (never hidden tests)
        if not examples and test_cases:
            for tc in test_cases:
                if not tc['is_hidden']:
                    in_val = str(tc['input_data']).strip()
                    out_val = str(tc['expected_output']).strip()
                    if in_val != "" and out_val != "":
                        examples.append({
                            "input": in_val,
                            "output": out_val,
                            "explanation": ""
                        })

        return examples


class HackerRankQuestionImporter:
    """
    Authorized HackerRank API question importer.
    Strict security policy:
    - Never uses web scraping, crawling, or private/undocumented web endpoints.
    - Operates strictly through authorized account API credentials.
    """

    @classmethod
    def is_configured(cls) -> bool:
        token = getattr(settings, 'HACKERRANK_API_TOKEN', '') or ''
        return bool(token.strip())

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        configured = cls.is_configured()
        return {
            "configured": configured,
            "auth_mode": "BEARER_TOKEN" if configured else "UNCONFIGURED",
            "message": "HackerRank official integration active" if configured else "HackerRank integration not configured. Provide API credentials or use manual import."
        }

    @classmethod
    def import_by_slug_or_data(cls, slug_or_id: str = "", payload_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = payload_data or {}
        has_content = bool(data.get('body') or data.get('problem_statement') or data.get('description'))

        if not cls.is_configured() and not has_content:
            raise DRFValidationError({
                "hackerrank": "HackerRank authorized integration is not configured. Configure HACKERRANK_API_TOKEN or import via structured content."
            })

        title = data.get('name') or data.get('title') or (slug_or_id.replace('-', ' ').title() if slug_or_id else "Imported HackerRank Problem")
        problem_text = data.get('body') or data.get('problem_statement') or data.get('description') or ""
        constraints = data.get('constraints') or ""
        input_format = data.get('input_format') or ""
        output_format = data.get('output_format') or ""
        
        diff_raw = (data.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        raw_points = data.get('points') or data.get('total_points') or 10
        total_points = max(1, int(raw_points))

        # Starter code & languages (Option A)
        starter_data = data.get('starter_codes') or data.get('starter_code') or data.get('starterCode')
        allowed_languages, starter_codes = CodingQuestionPayloadNormalizer.normalize_starter_codes_and_languages(
            data.get('languages'), starter_data
        )

        # Test cases
        test_cases = CodingQuestionPayloadNormalizer.normalize_test_cases(data, total_points)

        # Examples (Priority 1: explicit; Priority 2: public samples only)
        examples = CodingQuestionPayloadNormalizer.normalize_examples(data, test_cases)

        ref_solutions = data.get('reference_solutions') or {}
        ref_lang = data.get('reference_solution_language') or (next(iter(ref_solutions.keys())) if ref_solutions else "")

        return {
            "source": "HACKERRANK",
            "title": title,
            "description": problem_text,
            "difficulty": difficulty,
            "points": total_points,
            "tags": data.get('tags', ['hackerrank', 'algorithms']),
            "coding_config": {
                "problem_statement": problem_text,
                "input_description": input_format,
                "output_description": output_format,
                "constraints": constraints,
                "allowed_languages": allowed_languages,
                "starter_codes": starter_codes,
                "examples": examples,
                "reference_solutions": ref_solutions,
                "reference_solution_language": ref_lang,
                "reference_solution_verified": False,
                "time_limit_ms": min(5000, max(500, int(data.get('time_limit_ms', 2000)))),
                "memory_limit_mb": min(512, max(64, int(data.get('memory_limit_mb', 256)))),
            },
            "test_cases": test_cases
        }


class LeetCodeManualImporter:
    """
    LeetCode Structured / Manual Importer.
    Strict compliance policy:
    - LeetCode's Terms prohibit crawling, scraping, and unauthorized spidering.
    - This importer operates STRICTLY on administrator-provided structured content,
      JSON exports, or manual text, NEVER through automated scraping.
    """

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "configured": False,
            "auth_mode": "MANUAL_IMPORT_REQUIRED",
            "message": "LeetCode terms prohibit automated scraping. Import via pasted content or structured files."
        }

    @classmethod
    def import_structured_content(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if 'url' in payload and not payload.get('problem_statement') and not payload.get('content'):
            raise DRFValidationError({
                "leetcode": "Direct web URL scraping of LeetCode is prohibited by Terms of Service. Please paste question content or upload a structured export."
            })

        title = payload.get('title') or "Imported LeetCode Problem"
        problem_text = payload.get('problem_statement') or payload.get('content') or payload.get('description') or ""
        constraints = payload.get('constraints') or ""
        input_format = payload.get('input_format') or ""
        output_format = payload.get('output_format') or ""

        diff_raw = (payload.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        raw_points = payload.get('points') or payload.get('total_points') or 10
        total_points = max(1, int(raw_points))

        # Starter code & languages (Option A)
        starter_data = payload.get('starter_codes') or payload.get('starter_code') or payload.get('starterCode') or payload.get('code_template')
        allowed_languages, starter_codes = CodingQuestionPayloadNormalizer.normalize_starter_codes_and_languages(
            payload.get('languages') or payload.get('allowed_languages'), starter_data
        )

        # Test cases
        test_cases = CodingQuestionPayloadNormalizer.normalize_test_cases(payload, total_points)

        # Examples (Priority 1: explicit; Priority 2: public samples only)
        examples = CodingQuestionPayloadNormalizer.normalize_examples(payload, test_cases)

        return {
            "source": "LEETCODE_MANUAL",
            "title": title,
            "description": problem_text,
            "difficulty": difficulty,
            "points": total_points,
            "tags": payload.get('tags', ['leetcode', 'algorithms']),
            "coding_config": {
                "problem_statement": problem_text,
                "input_description": input_format,
                "output_description": output_format,
                "constraints": constraints,
                "allowed_languages": allowed_languages,
                "starter_codes": starter_codes,
                "examples": examples,
                "reference_solutions": payload.get('reference_solutions', {}),
                "reference_solution_language": payload.get('reference_solution_language', ''),
                "reference_solution_verified": False,
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
            },
            "test_cases": test_cases
        }


class PackageZipImporter:
    """
    Standard CODEGUARD ZIP / Structured Package Importer.
    Expects a ZIP archive with:
    - question.json (metadata, problem, config, test cases)
    - or problem.md + metadata.json + testcases/
    """

    @classmethod
    def import_zip_file(cls, zip_bytes: bytes) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                file_list = zf.namelist()
                
                # Check for question.json
                q_json_path = next((f for f in file_list if f.endswith('question.json')), None)
                if q_json_path:
                    data = json.loads(zf.read(q_json_path).decode('utf-8'))
                    return cls._normalize_package_data(data, zf, file_list)

                # Fallback: check for metadata.json + problem.md
                meta_path = next((f for f in file_list if f.endswith('metadata.json')), None)
                prob_path = next((f for f in file_list if f.endswith('problem.md') or f.endswith('README.md')), None)
                
                if meta_path and prob_path:
                    data = json.loads(zf.read(meta_path).decode('utf-8'))
                    data['problem_statement'] = zf.read(prob_path).decode('utf-8')
                    return cls._normalize_package_data(data, zf, file_list)

                raise DRFValidationError({
                    "zip_file": "ZIP archive must contain 'question.json' or 'metadata.json' and 'problem.md'."
                })
        except zipfile.BadZipFile:
            raise DRFValidationError({"zip_file": "Uploaded file is not a valid ZIP archive."})
        except json.JSONDecodeError:
            raise DRFValidationError({"zip_file": "Package JSON file contains invalid syntax."})

    @classmethod
    def _normalize_package_data(cls, data: Dict[str, Any], zf: zipfile.ZipFile, file_list: List[str]) -> Dict[str, Any]:
        title = data.get('title') or "Imported Package Problem"
        problem_statement = data.get('problem_statement') or data.get('description') or ""
        diff_raw = (data.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        raw_points = data.get('points') or data.get('total_points') or 10
        total_points = max(1, int(raw_points))

        # Check for directory-based test cases: testcases/in_*.txt, testcases/out_*.txt
        in_files = sorted([f for f in file_list if '/in' in f or f.startswith('in') or 'input' in f])
        if not data.get('test_cases') and not data.get('sample_tests') and in_files:
            file_tcs = []
            idx = 1
            for in_f in in_files:
                out_f = in_f.replace('in', 'out').replace('input', 'output')
                if out_f in file_list:
                    in_content = zf.read(in_f).decode('utf-8')
                    out_content = zf.read(out_f).decode('utf-8')
                    file_tcs.append({
                        "name": f"File Test {idx}",
                        "input_data": in_content,
                        "expected_output": out_content,
                        "points": 5,
                        "is_hidden": idx > 2,
                        "execution_order": idx
                    })
                    idx += 1
            data['test_cases'] = file_tcs

        # Starter code & languages (Option A)
        starter_data = data.get('starter_codes') or data.get('starter_code') or data.get('starterCode')
        allowed_langs, starter_codes = CodingQuestionPayloadNormalizer.normalize_starter_codes_and_languages(
            data.get('allowed_languages') or data.get('languages'), starter_data
        )

        # Test cases
        test_cases = CodingQuestionPayloadNormalizer.normalize_test_cases(data, total_points)

        # Examples (Priority 1: explicit; Priority 2: public samples only)
        examples = CodingQuestionPayloadNormalizer.normalize_examples(data, test_cases)

        return {
            "source": "CODEGUARD_ZIP",
            "title": title,
            "description": problem_statement,
            "difficulty": difficulty,
            "points": total_points,
            "tags": data.get('tags', ['imported-package']),
            "coding_config": {
                "problem_statement": problem_statement,
                "input_description": data.get('input_format', ''),
                "output_description": data.get('output_format', ''),
                "constraints": data.get('constraints', ''),
                "allowed_languages": allowed_langs,
                "starter_codes": starter_codes,
                "examples": examples,
                "reference_solutions": data.get('reference_solutions', {}),
                "reference_solution_language": data.get('reference_solution_language', ''),
                "reference_solution_verified": False,
                "time_limit_ms": min(5000, max(500, int(data.get('time_limit_ms', 2000)))),
                "memory_limit_mb": min(512, max(64, int(data.get('memory_limit_mb', 256)))),
            },
            "test_cases": test_cases
        }


class PlatformImportService:
    """
    Coordinator domain service for all platform imports.
    Enforces invariants:
    - All imported questions are created in DRAFT status with full audit trail.
    - Test cases with valid, explicitly supplied expected outputs are verified.
    - Language enablement matches available starter code.
    - Examples are preserved or safely derived from public samples only.
    """

    @classmethod
    def get_platforms_status(cls) -> Dict[str, Any]:
        return {
            "hackerrank": HackerRankQuestionImporter.get_status(),
            "leetcode": LeetCodeManualImporter.get_status(),
            "zip_package": {
                "supported": True,
                "auth_mode": "DIRECT_UPLOAD",
                "message": "Upload standard question definition ZIP archive"
            },
            "manual_json": {
                "supported": True,
                "auth_mode": "PASTE_JSON",
                "message": "Paste structured problem definition"
            }
        }

    @classmethod
    def parse_preview(cls, source: str, payload_data: Dict[str, Any], file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        src_upper = (source or '').upper()

        if src_upper == 'HACKERRANK':
            normalized = HackerRankQuestionImporter.import_by_slug_or_data(
                slug_or_id=payload_data.get('slug', ''),
                payload_data=payload_data.get('data') or payload_data
            )
        elif src_upper in ('LEETCODE', 'LEETCODE_MANUAL', 'MANUAL_JSON', 'JSON'):
            normalized = LeetCodeManualImporter.import_structured_content(payload_data.get('data') or payload_data)
        elif src_upper in ('CODEGUARD_ZIP', 'ZIP'):
            if not file_bytes:
                raise DRFValidationError({"file": "ZIP file required for package import."})
            normalized = PackageZipImporter.import_zip_file(file_bytes)
        else:
            raise DRFValidationError({"source": f"Unsupported platform source: {source}"})

        # Generate preview metadata
        test_cases = normalized.get('test_cases', [])
        sample_count = len([tc for tc in test_cases if not tc.get('is_hidden')])
        hidden_count = len([tc for tc in test_cases if tc.get('is_hidden')])
        all_verified = bool(test_cases) and all(tc.get('is_verified') for tc in test_cases)
        ref_sol = normalized.get('coding_config', {}).get('reference_solutions', {})

        return {
            "source": normalized['source'],
            "title": normalized['title'],
            "difficulty": normalized['difficulty'],
            "tags": normalized.get('tags', []),
            "languages": normalized['coding_config']['allowed_languages'],
            "examples": normalized['coding_config'].get('examples', []),
            "test_case_count": len(test_cases),
            "sample_test_count": sample_count,
            "hidden_test_count": hidden_count,
            "has_reference_solution": bool(ref_sol),
            "reference_solution_language": normalized['coding_config'].get('reference_solution_language', ''),
            "expected_output_verification_status": "UNVERIFIED",
            "import_status": "DRAFT",
            "normalized_payload": normalized
        }

    @classmethod
    def confirm_and_create_draft(cls, normalized_payload: Dict[str, Any], actor: User, request=None) -> QuestionVersion:
        """
        Atomically creates the imported question in DRAFT status with full audit trail.
        Preserves test case verification states according to the authoritative backend contract.
        """
        if not normalized_payload:
            raise DRFValidationError({"payload": "Normalized payload cannot be empty."})

        coding_config = normalized_payload.get('coding_config', {})
        test_cases = normalized_payload.get('test_cases', [])

        coding_config['reference_solution_verified'] = False
        coding_config['reference_solution_verified_at'] = None

        if normalized_payload.get('source') == 'HACKERRANK':
            for tc in test_cases:
                tc['is_verified'] = False

        with transaction.atomic():
            question, version = QuestionService.create_question(
                question_type=QuestionType.CODING,
                title=normalized_payload['title'],
                description=normalized_payload.get('description', ''),
                instructions=normalized_payload.get('instructions', ''),
                points=normalized_payload.get('points', 10),
                negative_marking_enabled=normalized_payload.get('negative_marking_enabled', False),
                negative_points=normalized_payload.get('negative_points', 0),
                difficulty=normalized_payload.get('difficulty', Difficulty.MEDIUM),
                tags=normalized_payload.get('tags', []),
                coding_config_data=coding_config,
                test_cases_data=test_cases,
                actor=actor,
                request=request
            )

        return version
