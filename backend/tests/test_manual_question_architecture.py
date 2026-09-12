import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError
from apps.accounts.models import User
from apps.questions.models import (
    Question,
    QuestionVersion,
    CodingQuestionConfig,
    TestCase,
    QuestionType,
    Difficulty,
    VersionStatus,
)
from apps.questions.services import QuestionService, CodingQuestionValidationService
from apps.questions.canonical import (
    CanonicalQuestionDTO,
    CanonicalOptionDTO,
    CanonicalCodingConfigDTO,
    CanonicalTestCaseDTO,
    validate_and_normalize_canonical_question,
)


@pytest.mark.django_db
class TestManualQuestionArchitecture:
    """
    Validation tests for the Simple Manual Question Architecture:
    - Exactly 11 DATA health checks + 1 separate ENVIRONMENT check
    - Parity between Manual Authoring and Excel v1 via CanonicalQuestionDTO
    - Draft creation, publication requirements, and immutable versioning
    """

    @pytest.fixture(autouse=True)
    def setup_admin_user(self):
        self.admin = User.objects.create_superuser(
            email='manual_q_admin@codeguard.internal',
            password='AdminPassword123!'
        )

    def test_question_health_has_exactly_11_data_checks(self):
        """Question health assessment evaluates exactly 11 DATA checks and 1 ENVIRONMENT check."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Sum Two Integers',
            description='Read two integers from stdin and print sum.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON', 'CPP', 'JAVA'],
                'starter_codes': {
                    'PYTHON': 'def solve(): pass\n',
                    'CPP': 'int main() { return 0; }\n',
                    'JAVA': 'public class Solution { public static void main(String[] args) {} }\n'
                },
                'examples': [{'input': '1 2', 'output': '3', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '1 2',
                    'expected_output': '3',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '3 4',
                    'expected_output': '7',
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
        data_checks = [c for c in health['checks'] if c['category'] == 'DATA']
        env_checks = [c for c in health['checks'] if c['category'] == 'ENVIRONMENT']

        assert len(data_checks) == 11, f"Expected 11 DATA checks, found {len(data_checks)}"
        assert health['total_data_checks'] == 11
        assert len(env_checks) == 1
        assert env_checks[0]['key'] in ('judge0_execution', 'sandbox_execution')

        expected_data_keys = [
            'problem_statement',
            'examples',
            'languages',
            'starter_code',
            'sample_tests',
            'hidden_tests',
            'expected_output_verification',
            'expected_outputs',
            'scoring_configuration',
            'point_sum_invariant',
            'duplicate_inputs',
        ]
        actual_data_keys = [c['key'] for c in data_checks]
        assert actual_data_keys == expected_data_keys

    def test_environment_status_is_separate_from_data_health(self):
        """is_data_ready is True when all 11 DATA checks pass even if environment_ready is False."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Healthy Data Problem',
            description='Complete description for data readiness check.',
            points=10,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'print("ready")\n'},
                'examples': [{'input': '0', 'output': '0', 'explanation': ''}],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '0',
                    'expected_output': '0',
                    'points': 5,
                    'is_hidden': False,
                    'is_example': True,
                    'is_verified': True,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '1',
                    'expected_output': '1',
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
        assert health['passed_data_checks'] == 11
        assert health['is_data_ready'] is True
        # Environment is reported independently
        assert 'environment_ready' in health

    def test_manual_mcq_uses_canonical_dto(self):
        """Manual MCQ creation constructs and validates CanonicalQuestionDTO."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title='Capital of France',
            description='What is the capital of France?',
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                'options': [
                    {'id': 'A', 'text': 'Paris', 'is_correct': True},
                    {'id': 'B', 'text': 'London', 'is_correct': False},
                ],
                'correct_options': ['A']
            },
            actor=self.admin
        )
        assert version.question_type == QuestionType.MCQ
        assert version.title == 'Capital of France'
        assert version.status == VersionStatus.DRAFT

    def test_manual_coding_uses_canonical_dto(self):
        """Manual Coding creation constructs and validates CanonicalQuestionDTO."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Array Sum',
            description='Sum elements of an array.',
            points=10,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'def sum_arr(a): pass\n'},
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'name': 'TC1',
                    'input_data': '1 2 3',
                    'expected_output': '6',
                    'points': 5,
                    'is_hidden': False,
                    'execution_order': 1
                },
                {
                    'name': 'TC2',
                    'input_data': '4 5 6',
                    'expected_output': '15',
                    'points': 5,
                    'is_hidden': True,
                    'execution_order': 2
                }
            ],
            actor=self.admin
        )
        assert version.question_type == QuestionType.CODING
        assert version.coding_config.allowed_languages == ['PYTHON']

    def test_manual_mcq_matches_excel_contract(self):
        """Manual MCQ normalized representation matches CanonicalQuestionDTO specification."""
        manual_dto = CanonicalQuestionDTO(
            question_id="Q-MCQ-01",
            title="Python Type Check",
            type="MCQ",
            statement="What is type([])?",
            instructions="Select one.",
            difficulty="EASY",
            points=5,
            negative_points=0,
            options=[
                CanonicalOptionDTO("A", "list", True),
                CanonicalOptionDTO("B", "dict", False),
            ]
        )
        norm_dto, errors, warnings = validate_and_normalize_canonical_question(manual_dto)
        assert len(errors) == 0
        assert norm_dto.type == "MCQ"
        assert len(norm_dto.options) == 2
        assert norm_dto.options[0].is_correct is True

    def test_manual_coding_matches_excel_contract(self):
        """Manual Coding normalized representation matches CanonicalQuestionDTO specification."""
        manual_dto = CanonicalQuestionDTO(
            question_id="Q-COD-01",
            title="Factorial",
            type="CODING",
            statement="Compute n!",
            instructions="Print factorial of n.",
            difficulty="MEDIUM",
            points=10,
            negative_points=0,
            coding=CanonicalCodingConfigDTO(
                languages=["PYTHON", "CPP"],
                starter_codes={"PYTHON": "def f(n): pass\n", "CPP": "int f(int n) {}\n"},
                constraints="1 <= n <= 20",
                execution_time_ms=2000,
                memory_mb=256,
                examples=[{"input": "5", "output": "120"}]
            ),
            test_cases=[
                CanonicalTestCaseDTO("TC01", "SAMPLE", "5", "120", 5, is_example=True),
                CanonicalTestCaseDTO("TC02", "HIDDEN", "6", "720", 5, is_example=False),
            ]
        )
        norm_dto, errors, warnings = validate_and_normalize_canonical_question(manual_dto)
        assert len(errors) == 0
        assert norm_dto.type == "CODING"
        assert norm_dto.coding.languages == ["PYTHON", "CPP"]
        assert len(norm_dto.test_cases) == 2

    def test_manual_validation_matches_excel_validation(self):
        """Manual authoring rejects invalid parameters just like Excel import."""
        # Negative points > total points
        with pytest.raises(DRFValidationError):
            QuestionService.create_question(
                question_type=QuestionType.MCQ,
                title='Negative Points Mismatch',
                description='Description',
                points=10,
                negative_marking_enabled=True,
                negative_points=20,
                difficulty=Difficulty.MEDIUM,
                type_config={
                    'options': [
                        {'id': 'A', 'text': 'A', 'is_correct': True},
                        {'id': 'B', 'text': 'B', 'is_correct': False},
                    ]
                },
                actor=self.admin
            )

        # Unsupported language
        with pytest.raises(DRFValidationError):
            QuestionService.create_question(
                question_type=QuestionType.CODING,
                title='Invalid Language Problem',
                description='Description',
                points=10,
                difficulty=Difficulty.MEDIUM,
                coding_config_data={
                    'allowed_languages': ['RUST_UNSUPPORTED'],
                    'starter_codes': {'RUST_UNSUPPORTED': 'fn main() {}\n'},
                },
                test_cases_data=[
                    {'name': 'TC1', 'input_data': '1', 'expected_output': '1', 'points': 10, 'is_hidden': False},
                ],
                actor=self.admin
            )

    def test_manual_save_creates_draft(self):
        """Saving a manual question creates a question in DRAFT status."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title='Draft Question Test',
            description='Question text',
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                'options': [
                    {'id': 'A', 'text': 'Opt 1', 'is_correct': True},
                    {'id': 'B', 'text': 'Opt 2', 'is_correct': False},
                ]
            },
            actor=self.admin
        )
        assert version.status == VersionStatus.DRAFT
        assert version.version_number == 1

    def test_manual_publish_requires_health(self):
        """Publishing a coding question requires data health checks to pass."""
        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Unverified Test Problem',
            description='Description',
            points=10,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON'],
                'starter_codes': {'PYTHON': 'def solve(): pass\n'},
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {'name': 'TC1', 'input_data': '1', 'expected_output': '1', 'points': 5, 'is_hidden': False, 'is_example': True, 'is_verified': False},
                {'name': 'TC2', 'input_data': '2', 'expected_output': '2', 'points': 5, 'is_hidden': True, 'is_example': False, 'is_verified': True},
            ],
            actor=self.admin
        )

        # Fails publish because TC1 is unverified
        with pytest.raises(DRFValidationError) as exc:
            QuestionService.publish_version(version, actor=self.admin)
        assert "verification" in str(exc.value).lower() or "health" in str(exc.value).lower()

        # Mark verified and publish succeeds
        tc1 = version.coding_config.test_cases.get(name='TC1')
        tc1.is_verified = True
        tc1.save()

        pub = QuestionService.publish_version(version, actor=self.admin)
        assert pub.status == VersionStatus.PUBLISHED

    def test_manual_edit_published_creates_new_version(self):
        """Published questions are immutable: draft version creation is rejected; duplicate creates a new question."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        question, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title='Version Test Question',
            description='Question text',
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                'options': [
                    {'id': 'A', 'text': 'Opt 1', 'is_correct': True},
                    {'id': 'B', 'text': 'Opt 2', 'is_correct': False},
                ]
            },
            actor=self.admin
        )
        published_v1 = QuestionService.publish_version(v1, actor=self.admin)
        assert published_v1.status == VersionStatus.PUBLISHED
        assert published_v1.version_number == 1

        # Attempting to branch a published question is strictly rejected
        with pytest.raises(DRFValidationError) as exc:
            QuestionService.get_or_create_draft_version(question=question, actor=self.admin)
        assert "immutable" in str(exc.value).lower()

        # Duplicating creates a completely new question in DRAFT
        new_q, new_v = QuestionService.duplicate_question(question=question, actor=self.admin)
        assert new_q.id != question.id
        assert new_v.status == VersionStatus.DRAFT
        assert new_v.version_number == 1
        assert "Copy" in new_v.title

        # Ensure published v1 remains immutable and published
        v1_reloaded = QuestionVersion.objects.get(id=v1.id)
        assert v1_reloaded.status == VersionStatus.PUBLISHED

    def test_manual_published_version_immutable(self):
        """Updating a published version directly raises an error and is blocked."""
        from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
        question, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title='Immutable Question',
            description='Original text',
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                'options': [
                    {'id': 'A', 'text': 'Opt 1', 'is_correct': True},
                    {'id': 'B', 'text': 'Opt 2', 'is_correct': False},
                ]
            },
            actor=self.admin
        )
        published_v1 = QuestionService.publish_version(v1, actor=self.admin)
        assert published_v1.status == VersionStatus.PUBLISHED

        with pytest.raises((DRFValidationError, DjangoPermissionDenied)):
            QuestionService.update_draft_version(
                version=published_v1,
                title='Mutated Title Attempt',
                actor=self.admin
            )
