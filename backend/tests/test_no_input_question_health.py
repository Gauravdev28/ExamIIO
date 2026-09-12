import pytest
from django.contrib.auth import get_user_model
from apps.questions.models import Question, QuestionVersion, CodingQuestionConfig, TestCase, QuestionType, Difficulty
from apps.questions.services import QuestionService, CodingQuestionValidationService
from apps.questions.canonical import (
    CanonicalQuestionDTO,
    CanonicalCodingConfigDTO,
    CanonicalTestCaseDTO,
    validate_and_normalize_canonical_question,
    is_no_input_coding_dto
)

User = get_user_model()


@pytest.mark.django_db
class TestNoInputQuestionHealthValidation:
    """
    Authoritative test suite for NO-INPUT coding questions health validation.
    Verifies:
    1. no-input question + empty input + expected output -> Examples PASS
    2. no-input question + empty input + empty output -> Examples ERROR
    3. input-based question + empty input -> Examples ERROR
    4. no-input question + sample + hidden tests both empty input -> Duplicate Inputs does NOT block
    5. input-based question + duplicate non-empty inputs -> Duplicate Inputs ERROR
    6. hidden test with expected output + positive points -> Hidden Tests PASS
    7. sample + hidden points preserve total question points
    """

    @pytest.fixture(autouse=True)
    def setup_admin(self):
        self.admin = User.objects.create_superuser(
            email='health_admin@codeguard.test',
            password='Password123!',
            role='ADMIN'
        )

    def test_no_input_question_examples_pass_with_empty_input_and_expected_output(self):
        """1. no-input question + empty input + expected output -> Examples PASS"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Print Hello World',
            description='Write a program that prints Hello World to the console.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print("Hello World")\n'},
                'constraints': 'No input is required.',
                'examples': [{'input': '', 'output': 'Hello World', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        health = CodingQuestionValidationService.get_health_status(version)
        ex_check = next(c for c in health['checks'] if c['key'] == 'examples')
        assert ex_check['passed'] is True
        assert ex_check['status'] == 'PASS'
        assert '1 example(s) configured' in ex_check['message']

    def test_no_input_question_examples_error_with_empty_output(self):
        """2. no-input question + empty input + empty output -> Examples ERROR"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Print Constant',
            description='Print a constant number.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print(42)\n'},
                'constraints': 'No input is required.',
                'examples': [{'input': '', 'output': '', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '',
                    'expected_output': '42',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '',
                    'expected_output': '42',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        version.coding_config.examples = [{'input': '', 'output': '', 'explanation': ''}]
        version.coding_config.save()

        health = CodingQuestionValidationService.get_health_status(version)
        ex_check = next(c for c in health['checks'] if c['key'] == 'examples')
        assert ex_check['passed'] is False
        assert ex_check['status'] == 'ERROR'

    def test_input_based_question_examples_error_with_empty_input(self):
        """3. input-based question + empty input -> Examples ERROR"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Reverse Array',
            description='Reverse an input array of numbers.',
            points=10,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'arr = input()\n'},
                'constraints': '1 <= n <= 1000',
                'input_description': 'A list of n numbers.',
                'examples': [{'input': '', 'output': '[3, 2, 1]', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '1 2 3',
                    'expected_output': '3 2 1',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '4 5 6',
                    'expected_output': '6 5 4',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        version.coding_config.examples = [{'input': '', 'output': '[3, 2, 1]', 'explanation': ''}]
        version.coding_config.save()

        health = CodingQuestionValidationService.get_health_status(version)
        ex_check = next(c for c in health['checks'] if c['key'] == 'examples')
        assert ex_check['passed'] is False
        assert ex_check['status'] == 'ERROR'
        assert 'No valid example with both input and output was found.' in ex_check['message']

    def test_no_input_question_allows_multiple_empty_inputs_without_blocking(self):
        """4. no-input question + sample + hidden tests both empty input -> Duplicate Inputs does NOT block"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Print Hello World',
            description='Write a program that prints Hello World to the console.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print("Hello World")\n'},
                'constraints': 'No input is required.',
                'examples': [{'input': '', 'output': 'Hello World', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC005',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC006',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        health = CodingQuestionValidationService.get_health_status(version)
        dup_check = next(c for c in health['checks'] if c['key'] == 'duplicate_inputs')
        assert dup_check['passed'] is True
        assert dup_check['status'] == 'PASS'
        assert dup_check['message'] == 'No duplicate test case inputs'

    def test_input_based_question_flags_duplicate_inputs_as_error(self):
        """5. input-based question + duplicate non-empty inputs -> Duplicate Inputs ERROR"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Duplicate Vector Problem',
            description='Find target in array.',
            points=10,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'x = input()\n'},
                'constraints': '1 <= n <= 100',
                'input_description': 'Array input.',
                'examples': [{'input': '5 10', 'output': '15', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '5 10',
                    'expected_output': '15',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '5 10',  # Duplicate!
                    'expected_output': '15',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        health = CodingQuestionValidationService.get_health_status(version)
        dup_check = next(c for c in health['checks'] if c['key'] == 'duplicate_inputs')
        assert dup_check['passed'] is False
        assert dup_check['status'] == 'ERROR'
        assert 'Duplicate test case inputs detected' in dup_check['message']

    def test_hidden_test_with_expected_output_and_positive_points_passes(self):
        """6. hidden test with expected output + positive points -> Hidden Tests PASS"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Print Hello World',
            description='Write a program that prints Hello World to the console.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print("Hello World")\n'},
                'constraints': 'No input is required.',
                'examples': [{'input': '', 'output': 'Hello World', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC005',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC006',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        health = CodingQuestionValidationService.get_health_status(version)
        hidden_check = next(c for c in health['checks'] if c['key'] == 'hidden_tests')
        assert hidden_check['passed'] is True
        assert hidden_check['status'] == 'PASS'
        assert '1 hidden test(s) configured' in hidden_check['message']

    def test_sample_and_hidden_points_preserve_total_question_points(self):
        """7. sample + hidden points preserve total question points"""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Print Hello World',
            description='Write a program that prints Hello World to the console.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print("Hello World")\n'},
                'constraints': 'No input is required.',
                'examples': [{'input': '', 'output': 'Hello World', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC005',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC006',
                    'input_data': '',
                    'expected_output': 'Hello World',
                    'points': 5,
                    'is_hidden': True,
                    'is_example': False,
                    'is_verified': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )

        health = CodingQuestionValidationService.get_health_status(version)
        psi_check = next(c for c in health['checks'] if c['key'] == 'point_sum_invariant')
        assert psi_check['passed'] is True
        assert psi_check['status'] == 'PASS'
        assert health['passed_data_checks'] == 11
        assert health['is_data_ready'] is True
        assert len(health['errors']) == 0 or (len(health['errors']) == 1 and ('Judge0' in health['errors'][0] or 'Piston' in health['errors'][0] or 'sandbox' in health['errors'][0].lower()))

    def test_canonical_dto_no_input_duplicate_check(self):
        """Canonical DTO validation permits empty inputs for NO-INPUT questions."""
        dto = CanonicalQuestionDTO(
            question_id='Q004',
            title='Print Hello World',
            type='CODING',
            statement='Write a program that prints Hello World to the console.',
            instructions='',
            difficulty='EASY',
            points=10,
            negative_points=0,
            coding=CanonicalCodingConfigDTO(
                languages=['PYTHON'],
                starter_codes={'PYTHON': 'print("Hello World")'},
                constraints='No input is required.',
                examples=[{'input': '', 'output': 'Hello World', 'explanation': ''}]
            ),
            test_cases=[
                CanonicalTestCaseDTO(case_id='TC005', visibility='SAMPLE', input='', expected_output='Hello World', points=5, is_example=True, is_verified=True),
                CanonicalTestCaseDTO(case_id='TC006', visibility='HIDDEN', input='', expected_output='Hello World', points=5, is_example=False, is_verified=True),
            ]
        )

        norm_dto, errors, warnings = validate_and_normalize_canonical_question(dto)
        assert len(errors) == 0, f"Expected 0 errors, found: {errors}"
        # No duplicate input warning for empty inputs on no-input questions
        assert not any('duplicate normalized input' in w for w in warnings)
