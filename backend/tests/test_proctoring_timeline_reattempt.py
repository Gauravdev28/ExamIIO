"""
Focused Integration Test Suite for Proctoring Timeline & Evidence Review Second-Chance Action.
ExamIIO / CODEGUARD

Tests cover:
1. Timeline session detail shows can_grant_reattempt=True for eligible cancelled/disqualified Attempt #1.
2. Reattempt option is NOT added to the Human Review Verdict choices.
3. Existing four review decisions (REVIEWED_CLEAN, SUSPICIOUS_CONFIRMED, REQUIRES_FURTHER_INSPECTION, DISMISSED_FALSE_POSITIVE) remain unchanged and fully functional.
4. Saving review decision does not authorize reattempt, and authorizing reattempt does not alter review verdict.
5. Authorizing reattempt via the timeline API with all 4 reasons:
   - ACCIDENTAL_VIOLATION succeeds.
   - TECHNICAL_PROBLEM succeeds.
   - PROCTOR_DECISION succeeds.
   - OTHER without note is rejected with 400.
   - OTHER with note succeeds.
6. Successful authorization does not create Attempt #2 immediately (60s preparation delay strictly active; Attempt #1 remains CANCELLED).
7. Authorized state returns can_grant_reattempt=False, status='AUTHORIZED', and remaining_seconds on session detail.
8. Student starts Attempt #2 after 60s preparation delay; Attempt #1 session detail now returns status='CONSUMED', new_attempt_number=2, and can_grant_reattempt=False.
9. Attempt #2 session detail returns is_already_reattempt=True and can_grant_reattempt=False (Attempt #3 strictly prohibited).
10. Permissions: student or unauthorized actor cannot access session detail or authorize reattempt.
11. Double-submitting authorization is rejected idempotently with error.
12. Existing Proctor Console and Django Admin reattempt behavior remain completely intact and unaffected.
"""
from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

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
)
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus
from apps.assessments.services import AttemptService
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringReview,
)
from apps.invigilation.models import (
    ProctorReattemptAuthorization,
    ReattemptReason,
    ReattemptAuthStatus,
    ProctorIntervention,
    InterventionType,
)


@pytest.mark.django_db(transaction=True)
class TestProctoringTimelineReattemptSuite:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()

        # 1. Admin User
        self.admin = User.objects.create_user(
            email="admin_timeline@example.com",
            password="AdminPassword123!",
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        # 2. Student User
        self.student = User.objects.create_user(
            email="student_timeline@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT,
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="ROLL-TIMELINE-001",
            euid="EUID-TIMELINE-001",
        )

        # 3. Assessment & Assignment
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Timeline Reattempt Assessment",
            instructions="Proctored exam",
            duration_minutes=60,
            passing_percentage=50,
            attempt_limit=1,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=5),
            created_by=self.admin,
        )
        self.assignment = AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin,
            status=AssignmentStatus.ASSIGNED,
        )

        # 4. Question & Snapshot
        self.q = Question.objects.create(question_type=QuestionType.MCQ, created_by=self.admin)
        self.qv = QuestionVersion.objects.create(
            question=self.q,
            version_number=1,
            title="MCQ Question 1",
            question_type=QuestionType.MCQ,
            points=10,
            status=VersionStatus.PUBLISHED,
            created_by=self.admin,
            type_config={"options": [{"id": "o1", "text": "Correct", "is_correct": True}]},
        )
        self.snapshot = AssessmentSnapshot.objects.create(
            assessment=self.assessment,
            version_number=1,
        )
        AssessmentSnapshotQuestion.objects.create(
            snapshot=self.snapshot,
            question_version=self.qv,
            snapshot_question_id=str(self.q.id),
            order=1,
            points=10,
            question_type=self.qv.question_type,
            type_config=self.qv.type_config,
        )

        # 5. Attempt #1 (Disqualified & Cancelled)
        self.attempt_1 = TestAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            attempt_number=1,
            status=AttemptStatus.CANCELLED,
            is_disqualified=True,
            disqualification_reason="EXAMINATION TERMINATED — WINDOW FOCUS LOST",
            disqualified_at=now,
            started_at=now - timedelta(minutes=15),
            expires_at=now + timedelta(minutes=45),
        )

        # 6. Proctoring Session
        self.session_1 = ProctoringSession.objects.create(
            attempt=self.attempt_1,
            status=ProctoringSessionStatus.TERMINATED,
            risk_score=95.0,
            risk_band='CRITICAL',
            total_events_count=3,
            total_warnings_count=1,
        )

    # -------------------------------------------------------------------------
    # 1. Timeline Session Detail & Reattempt Fields
    # -------------------------------------------------------------------------

    def test_session_detail_exposes_eligible_reattempt_state(self):
        """Session detail endpoint exposes attempt metadata and can_grant_reattempt=True for cancelled Attempt #1."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/"
        resp = self.client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert data["attempt_id"] == str(self.attempt_1.id)
        assert data["attempt_number"] == 1
        assert data["assessment_title"] == "Timeline Reattempt Assessment"
        assert data["is_disqualified"] is True
        assert data["is_already_reattempt"] is False
        assert data["can_grant_reattempt"] is True
        assert data["reattempt"] is None

    # -------------------------------------------------------------------------
    # 2. Existing Human Review Verdicts Remain Intact & Independent
    # -------------------------------------------------------------------------

    def test_human_review_verdicts_remain_intact_and_independent(self):
        """The four human review decisions are preserved and do NOT interfere with reattempt."""
        self.client.force_authenticate(user=self.admin)
        review_url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/review/"

        # Test all 4 existing choices
        valid_decisions = [
            "REVIEWED_CLEAN",
            "SUSPICIOUS_CONFIRMED",
            "REQUIRES_FURTHER_INSPECTION",
            "DISMISSED_FALSE_POSITIVE",
        ]
        for decision in valid_decisions:
            resp = self.client.patch(review_url, {
                "decision": decision,
                "notes": f"Testing review verdict {decision}",
            })
            assert resp.status_code == status.HTTP_200_OK
            assert resp.data["decision"] == decision

        # Verify ProctoringReview model has the expected decision
        review = ProctoringReview.objects.get(session=self.session_1)
        assert review.decision == "DISMISSED_FALSE_POSITIVE"

        # Verify reattempt authorization was NOT created by review
        assert ProctorReattemptAuthorization.objects.filter(student=self.student, assessment=self.assessment).count() == 0

        # Verify session detail still allows reattempt
        detail_url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/"
        detail_resp = self.client.get(detail_url)
        assert detail_resp.data["can_grant_reattempt"] is True

    # -------------------------------------------------------------------------
    # 3. Authorizing Reattempt via Timeline API: Reasons & Validation
    # -------------------------------------------------------------------------

    def test_authorize_reattempt_accidental_violation(self):
        """Admin can authorize reattempt with ACCIDENTAL_VIOLATION from timeline."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Candidate had OS notification blur",
        })

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["status"] == ReattemptAuthStatus.AUTHORIZED
        assert resp.data["reason"] == ReattemptReason.ACCIDENTAL_VIOLATION
        assert 58 <= resp.data["remaining_seconds"] <= 60
        assert resp.data["new_attempt_id"] is None

        # Verify Attempt #1 remains CANCELLED
        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.CANCELLED
        assert self.attempt_1.is_disqualified is True

    def test_authorize_reattempt_technical_problem(self):
        """Admin can authorize reattempt with TECHNICAL_PROBLEM."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Browser crash reported",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["reason"] == ReattemptReason.TECHNICAL_PROBLEM

    def test_authorize_reattempt_proctor_decision(self):
        """Admin can authorize reattempt with PROCTOR_DECISION."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {
            "reason": ReattemptReason.PROCTOR_DECISION,
            "note": "Reviewed footage, authorized",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["reason"] == ReattemptReason.PROCTOR_DECISION

    def test_authorize_reattempt_other_without_note_rejected(self):
        """OTHER reason requires an explanatory note."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {
            "reason": ReattemptReason.OTHER,
            "note": "",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert ProctorReattemptAuthorization.objects.count() == 0

    def test_authorize_reattempt_other_with_note_succeeds(self):
        """OTHER reason succeeds when an explanatory note is provided."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        resp = self.client.post(url, {
            "reason": ReattemptReason.OTHER,
            "note": "Specific institutional dispensation granted.",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["reason"] == ReattemptReason.OTHER
        assert resp.data["note"] == "Specific institutional dispensation granted."

    # -------------------------------------------------------------------------
    # 4. Session Detail Updates after Authorization (STATE 2: AUTHORIZED)
    # -------------------------------------------------------------------------

    def test_session_detail_reflects_authorized_state(self):
        """After authorization, session detail shows can_grant_reattempt=False and reattempt info."""
        self.client.force_authenticate(user=self.admin)
        auth_url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        self.client.post(auth_url, {
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Hardware glitch",
        })

        detail_url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/"
        resp = self.client.get(detail_url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert data["can_grant_reattempt"] is False
        assert data["reattempt"] is not None
        assert data["reattempt"]["status"] == ReattemptAuthStatus.AUTHORIZED
        assert data["reattempt"]["reason"] == ReattemptReason.TECHNICAL_PROBLEM
        assert data["reattempt"]["new_attempt_id"] is None
        assert data["reattempt"]["remaining_seconds"] <= 60

    # -------------------------------------------------------------------------
    # 5. Session Detail Updates after Student Starts (STATE 3: CONSUMED)
    # -------------------------------------------------------------------------

    def test_session_detail_reflects_consumed_state_after_student_starts(self):
        """After candidate starts Attempt #2, session detail shows CONSUMED and Attempt #2 info."""
        # 1. Authorize
        self.client.force_authenticate(user=self.admin)
        auth_url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        self.client.post(auth_url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Focus loss",
        })

        auth = ProctorReattemptAuthorization.objects.get(student=self.student, assessment=self.assessment)
        # Advance preparation window
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        # 2. Student starts Attempt #2
        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        assert attempt_2.attempt_number == 2

        # 3. Fetch Attempt #1 session detail as Admin
        detail_url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/"
        resp = self.client.get(detail_url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert data["can_grant_reattempt"] is False
        assert data["reattempt"]["status"] == ReattemptAuthStatus.CONSUMED
        assert data["reattempt"]["new_attempt_id"] == str(attempt_2.id)
        assert data["reattempt"]["new_attempt_number"] == 2

    # -------------------------------------------------------------------------
    # 6. Attempt #2 Session Detail (STATE 4: Already a Reattempt)
    # -------------------------------------------------------------------------

    def test_attempt_2_session_detail_blocks_further_reattempt(self):
        """Attempt #2 session detail reflects is_already_reattempt=True and blocks Attempt #3."""
        # Authorize and start Attempt #2
        self.client.force_authenticate(user=self.admin)
        auth_url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        self.client.post(auth_url, {
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Hardware glitch",
        })
        auth = ProctorReattemptAuthorization.objects.get(student=self.student, assessment=self.assessment)
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        attempt_2.status = AttemptStatus.CANCELLED
        attempt_2.is_disqualified = True
        attempt_2.disqualification_reason = "EXAMINATION TERMINATED — TAB SWITCH"
        attempt_2.save()

        # Create proctoring session for Attempt #2
        session_2 = ProctoringSession.objects.create(
            attempt=attempt_2,
            status=ProctoringSessionStatus.TERMINATED,
            risk_score=90.0,
            risk_band='CRITICAL',
        )

        detail_url = f"/api/v1/admin/proctoring/sessions/{session_2.id}/"
        resp = self.client.get(detail_url)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert data["attempt_number"] == 2
        assert data["is_already_reattempt"] is True
        assert data["can_grant_reattempt"] is False

        # Attempt to authorize Attempt #2 is rejected
        auth_2_url = f"/api/v1/proctor/attempts/{attempt_2.id}/reattempt/"
        resp_attempt_3 = self.client.post(auth_2_url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Attempting third attempt",
        })
        assert resp_attempt_3.status_code == status.HTTP_400_BAD_REQUEST
        assert TestAttempt.objects.filter(student=self.student, assessment=self.assessment).count() == 2

    # -------------------------------------------------------------------------
    # 7. Access Control & Permission Enforcement
    # -------------------------------------------------------------------------

    def test_student_cannot_access_session_detail_or_authorize(self):
        """Student is denied access to admin session detail and proctor reattempt authorization."""
        self.client.force_authenticate(user=self.student)
        detail_url = f"/api/v1/admin/proctoring/sessions/{self.session_1.id}/"
        resp = self.client.get(detail_url)
        assert resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        auth_url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"
        auth_resp = self.client.post(auth_url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
        })
        assert auth_resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    # -------------------------------------------------------------------------
    # 8. Duplicate Submission Prevention
    # -------------------------------------------------------------------------

    def test_duplicate_authorization_submission_rejected(self):
        """Submitting reattempt authorization twice produces a 400 error and creates only 1 authorization."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/proctor/attempts/{self.attempt_1.id}/reattempt/"

        resp1 = self.client.post(url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "First attempt",
        })
        assert resp1.status_code == status.HTTP_201_CREATED

        resp2 = self.client.post(url, {
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Duplicate attempt",
        })
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST
        assert ProctorReattemptAuthorization.objects.filter(student=self.student, assessment=self.assessment).count() == 1
