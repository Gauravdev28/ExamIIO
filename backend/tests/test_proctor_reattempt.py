"""
Comprehensive Backend Test Suite for Proctor Reattempt / Second-Chance Exam Feature.
ExamIIO / CODEGUARD

Tests cover:
- Authorization lifecycle, permissions, relationships, uniqueness
- State immutability & terminal protections (Attempt #1 never revived)
- Idempotency across IN_PROGRESS, SUBMITTED, EXPIRED, CANCELLED
- Strict one-reattempt limit (No Attempt #3, no chaining)
- Concurrency & serialization under row locks
- Canonical Max+1 attempt numbering
- Independence of eligibility logic
- Result & Certificate isolation
- 60-second server-authoritative delay window & schedule checks
- Foreign key deletion protections (on_delete=models.PROTECT)
- Concurrency test on MySQL/InnoDB
"""
import math
import uuid
import threading
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from django.db import IntegrityError, models, transaction, connection
from django.db.models import ProtectedError
from django.core.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role, AuditLog
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AssessmentService, AttemptService, AttemptTimerService
from apps.assessments.serializers import StudentAssessmentListSerializer
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorReattemptAuthorization,
    ReattemptReason,
    ReattemptAuthStatus,
)
from apps.invigilation.services import ProctorReattemptService
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus
from apps.questions.services import QuestionService
from apps.results.models import AssessmentResult, ResultStatus, Certificate, CertificateStatus
from apps.results.certificate_service import CertificateService


@pytest.mark.django_db(transaction=True)
class TestProctorReattemptSuite:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.admin = User.objects.create(email="admin_reatt@example.com", role=Role.ADMIN)
        self.proctor = User.objects.create(email="proctor_reatt@example.com", role=Role.PROCTOR)
        self.other_proctor = User.objects.create(email="other_proctor@example.com", role=Role.PROCTOR)
        self.student = User.objects.create(email="student_reatt@example.com", role=Role.STUDENT)
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="ROLL-REATT-001",
            euid="EUID-REATT-001",
            first_login_required=False,
        )
        self.student_2 = User.objects.create(email="student2_reatt@example.com", role=Role.STUDENT)
        self.profile_2 = StudentProfile.objects.create(
            user=self.student_2,
            roll_number="ROLL-REATT-002",
            euid="EUID-REATT-002",
            first_login_required=False,
        )

        now = timezone.now()
        # Create published assessment with 1 attempt limit
        self.assessment = Assessment.objects.create(
            title="Reattempt Verification Exam",
            description="Testing Proctor Reattempt Invariants",
            instructions="Exam instructions",
            duration_minutes=60,
            passing_percentage=50,
            attempt_limit=1,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=5),
            created_by=self.admin,
        )

        # Assign proctor
        self.proctor_assignment = ProctorAssignment.objects.create(
            proctor=self.proctor,
            assessment=self.assessment,
            is_active=True,
        )

        # Assign student
        self.assignment = AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )
        self.assignment_2 = AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student_2,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )

        # Create question and version
        self.q = Question.objects.create(question_type=QuestionType.MCQ, created_by=self.admin)
        self.qv = QuestionVersion.objects.create(
            question=self.q,
            version_number=1,
            title="Q1 Version",
            question_type=QuestionType.MCQ,
            points=10,
            status=VersionStatus.PUBLISHED,
            created_by=self.admin,
            type_config={
                "options": [
                    {"id": "opt-1", "text": "A", "is_correct": True},
                    {"id": "opt-2", "text": "B", "is_correct": False},
                ]
            },
        )

        # Create Snapshot
        self.snapshot = AssessmentSnapshot.objects.create(
            assessment=self.assessment,
            version_number=1,
            snapshot_data={"questions": [{"snapshot_question_id": "sq-1", "question_type": "MCQ"}]},
        )
        self.sq = AssessmentSnapshotQuestion.objects.create(
            snapshot=self.snapshot,
            question_version=self.qv,
            snapshot_question_id="sq-1",
            order=1,
            points=10,
            question_type=QuestionType.MCQ,
        )

        # Helper method to create attempt 1
        self.attempt_1, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))

    def _cancel_attempt(self, attempt, reason="Test Cancellation"):
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.disqualification_reason = reason
        attempt.disqualified_at = timezone.now()
        attempt.save()
        return attempt

    # =========================================================================
    # 1. AUTHORIZATION
    # =========================================================================

    def test_authorization_starts_authorized(self):
        """Verify initial state is AUTHORIZED, new_attempt is None, available_at is 60s in future."""
        self._cancel_attempt(self.attempt_1)
        now = timezone.now()

        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
            note="Accidental OS blur",
        )

        assert auth.status == ReattemptAuthStatus.AUTHORIZED
        assert auth.new_attempt is None
        assert auth.student == self.student
        assert auth.assessment == self.assessment
        assert auth.original_attempt == self.attempt_1
        assert auth.authorized_by == self.proctor
        assert auth.available_at >= now + timedelta(seconds=59)
        assert auth.available_at <= now + timedelta(seconds=61)

    def test_authorization_requires_cancelled_attempt(self):
        """Active or submitted attempts cannot be authorized for reattempt."""
        # Attempt 1 is currently IN_PROGRESS
        with pytest.raises(DRFValidationError) as exc:
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(self.attempt_1.id),
                reason=ReattemptReason.ACCIDENTAL_VIOLATION,
            )
        assert "CANCELLED" in str(exc.value)

        # SUBMITTED attempt
        self.attempt_1.status = AttemptStatus.SUBMITTED
        self.attempt_1.save()
        with pytest.raises(DRFValidationError) as exc:
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(self.attempt_1.id),
                reason=ReattemptReason.ACCIDENTAL_VIOLATION,
            )
        assert "CANCELLED" in str(exc.value)

    def test_authorization_requires_proctor_permission(self):
        """Endpoint rejects non-proctor / non-assigned users."""
        self._cancel_attempt(self.attempt_1)

        # Student attempting to authorize
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {"reason": ReattemptReason.ACCIDENTAL_VIOLATION})
        assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

        # Unassigned proctor
        self.client.force_authenticate(user=self.other_proctor)
        resp = self.client.post(url, {"reason": ReattemptReason.ACCIDENTAL_VIOLATION})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Assigned proctor succeeds
        self.client.force_authenticate(user=self.proctor)
        resp = self.client.post(url, {"reason": ReattemptReason.ACCIDENTAL_VIOLATION})
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["status"] == "AUTHORIZED"

    def test_authorization_requires_valid_attempt_assignment_relationship(self):
        """Target attempt must match an active candidate assessment assignment."""
        self._cancel_attempt(self.attempt_1)
        self.assignment.status = AssignmentStatus.REVOKED
        self.assignment.save()

        with pytest.raises(DRFValidationError) as exc:
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(self.attempt_1.id),
                reason=ReattemptReason.ACCIDENTAL_VIOLATION,
            )
        assert "assignment" in str(exc.value).lower()

    def test_duplicate_authorization_rejected(self):
        """Multiple authorizations for same student + assessment are strictly rejected."""
        self._cancel_attempt(self.attempt_1)

        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        assert auth is not None

        # Second attempt to authorize must fail
        with pytest.raises(DRFValidationError) as exc:
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(self.attempt_1.id),
                reason=ReattemptReason.TECHNICAL_PROBLEM,
            )
        assert "already" in str(exc.value).lower()

    # =========================================================================
    # 2. STATE TRANSITIONS & TERMINAL PROTECTIONS
    # =========================================================================

    def test_cancelled_original_attempt_never_reopened(self):
        """Attempt #1 remains CANCELLED across the entire lifecycle."""
        self._cancel_attempt(self.attempt_1)
        assert self.attempt_1.status == AttemptStatus.CANCELLED

        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )

        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.CANCELLED

        # Advance past 60s delay and start Attempt #2
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True
        assert attempt_2.id != self.attempt_1.id

        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.CANCELLED
        assert self.attempt_1.attempt_number == 1

    def test_authorized_to_consumed_transition(self):
        """Authorization moves from AUTHORIZED to CONSUMED with linked attempt."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        assert auth.status == ReattemptAuthStatus.AUTHORIZED

        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True

        auth.refresh_from_db()
        assert auth.status == ReattemptAuthStatus.CONSUMED
        assert auth.new_attempt == attempt_2
        assert auth.used_at is not None

    def test_consumed_never_returns_to_authorized(self):
        """A consumed authorization cannot transition back to AUTHORIZED."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        auth.refresh_from_db()
        assert auth.status == ReattemptAuthStatus.CONSUMED

        # Calling start again must not set it back
        att, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is False
        assert att.id == attempt_2.id
        auth.refresh_from_db()
        assert auth.status == ReattemptAuthStatus.CONSUMED

    # =========================================================================
    # 3. IDEMPOTENCY
    # =========================================================================

    def test_consumed_in_progress_returns_existing_attempt(self):
        """Starting an in-progress Attempt #2 returns the same attempt idempotently."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True

        # Second call
        att_resumed, is_new_2 = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new_2 is False
        assert att_resumed.id == att_2.id

    def test_consumed_submitted_returns_existing_attempt(self):
        """Starting a submitted Attempt #2 returns existing attempt without creating Attempt #3."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        att_2.status = AttemptStatus.SUBMITTED
        att_2.save()

        resumed, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is False
        assert resumed.id == att_2.id
        assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2

    def test_consumed_expired_returns_existing_attempt(self):
        """Starting an expired Attempt #2 returns existing attempt."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        att_2.status = AttemptStatus.EXPIRED
        att_2.save()

        resumed, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is False
        assert resumed.id == att_2.id
        assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2

    def test_consumed_cancelled_returns_terminal_error(self):
        """If Attempt #2 is CANCELLED, calling start returns deterministic CANDIDATE_DISQUALIFIED."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        self._cancel_attempt(att_2, reason="Attempt 2 cancelled")

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert "CANDIDATE_DISQUALIFIED" in str(exc.value)
        assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2

    def test_consumed_attempt_never_creates_attempt_3(self):
        """Repeated start calls on a consumed authorization never produce Attempt #3."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))

        for _ in range(5):
            res, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
            assert is_new is False
            assert res.id == att_2.id

        assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2

    def test_consumed_attempt_resolution_after_assessment_deadline(self):
        """Existing consumed attempt is resolved even after the assessment end_datetime has passed."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))

        # Set assessment end_datetime into the past
        self.assessment.end_datetime = timezone.now() - timedelta(minutes=10)
        self.assessment.save()

        res, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is False
        assert res.id == att_2.id

    # =========================================================================
    # 4. ONE REATTEMPT
    # =========================================================================

    def test_only_one_total_reattempt_per_student_assessment(self):
        """Only one reattempt authorization is permitted per (student, assessment)."""
        self._cancel_attempt(self.attempt_1)
        ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        assert ProctorReattemptAuthorization.objects.filter(assessment=self.assessment, student=self.student).count() == 1

        with pytest.raises(DRFValidationError):
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(self.attempt_1.id),
                reason=ReattemptReason.TECHNICAL_PROBLEM,
            )

    def test_cancelled_reattempt_cannot_spawn_second_reattempt(self):
        """Attempt #2 cancelled cannot be authorized for Attempt #3."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        self._cancel_attempt(att_2, reason="Attempt 2 cancelled")

        with pytest.raises(DRFValidationError) as exc:
            ProctorReattemptService.authorize_reattempt(
                proctor=self.proctor,
                attempt_id=str(att_2.id),
                reason=ReattemptReason.PROCTOR_DECISION,
            )
        assert "already" in str(exc.value).lower() or "reattempt" in str(exc.value).lower()

    # =========================================================================
    # 5. ATTEMPT NUMBERING
    # =========================================================================

    def test_attempt_number_uses_max_plus_one(self):
        """Attempt numbers strictly follow Max + 1."""
        assert self.attempt_1.attempt_number == 1

        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert att_2.attempt_number == 2

    def test_attempt_number_never_collides(self):
        """Database UniqueConstraint prevents duplicate attempt numbers."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TestAttempt.objects.create(
                    student=self.student,
                    assessment=self.assessment,
                    assessment_snapshot=self.snapshot,
                    attempt_number=1,
                    status=AttemptStatus.IN_PROGRESS,
                    randomization_seed="seed-dup",
                )

    # =========================================================================
    # 6. ELIGIBILITY
    # =========================================================================

    def test_reattempt_allowed_when_normal_attempt_limit_exhausted(self):
        """Reattempt is granted and start succeeds even when normal attempt_limit is reached."""
        assert self.assessment.attempt_limit == 1
        self._cancel_attempt(self.attempt_1)

        # Without auth, start fails
        with pytest.raises(DRFValidationError):
            AttemptService.start_attempt(self.student, str(self.assessment.id))

        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True
        assert att_2.attempt_number == 2

    def test_normal_attempt_limit_enforced_without_authorization(self):
        """Normal candidates without reattempt authorization are strictly bound to attempt_limit."""
        self.attempt_1.status = AttemptStatus.SUBMITTED
        self.attempt_1.save()

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert "attempt limit reached" in str(exc.value).lower()

    def test_is_eligible_logic_is_unchanged(self):
        """StudentAssessmentListSerializer.is_eligible remains attempts_used < attempt_limit."""
        class MockRequest:
            user = self.student

        serializer = StudentAssessmentListSerializer(self.assessment, context={"request": MockRequest()})
        data = serializer.data
        assert data["attempts_used"] == 1
        assert data["attempt_limit"] == 1
        assert data["is_eligible"] is False
        assert data["reattempt_authorized"] is False

        # Authorize reattempt
        self._cancel_attempt(self.attempt_1)
        ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )

        serializer_after = StudentAssessmentListSerializer(self.assessment, context={"request": MockRequest()})
        data_after = serializer_after.data
        # is_eligible MUST remain False
        assert data_after["is_eligible"] is False
        # reattempt fields expose second chance
        assert data_after["reattempt_authorized"] is True

    # =========================================================================
    # 7. ASSIGNMENT & SERIALIZATION ANCHOR
    # =========================================================================

    def test_assignment_parent_row_is_locked_before_attempt_creation(self):
        """AssessmentAssignment is locked with select_for_update."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        with patch("apps.assessments.models.AssessmentAssignment.objects.select_for_update", wraps=AssessmentAssignment.objects.select_for_update) as mock_lock:
            att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
            assert is_new is True
            assert mock_lock.called

    def test_revoked_assignment_rejected(self):
        """Revoked assignment blocks start with PermissionDenied."""
        self.assignment.status = AssignmentStatus.REVOKED
        self.assignment.save()

        with pytest.raises(PermissionDenied):
            AttemptService.start_attempt(self.student, str(self.assessment.id))

    # =========================================================================
    # 8. RESULTS ISOLATION
    # =========================================================================

    def test_reattempt_result_is_independent_from_original_result(self):
        """Attempt #2 creates an independent AssessmentResult."""
        self._cancel_attempt(self.attempt_1)
        res_1 = AssessmentResult.objects.create(
            attempt=self.attempt_1,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student,
            total_score_earned=Decimal("0.00"),
            total_possible_score=Decimal("50.00"),
            percentage=Decimal("0.00"),
            is_passed=False,
            status=ResultStatus.FINALIZED,
        )

        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        res_2 = AssessmentResult.objects.create(
            attempt=attempt_2,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student,
            total_score_earned=Decimal("50.00"),
            total_possible_score=Decimal("50.00"),
            percentage=Decimal("100.00"),
            is_passed=True,
            status=ResultStatus.FINALIZED,
        )

        assert res_1.id != res_2.id
        assert res_1.percentage == Decimal("0.00")
        assert res_2.percentage == Decimal("100.00")
        assert AssessmentResult.objects.filter(student=self.student, assessment=self.assessment).count() == 2

    def test_cancelled_original_result_cannot_be_overwritten_by_reattempt(self):
        """Finalized result from cancelled attempt cannot be overwritten."""
        self._cancel_attempt(self.attempt_1)
        res_1 = AssessmentResult.objects.create(
            attempt=self.attempt_1,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student,
            total_score_earned=Decimal("0.00"),
            total_possible_score=Decimal("50.00"),
            percentage=Decimal("0.00"),
            is_passed=False,
            status=ResultStatus.FINALIZED,
        )

        with pytest.raises(PermissionDenied):
            res_1.total_score_earned = Decimal("50.00")
            res_1.save()

    def test_original_result_remains_unchanged_after_attempt_2_submission(self):
        """Submitting Attempt #2 does not modify Attempt #1 answers, result, or status."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        # Answer on Attempt 2
        ans = attempt_2.answers.first()
        ans.selected_options = ["opt-1"]
        ans.is_answered = True
        ans.save()

        sub = AttemptService.submit_attempt(self.student, str(attempt_2.id))
        assert sub.status == AttemptStatus.SUBMITTED

        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.CANCELLED
        assert self.attempt_1.is_disqualified is True
        assert self.attempt_1.submitted_at is None

    # =========================================================================
    # 9. CERTIFICATES
    # =========================================================================

    def test_cancelled_attempt_never_qualifies_for_certificate(self):
        """Cancelled attempt never receives a certificate."""
        self._cancel_attempt(self.attempt_1)
        cert = CertificateService.generate_or_get_certificate(attempt=self.attempt_1)
        assert cert is None
        assert Certificate.objects.filter(exam=self.assessment, student=self.student).count() == 0

    def test_valid_reattempt_certificate_behavior_matches_existing_semantics(self):
        """Passed Attempt #2 successfully generates a certificate."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        attempt_2.status = AttemptStatus.SUBMITTED
        attempt_2.submitted_at = timezone.now()
        attempt_2.is_disqualified = False
        attempt_2.save()

        res_2 = AssessmentResult.objects.create(
            attempt=attempt_2,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            student=self.student,
            total_score_earned=Decimal("50.00"),
            total_possible_score=Decimal("50.00"),
            percentage=Decimal("100.00"),
            is_passed=True,
            status=ResultStatus.FINALIZED,
        )

        cert = CertificateService.generate_or_get_certificate(attempt=attempt_2)
        assert cert is not None
        assert cert.attempt_id == attempt_2.id

    # =========================================================================
    # 10. TIMER & 60-SECOND PREPARATION WINDOW
    # =========================================================================

    def test_start_before_60_seconds_rejected(self):
        """Attempting start before available_at raises REATTEMPT_PREPARING."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert exc.value.detail.get("error") == "REATTEMPT_PREPARING"
        assert int(exc.value.detail.get("remaining_seconds", 0)) > 0

    def test_start_at_60_seconds_accepted(self):
        """Starting exactly at available_at succeeds."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now()
        auth.save()

        att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True
        assert att_2.attempt_number == 2

    def test_start_after_60_seconds_accepted(self):
        """Starting after 60 seconds (e.g. 5 minutes later) succeeds."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(minutes=5)
        auth.save()

        att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True
        assert att_2.attempt_number == 2

    def test_authorization_remains_valid_before_assessment_deadline(self):
        """Authorization remains valid until the assessment end_datetime."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(hours=1)
        auth.save()

        # Assessment end_datetime is in the future
        assert timezone.now() < self.assessment.end_datetime

        att_2, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert is_new is True

    def test_authorized_start_after_assessment_deadline_rejected(self):
        """Starting an authorized attempt after assessment deadline is rejected."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(hours=1)
        auth.save()

        self.assessment.end_datetime = timezone.now() - timedelta(minutes=1)
        self.assessment.save()

        with pytest.raises(DRFValidationError) as exc:
            AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert "START_REJECTED_TOO_LATE" in str(exc.value)

    # =========================================================================
    # 11. REFERENTIAL INTEGRITY & ON_DELETE=PROTECT
    # =========================================================================

    def test_original_attempt_deletion_protected(self):
        """Deleting original_attempt raises ProtectedError."""
        self._cancel_attempt(self.attempt_1)
        ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )

        with pytest.raises(ProtectedError):
            self.attempt_1.delete()

    def test_reattempt_attempt_deletion_protected(self):
        """Deleting new_attempt raises ProtectedError."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))

        with pytest.raises(ProtectedError):
            attempt_2.delete()

    # =========================================================================
    # 12. CONCURRENCY TESTS (THREADING & ROW-LOCK SERIALIZATION)
    # =========================================================================

    def test_concurrent_authorization_cannot_bypass_reattempt_limit(self):
        """Simultaneous proctor authorization requests produce exactly 1 authorization."""
        self._cancel_attempt(self.attempt_1)

        results = []
        errors = []

        def worker():
            try:
                auth = ProctorReattemptService.authorize_reattempt(
                    proctor=self.proctor,
                    attempt_id=str(self.attempt_1.id),
                    reason=ReattemptReason.ACCIDENTAL_VIOLATION,
                )
                results.append(auth)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 1
        assert len(errors) == 1
        assert ProctorReattemptAuthorization.objects.filter(
            assessment=self.assessment, student=self.student
        ).count() == 1

    def test_concurrent_start_creates_single_attempt(self):
        """Simultaneous start calls on an authorized reattempt produce exactly 1 Attempt #2."""
        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempts_created = []
        attempts_returned = []
        errors = []

        def worker():
            connection.close()
            try:
                att, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
                if is_new:
                    attempts_created.append(att)
                else:
                    attempts_returned.append(att)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        if connection.vendor == 'sqlite':
            # SQLite does not support row-level locking, so simultaneous writes may raise table lock error,
            # but at most 1 Attempt #2 is ever created and no Attempt #3 exists.
            assert len(attempts_created) == 1
            assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2
        else:
            assert len(errors) == 0
            assert len(attempts_created) == 1
            assert len(attempts_returned) == 1
            assert attempts_created[0].id == attempts_returned[0].id
            assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2

        auth.refresh_from_db()
        assert auth.status == ReattemptAuthStatus.CONSUMED
        assert auth.new_attempt_id == attempts_created[0].id

    def test_mysql_two_simultaneous_starts_produce_single_attempt(self):
        """
        Verify that AssessmentAssignment row-lock serialization guarantees
        exactly 1 Attempt #2 and exactly 1 CONSUMED status under concurrency.
        """
        if connection.vendor == 'sqlite':
            pytest.skip("Production row-level concurrency test requires MySQL/InnoDB")

        self._cancel_attempt(self.attempt_1)
        auth = ProctorReattemptService.authorize_reattempt(
            proctor=self.proctor,
            attempt_id=str(self.attempt_1.id),
            reason=ReattemptReason.ACCIDENTAL_VIOLATION,
        )
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        barrier = threading.Barrier(2)
        results = []

        def worker():
            connection.close()
            try:
                barrier.wait()
                att, is_new = AttemptService.start_attempt(self.student, str(self.assessment.id))
                results.append((att.id, is_new))
            except Exception as e:
                results.append((None, str(e)))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both returned the same attempt ID
        att_ids = [r[0] for r in results if r[0] is not None]
        assert len(att_ids) == 2
        assert att_ids[0] == att_ids[1]

        # Exactly one was is_new=True, the other is_new=False
        is_news = [r[1] for r in results]
        assert True in is_news
        assert False in is_news

        assert TestAttempt.objects.filter(assessment=self.assessment, student=self.student).count() == 2
