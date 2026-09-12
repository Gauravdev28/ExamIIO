import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from rest_framework import status
from apps.accounts.models import User, Role, StudentProfile
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentSnapshot,
    TestAttempt,
    AttemptStatus,
)
from apps.results.models import StudentCoinLedger
from apps.results.services import CoinRewardService


class DummyQuestionResult:
    def __init__(self, question_id: str, is_correct: bool):
        self.question_id = question_id
        self.is_correct = is_correct


@pytest.mark.django_db
class TestStudentCoinLedger:
    @pytest.fixture
    def student_a(self):
        user = User.objects.create_user(
            email="alice@test.com",
            password="StrongPassword123!",
            display_name="Alice Candidate",
            role=Role.STUDENT,
            is_active=True,
            first_login_required=False
        )
        StudentProfile.objects.create(user=user, roll_number="CS2026-001", euid="EUID-ALICE")
        return user

    @pytest.fixture
    def student_b(self):
        user = User.objects.create_user(
            email="bob@test.com",
            password="StrongPassword123!",
            display_name="Bob Candidate",
            role=Role.STUDENT,
            is_active=True,
            first_login_required=False
        )
        StudentProfile.objects.create(user=user, roll_number="CS2026-002", euid="EUID-BOB")
        return user

    @pytest.fixture
    def sample_assessment(self, admin_user):
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Coin Trial Assessment",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=30,
            created_by=admin_user,
            status=AssessmentStatus.PUBLISHED
        )
        AssessmentSnapshot.objects.create(
            assessment=assessment,
            version_number=1,
            snapshot_data={},
            server_evaluation_bundle={}
        )
        return assessment

    def test_ledger_immutability_save_update_denied(self, student_a, sample_assessment):
        attempt = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_a,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        entry = StudentCoinLedger.objects.create(
            student=student_a,
            attempt=attempt,
            question_id="q-001",
            coins_awarded=3,
            reason="Correct solution for question q-001"
        )
        assert entry.id is not None
        assert entry.coins_awarded == 3

        # Update should be blocked by PermissionDenied
        entry.coins_awarded = 10
        with pytest.raises(PermissionDenied):
            entry.save()

    def test_ledger_immutability_delete_denied(self, student_a, sample_assessment):
        attempt = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_a,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        entry = StudentCoinLedger.objects.create(
            student=student_a,
            attempt=attempt,
            question_id="q-002",
            coins_awarded=3,
            reason="Correct solution for question q-002"
        )
        with pytest.raises(PermissionDenied):
            entry.delete()

    def test_attempt_question_idempotency_constraint(self, student_a, sample_assessment):
        attempt = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_a,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        StudentCoinLedger.objects.create(
            student=student_a,
            attempt=attempt,
            question_id="q-unique-1",
            coins_awarded=3,
            reason="Initial award"
        )
        with pytest.raises(IntegrityError):
            StudentCoinLedger.objects.create(
                student=student_a,
                attempt=attempt,
                question_id="q-unique-1",
                coins_awarded=3,
                reason="Duplicate award attempt"
            )

    def test_award_coins_for_finalized_attempt_strict_plus_3(self, student_a, sample_assessment):
        attempt = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_a,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        results = [
            DummyQuestionResult("q-mcq-1", is_correct=True),
            DummyQuestionResult("q-mcq-2", is_correct=False),
            DummyQuestionResult("q-coding-1", is_correct=True),
        ]

        # First run: 2 correct questions -> strictly 6 coins
        awarded = CoinRewardService.award_coins_for_finalized_attempt(attempt, results)
        assert awarded == 6
        assert CoinRewardService.get_student_coin_summary(student_a)['total_coins'] == 6

        # Idempotent re-run: 0 new coins awarded
        awarded_again = CoinRewardService.award_coins_for_finalized_attempt(attempt, results)
        assert awarded_again == 0
        assert CoinRewardService.get_student_coin_summary(student_a)['total_coins'] == 6

    def test_student_coins_summary_and_leaderboard_api(self, api_client, student_a, student_b, sample_assessment):
        attempt_a = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_a,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        StudentCoinLedger.objects.create(
            student=student_a,
            attempt=attempt_a,
            question_id="q-1",
            coins_awarded=3,
            reason="Correct"
        )
        StudentCoinLedger.objects.create(
            student=student_a,
            attempt=attempt_a,
            question_id="q-2",
            coins_awarded=3,
            reason="Correct"
        )

        attempt_b = TestAttempt.objects.create(
            assessment=sample_assessment,
            assessment_snapshot=sample_assessment.snapshot,
            student=student_b,
            status=AttemptStatus.SUBMITTED,
            submitted_at=sample_assessment.start_datetime
        )
        StudentCoinLedger.objects.create(
            student=student_b,
            attempt=attempt_b,
            question_id="q-1",
            coins_awarded=3,
            reason="Correct"
        )

        # Student A calls coins summary
        api_client.force_authenticate(user=student_a)
        res = api_client.get('/api/v1/student/coins/')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['total_coins'] == 6
        assert len(data['history']) == 2

        # Leaderboard check: Alice (6) > Bob (3)
        res_lb = api_client.get('/api/v1/student/coins/leaderboard/')
        assert res_lb.status_code == status.HTTP_200_OK
        lb_data = res_lb.data['data']
        lb = lb_data['leaderboard']
        assert len(lb) >= 2
        assert lb[0]['name'] == student_a.display_name
        assert lb[0]['coins'] == 6
        assert lb[0]['rank'] == 1
        assert lb[1]['name'] == student_b.display_name
        assert lb[1]['coins'] == 3
        assert lb[1]['rank'] == 2
        assert lb_data['current_user_rank'] == 1
        assert lb_data['current_user_coins'] == 6
