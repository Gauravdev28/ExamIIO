import pytest
from decimal import Decimal
from unittest.mock import patch
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    CodingQuestionConfig,
    TestCase,
)
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    AssignmentStatus,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
    ResultVisibility,
)
from apps.assessments.services import (
    AssessmentSnapshotService,
    AttemptService,
)
from apps.results.models import (
    AssessmentResult,
    ResultStatus,
)
from apps.results.services import (
    ResultFinalizationService,
    ResultAccessPolicyService,
)
from apps.proctoring.models import ProctoringSession, RiskBand


@pytest.mark.django_db
class TestResultsAuditFixes:

    @pytest.fixture
    def setup_data(self, db):
        admin_user = User.objects.create_user(
            email="admin_results@codeguard.io",
            password="AdminPassword123!",
            role=Role.ADMIN,
            is_staff=True
        )
        student_1 = User.objects.create_user(
            email="student1@codeguard.io",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        student_2 = User.objects.create_user(
            email="student2@codeguard.io",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        student_3 = User.objects.create_user(
            email="student3@codeguard.io",
            password="StudentPassword123!",
            role=Role.STUDENT
        )

        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Comprehensive Audit Assessment",
            description="Results Audit Test",
            instructions="Follow instructions",
            created_by=admin_user,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timezone.timedelta(hours=1),
            end_datetime=now + timezone.timedelta(hours=5),
            duration_minutes=60,
            total_points=50,
            passing_percentage=Decimal('60.00'),
            attempt_limit=1,
            result_visibility=ResultVisibility.MANUAL,
            negative_marking_enabled=True,
        )

        # Q1: MCQ (10 pts, -2 negative)
        q1 = Question.objects.create(created_by=admin_user, question_type=QuestionType.MCQ)
        qv1 = QuestionVersion.objects.create(
            question=q1,
            version_number=1,
            title="Q1 MCQ",
            description="Select option A",
            question_type=QuestionType.MCQ,
            difficulty=Difficulty.EASY,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user,
            points=10,
            type_config={
                "options": [
                    {"id": "A", "text": "Option A"},
                    {"id": "B", "text": "Option B"}
                ],
                "correct_options": ["A"]
            }
        )
        AssessmentQuestion.objects.create(
            assessment=assessment,
            question_version=qv1,
            order=1,
            points=10,
            negative_marking_enabled=True,
            negative_points=2
        )

        # Q2: MCQ with negative marking (10 pts, -2 negative)
        q2 = Question.objects.create(created_by=admin_user, question_type=QuestionType.MCQ)
        qv2 = QuestionVersion.objects.create(
            question=q2,
            version_number=1,
            title="Q2 MCQ",
            description="Select option B",
            question_type=QuestionType.MCQ,
            difficulty=Difficulty.EASY,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user,
            points=10,
            type_config={
                "options": [
                    {"id": "A", "text": "Option A"},
                    {"id": "B", "text": "Option B"}
                ],
                "correct_options": ["B"]
            }
        )
        AssessmentQuestion.objects.create(
            assessment=assessment,
            question_version=qv2,
            order=2,
            points=10,
            negative_marking_enabled=True,
            negative_points=2
        )

        # Q3: Unanswered Question (10 pts)
        q3 = Question.objects.create(created_by=admin_user, question_type=QuestionType.MCQ)
        qv3 = QuestionVersion.objects.create(
            question=q3,
            version_number=1,
            title="Q3 MCQ",
            description="Select option A",
            question_type=QuestionType.MCQ,
            difficulty=Difficulty.EASY,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user,
            points=10,
            type_config={
                "options": [{"id": "A", "text": "Option A"}],
                "correct_options": ["A"]
            }
        )
        AssessmentQuestion.objects.create(
            assessment=assessment,
            question_version=qv3,
            order=3,
            points=10
        )

        # Q4: Multi-Select (10 pts)
        q4 = Question.objects.create(created_by=admin_user, question_type=QuestionType.MULTI_SELECT)
        qv4 = QuestionVersion.objects.create(
            question=q4,
            version_number=1,
            title="Q4 Multi-Select",
            description="Select A and B",
            question_type=QuestionType.MULTI_SELECT,
            difficulty=Difficulty.MEDIUM,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user,
            points=10,
            type_config={
                "options": [
                    {"id": "A", "text": "Option A"},
                    {"id": "B", "text": "Option B"},
                    {"id": "C", "text": "Option C"}
                ],
                "correct_options": ["A", "B"]
            }
        )
        AssessmentQuestion.objects.create(
            assessment=assessment,
            question_version=qv4,
            order=4,
            points=10
        )

        # Q5: Coding Question (10 pts)
        q5 = Question.objects.create(created_by=admin_user, question_type=QuestionType.CODING)
        qv5 = QuestionVersion.objects.create(
            question=q5,
            version_number=1,
            title="Q5 Coding",
            description="Write addition",
            question_type=QuestionType.CODING,
            difficulty=Difficulty.MEDIUM,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user,
            points=10
        )
        code_cfg = CodingQuestionConfig.objects.create(
            question_version=qv5,
            allowed_languages=["PYTHON"],
            time_limit_ms=2000,
            memory_limit_mb=128
        )
        TestCase.objects.create(
            coding_config=code_cfg,
            name="test 1",
            input_data="1 2",
            expected_output="3\n",
            is_hidden=False,
            points=10,
            execution_order=1
        )
        AssessmentQuestion.objects.create(
            assessment=assessment,
            question_version=qv5,
            order=5,
            points=10
        )

        # Publish assessment
        AssessmentSnapshotService.create_snapshot(assessment, actor=admin_user)
        assessment.status = AssessmentStatus.PUBLISHED
        assessment.published_at = now
        assessment.save()

        # Assign all 3 students
        asgn1 = AssessmentAssignment.objects.create(
            assessment=assessment, student=student_1, status=AssignmentStatus.ASSIGNED, assigned_by=admin_user
        )
        asgn2 = AssessmentAssignment.objects.create(
            assessment=assessment, student=student_2, status=AssignmentStatus.ASSIGNED, assigned_by=admin_user
        )
        asgn3 = AssessmentAssignment.objects.create(
            assessment=assessment, student=student_3, status=AssignmentStatus.ASSIGNED, assigned_by=admin_user
        )

        return {
            "admin": admin_user,
            "student_1": student_1,
            "student_2": student_2,
            "student_3": student_3,
            "assessment": assessment,
        }

    def test_authoritative_admin_result_roster_complete_candidate_view(self, setup_data):
        """
        R1: Admin assessment results roster lists ALL assigned candidates with authoritative status:
        NOT_STARTED, IN_PROGRESS, EVALUATED/RELEASED, DISQUALIFIED.
        """
        admin = setup_data["admin"]
        s1 = setup_data["student_1"]
        s2 = setup_data["student_2"]
        s3 = setup_data["student_3"]
        assessment = setup_data["assessment"]

        # Student 1: Not started -> remains NOT_STARTED
        # Student 2: In Progress
        att2, _ = AttemptService.start_attempt(student=s2, assessment_id=str(assessment.id))

        # Student 3: Submitted & Finalized
        att3, _ = AttemptService.start_attempt(student=s3, assessment_id=str(assessment.id))
        AttemptService.submit_attempt(student=s3, attempt_id=str(att3.id))
        res3 = ResultFinalizationService.finalize_attempt(attempt_id=str(att3.id))

        client = APIClient()
        client.force_authenticate(user=admin)
        url = f"/api/v1/admin/assessments/{assessment.id}/results/"
        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["results"]
        assert len(data) == 3

        statuses = {item["student"]["email"]: item["status"] for item in data}
        assert statuses[s1.email] == "NOT_STARTED"
        assert statuses[s2.email] == "IN_PROGRESS"
        assert statuses[s3.email] == "EVALUATED"

        # Check NOT_STARTED is_passed is None
        s1_item = next(item for item in data if item["student"]["email"] == s1.email)
        assert s1_item["is_passed"] is None

        # Test Status Filtering
        resp_ns = client.get(url, {"status": "NOT_STARTED"})
        assert resp_ns.status_code == status.HTTP_200_OK
        ns_data = resp_ns.json()["results"]
        assert len(ns_data) == 1
        assert ns_data[0]["student"]["email"] == s1.email

    def test_disqualified_status_derivation(self, setup_data):
        """
        R1: Disqualified status is properly derived when attempt is CANCELLED and proctoring is TERMINATED.
        """
        admin = setup_data["admin"]
        s2 = setup_data["student_2"]
        assessment = setup_data["assessment"]

        att2, _ = AttemptService.start_attempt(student=s2, assessment_id=str(assessment.id))
        proc_sess = ProctoringSession.objects.create(
            attempt=att2,
            status="TERMINATED",
            risk_band=RiskBand.CRITICAL,
            risk_score=Decimal('95.00')
        )
        att2.status = AttemptStatus.CANCELLED
        att2.save()

        client = APIClient()
        client.force_authenticate(user=admin)
        url = f"/api/v1/admin/assessments/{assessment.id}/results/"
        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["results"]
        s2_item = next(item for item in data if item["student"]["email"] == s2.email)
        assert s2_item["status"] == "DISQUALIFIED"

    def test_celery_broker_offline_inline_finalization_fallback(self, setup_data, monkeypatch):
        """
        R2: When Celery broker is unavailable, submission finalization executes inline fallback
        and guarantees an AssessmentResult is created.
        """
        s1 = setup_data["student_1"]
        assessment = setup_data["assessment"]

        att, _ = AttemptService.start_attempt(student=s1, assessment_id=str(assessment.id))

        monkeypatch.setattr("django.db.transaction.on_commit", lambda func: func())

        with patch("apps.results.tasks.finalize_assessment_result_task.delay") as mock_delay:
            mock_delay.side_effect = RuntimeError("Celery Broker Offline")

            # Submit attempt
            submitted_att = AttemptService.submit_attempt(student=s1, attempt_id=str(att.id))
            assert submitted_att.status == AttemptStatus.SUBMITTED

            # AssessmentResult must exist because inline fallback finalized it!
            result = AssessmentResult.objects.filter(attempt=submitted_att).first()
            assert result is not None
            assert result.status == ResultStatus.FINALIZED

    def test_blank_exam_submission_zero_score_finalization(self, setup_data):
        """
        R4: Blank exam submission (0 answers) transitions to SUBMITTED and creates
        AssessmentResult with score 0.00 and is_passed False without crashing.
        """
        s1 = setup_data["student_1"]
        assessment = setup_data["assessment"]

        att, _ = AttemptService.start_attempt(student=s1, assessment_id=str(assessment.id))
        submitted_att = AttemptService.submit_attempt(student=s1, attempt_id=str(att.id))

        result = ResultFinalizationService.finalize_attempt(attempt_id=str(submitted_att.id))

        assert result.status == ResultStatus.FINALIZED
        assert result.total_score_earned == Decimal('0.00')
        assert result.total_possible_score == Decimal('50.00')
        assert result.percentage == Decimal('0.00')
        assert result.is_passed is False
        assert result.answered_questions == 0
        assert result.skipped_questions == 5

    def test_normal_mixed_score_assessment_evaluation(self, setup_data):
        """
        R3: Mixed assessment scoring:
        - Q1: correct MCQ (+10)
        - Q2: incorrect MCQ with negative marking (-2)
        - Q3: unanswered MCQ (0, no penalty)
        - Q4: correct multi-select (+10)
        - Q5: skipped coding (0)
        Total earned: 10 - 2 + 0 + 10 + 0 = 18.00 / 50.00 (36.00%), is_passed = False (pass threshold 60%).
        """
        s1 = setup_data["student_1"]
        assessment = setup_data["assessment"]

        att, _ = AttemptService.start_attempt(student=s1, assessment_id=str(assessment.id))
        snapshot = att.assessment_snapshot
        snapshot_qs = list(snapshot.snapshot_questions.order_by('order'))

        # Q1: Correct (Selected A)
        AttemptService.save_answer(
            student=s1,
            attempt_id=str(att.id),
            snapshot_question_id=snapshot_qs[0].snapshot_question_id,
            answer_data={"selected_options": ["A"]},
            client_revision=1
        )

        # Q2: Incorrect (Selected A instead of B)
        AttemptService.save_answer(
            student=s1,
            attempt_id=str(att.id),
            snapshot_question_id=snapshot_qs[1].snapshot_question_id,
            answer_data={"selected_options": ["A"]},
            client_revision=1
        )

        # Q3: Unanswered (skipped)

        # Q4: Correct Multi-Select (Selected A and B)
        AttemptService.save_answer(
            student=s1,
            attempt_id=str(att.id),
            snapshot_question_id=snapshot_qs[3].snapshot_question_id,
            answer_data={"selected_options": ["A", "B"]},
            client_revision=1
        )

        # Submit attempt
        submitted_att = AttemptService.submit_attempt(student=s1, attempt_id=str(att.id))
        result = ResultFinalizationService.finalize_attempt(attempt_id=str(submitted_att.id))

        assert result.total_score_earned == Decimal('18.00')
        assert result.total_possible_score == Decimal('50.00')
        assert result.percentage == Decimal('36.00')
        assert result.is_passed is False
        assert result.answered_questions == 3
        assert result.correct_questions == 2
        assert result.incorrect_questions == 1
        assert result.skipped_questions == 2

    def test_result_release_policy_and_idor_protection(self, setup_data):
        """
        R5/R6: Manual release gating and student IDOR protection.
        """
        admin = setup_data["admin"]
        s1 = setup_data["student_1"]
        s2 = setup_data["student_2"]
        assessment = setup_data["assessment"]

        att, _ = AttemptService.start_attempt(student=s1, assessment_id=str(assessment.id))
        AttemptService.submit_attempt(student=s1, attempt_id=str(att.id))
        res = ResultFinalizationService.finalize_attempt(attempt_id=str(att.id))

        client = APIClient()

        # Student 1 attempts to view unreleased result -> 403 Forbidden
        client.force_authenticate(user=s1)
        resp_unreleased = client.get(f"/api/v1/student/attempts/{att.id}/result/")
        assert resp_unreleased.status_code == status.HTTP_403_FORBIDDEN
        assert "not been released" in resp_unreleased.json()["message"]

        # Student 2 attempts to view Student 1's result -> 403 Forbidden (IDOR)
        client.force_authenticate(user=s2)
        resp_idor = client.get(f"/api/v1/student/attempts/{att.id}/result/")
        assert resp_idor.status_code == status.HTTP_403_FORBIDDEN

        # Admin releases results
        client.force_authenticate(user=admin)
        rel_resp = client.post(f"/api/v1/admin/assessments/{assessment.id}/release-results/")
        assert rel_resp.status_code == status.HTTP_200_OK

        # Student 1 can now view released result
        client.force_authenticate(user=s1)
        resp_released = client.get(f"/api/v1/student/attempts/{att.id}/result/")
        assert resp_released.status_code == status.HTTP_200_OK
        assert resp_released.json()["data"]["total_score_earned"] is not None
