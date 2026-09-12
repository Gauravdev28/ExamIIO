"""
Focused Test Suite for Django Admin 'Give Student Another Chance' Action.
ExamIIO / CODEGUARD

Tests cover:
1. Admin can see/use the action for an eligible cancelled attempt (GET returns 200 with form).
2. Non-admin / student cannot access the admin action (raises 403 / redirects).
3. Admin confirmation with ACCIDENTAL_VIOLATION successfully calls ProctorReattemptService.
4. Confirmation with TECHNICAL_PROBLEM succeeds.
5. Confirmation with PROCTOR_DECISION succeeds.
6. Confirmation with OTHER without a note is rejected with clean error message.
7. Confirmation with OTHER with note succeeds.
8. Already-authorized attempt cannot be authorized again.
9. Attempt #2 cannot receive another reattempt (chaining prohibited).
10. Admin action does NOT reopen Attempt #1 (Attempt #1 remains CANCELLED).
11. Admin action creates no Attempt #2 immediately (only creates authorization; 60s delay holds).
12. Existing audit trail is created (AuditLog + ProctorIntervention).
13. Admin-triggered authorization records request.user as authorized_by.
14. Changelist action redirects single selected attempt to confirmation view.
15. Changelist action with multiple selections produces warning and does not authorize.
"""
import sys
import copy
from datetime import timedelta
import pytest
from django.urls import reverse
from django.utils import timezone
from django.test import Client
from django.template import context as django_context

# Python 3.14 compatibility patch for Django 5.1 test client template context copying
if sys.version_info >= (3, 14):
    def _py314_basecontext_copy(self):
        duplicate = object.__new__(self.__class__)
        duplicate.__dict__.update(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate
    django_context.BaseContext.__copy__ = _py314_basecontext_copy

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
from apps.assessments.services import AttemptService
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorReattemptAuthorization,
    ReattemptReason,
    ReattemptAuthStatus,
)
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus


@pytest.mark.django_db(transaction=True)
class TestAdminReattemptSuite:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        # Admin user with staff privileges
        self.admin = User.objects.create(
            email="admin_user@example.com",
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.admin.set_password("AdminSecure#2026")
        self.admin.save()

        # Student user (non-staff)
        self.student = User.objects.create(
            email="student_user@example.com",
            role=Role.STUDENT,
            is_staff=False,
        )
        self.student.set_password("StudentPass#123")
        self.student.save()
        self.student_profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="ADMIN-REATT-001",
            euid="EUID-ADMIN-001",
        )

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Admin Reattempt Exam",
            instructions="Exam instructions",
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

        self.q = Question.objects.create(question_type=QuestionType.MCQ, created_by=self.admin)
        self.qv = QuestionVersion.objects.create(
            question=self.q,
            version_number=1,
            title="Q1 Title",
            question_type=QuestionType.MCQ,
            points=10,
            status=VersionStatus.PUBLISHED,
            created_by=self.admin,
            type_config={"options": [{"id": "o1", "text": "A", "is_correct": True}]},
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

        # Create Attempt #1 in CANCELLED status
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

    # -------------------------------------------------------------------------
    # 1. Access Control & Rendering
    # -------------------------------------------------------------------------

    def test_admin_can_see_and_access_action_for_cancelled_attempt(self):
        """Admin can access give-another-chance page and sees confirmation form."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        resp = self.client.get(url)

        assert resp.status_code == 200
        assert "Give Student Another Chance" in resp.content.decode()
        assert "Target Attempt Details" in resp.content.decode()
        assert "Authorize Second-Chance Reattempt" in resp.content.decode()
        assert "EXAMINATION TERMINATED — WINDOW FOCUS LOST" in resp.content.decode()

    def test_non_admin_student_denied_access_to_admin_action(self):
        """Student or unauthenticated user cannot access the admin action."""
        # Unauthenticated redirects to admin login
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        resp = self.client.get(url)
        assert resp.status_code == 302
        assert "/admin/login/" in resp.url

        # Authenticated student is denied
        self.client.force_login(self.student)
        resp_student = self.client.get(url)
        assert resp_student.status_code in (302, 403)

    # -------------------------------------------------------------------------
    # 2. Reason Code Authorizations & Note Validation
    # -------------------------------------------------------------------------

    def test_admin_authorize_with_accidental_violation_succeeds(self):
        """Admin confirms ACCIDENTAL_VIOLATION; authorization created."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        resp = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Candidate experienced OS notification blur",
        })

        assert resp.status_code == 302
        auth = ProctorReattemptAuthorization.objects.get(
            student=self.student,
            assessment=self.assessment,
        )
        assert auth.status == ReattemptAuthStatus.AUTHORIZED
        assert auth.reason == ReattemptReason.ACCIDENTAL_VIOLATION
        assert auth.authorized_by == self.admin
        assert auth.new_attempt is None
        assert auth.original_attempt == self.attempt_1

    def test_admin_authorize_with_technical_problem_succeeds(self):
        """Admin confirms TECHNICAL_PROBLEM; authorization created."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        resp = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Chrome crashed during exam",
        })

        assert resp.status_code == 302
        auth = ProctorReattemptAuthorization.objects.get(
            student=self.student,
            assessment=self.assessment,
        )
        assert auth.reason == ReattemptReason.TECHNICAL_PROBLEM

    def test_admin_authorize_with_proctor_decision_succeeds(self):
        """Admin confirms PROCTOR_DECISION; authorization created."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        resp = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.PROCTOR_DECISION,
            "note": "Proctor reviewed recording and cleared candidate",
        })

        assert resp.status_code == 302
        auth = ProctorReattemptAuthorization.objects.get(
            student=self.student,
            assessment=self.assessment,
        )
        assert auth.reason == ReattemptReason.PROCTOR_DECISION

    def test_admin_authorize_other_without_note_rejected(self):
        """Reason OTHER strictly requires an explanatory note."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        resp = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.OTHER,
            "note": "",
        })

        # Stay on page / redirected with error message
        assert resp.status_code in (200, 302)
        assert ProctorReattemptAuthorization.objects.filter(
            student=self.student,
            assessment=self.assessment,
        ).count() == 0

    def test_admin_authorize_other_with_note_succeeds(self):
        """Reason OTHER with explanatory note succeeds."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        resp = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.OTHER,
            "note": "Discretionary override approved by department head",
        })

        assert resp.status_code == 302
        auth = ProctorReattemptAuthorization.objects.get(
            student=self.student,
            assessment=self.assessment,
        )
        assert auth.reason == ReattemptReason.OTHER
        assert auth.note == "Discretionary override approved by department head"

    # -------------------------------------------------------------------------
    # 3. Invariant Enforcements & Chaining Prevention
    # -------------------------------------------------------------------------

    def test_already_authorized_attempt_cannot_be_authorized_again(self):
        """If authorization already exists, admin action shows already authorized UI and rejects."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])

        # First authorization succeeds
        self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "First auth",
        })
        assert ProctorReattemptAuthorization.objects.count() == 1

        # Second attempt displays already-authorized alert
        resp = self.client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Reattempt Already Authorized" in content
        assert "Authorize Second-Chance Reattempt" not in content

        # Submitting post also fails
        resp_post = self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Duplicate",
        })
        assert ProctorReattemptAuthorization.objects.count() == 1

    def test_attempt_2_cannot_receive_another_reattempt(self):
        """Attempt #2 cannot spawn Attempt #3 (chaining strictly blocked)."""
        # Authorize and start Attempt #2
        self.client.force_login(self.admin)
        url_1 = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        self.client.post(url_1, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Auth 1",
        })

        auth = ProctorReattemptAuthorization.objects.get(student=self.student, assessment=self.assessment)
        auth.available_at = timezone.now() - timedelta(seconds=5)
        auth.save()

        attempt_2, _ = AttemptService.start_attempt(self.student, str(self.assessment.id))
        attempt_2.status = AttemptStatus.CANCELLED
        attempt_2.is_disqualified = True
        attempt_2.disqualification_reason = "EXAMINATION TERMINATED — TAB SWITCH"
        attempt_2.save()

        # Admin visits give-another-chance on Attempt #2
        url_2 = reverse("admin:assessments_testattempt_give_another_chance", args=[attempt_2.id])
        resp = self.client.get(url_2)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Chaining Prohibited" in content or "Reattempt Already Authorized" in content
        assert "Authorize Second-Chance Reattempt" not in content

        # Post is strictly blocked
        resp_post = self.client.post(url_2, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Attempt 3 attempt",
        })
        assert TestAttempt.objects.filter(student=self.student, assessment=self.assessment).count() == 2

    def test_admin_action_does_not_reopen_attempt_1(self):
        """Attempt #1 status remains strictly CANCELLED after authorization."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Check attempt 1 status",
        })

        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.CANCELLED
        assert self.attempt_1.is_disqualified is True

    def test_admin_action_creates_no_attempt_2_immediately(self):
        """Admin authorization creates an authorization record, NOT Attempt #2 immediately."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Check delay window",
        })

        # Exactly 1 attempt in database (Attempt #1)
        assert TestAttempt.objects.filter(student=self.student, assessment=self.assessment).count() == 1

        # Authorization is in AUTHORIZED state with 60s delay
        auth = ProctorReattemptAuthorization.objects.get(student=self.student, assessment=self.assessment)
        assert auth.status == ReattemptAuthStatus.AUTHORIZED
        assert auth.new_attempt is None
        assert auth.available_at > timezone.now()

    # -------------------------------------------------------------------------
    # 4. Audit Trail & Actor Integrity
    # -------------------------------------------------------------------------

    def test_admin_action_records_audit_trail_and_actor(self):
        """Admin action produces AuditLog and ProctorIntervention with admin as actor."""
        self.client.force_login(self.admin)
        url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        self.client.post(url, {
            "confirm": "1",
            "reason": ReattemptReason.ACCIDENTAL_VIOLATION,
            "note": "Audit verification note",
        })

        # ProctorIntervention recorded
        intervention = ProctorIntervention.objects.filter(
            attempt=self.attempt_1,
            event_type=InterventionType.REATTEMPT_AUTHORIZED,
        ).first()
        assert intervention is not None
        assert intervention.proctor == self.admin
        assert intervention.student == self.student
        assert intervention.reason_code == ReattemptReason.ACCIDENTAL_VIOLATION

        # ProctorReattemptAuthorization recorded
        auth = ProctorReattemptAuthorization.objects.get(student=self.student, assessment=self.assessment)
        assert auth.authorized_by == self.admin

        # AuditLog recorded
        audit = AuditLog.objects.filter(
            action="PROCTOR_REATTEMPT_AUTHORIZED",
            target_id=str(self.attempt_1.id),
        ).first()
        assert audit is not None
        assert audit.actor == self.admin

    # -------------------------------------------------------------------------
    # 5. Changelist Action Dropdown
    # -------------------------------------------------------------------------

    def test_changelist_action_redirects_single_selection(self):
        """Selecting 1 attempt in changelist redirects to give-another-chance page."""
        self.client.force_login(self.admin)
        changelist_url = reverse("admin:assessments_testattempt_changelist")

        resp = self.client.post(changelist_url, {
            "action": "give_student_another_chance",
            "_selected_action": [str(self.attempt_1.id)],
        })

        assert resp.status_code == 302
        expected_url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        assert resp.url == expected_url

    def test_changelist_action_warns_on_multiple_selections(self):
        """Selecting multiple attempts shows warning and does not authorize."""
        # Create a second attempt
        student_2 = User.objects.create(email="student_2@example.com", role=Role.STUDENT)
        attempt_other = TestAttempt.objects.create(
            student=student_2,
            assessment=self.assessment,
            assessment_snapshot=self.snapshot,
            attempt_number=1,
            status=AttemptStatus.CANCELLED,
            is_disqualified=True,
        )

        self.client.force_login(self.admin)
        changelist_url = reverse("admin:assessments_testattempt_changelist")

        resp = self.client.post(changelist_url, {
            "action": "give_student_another_chance",
            "_selected_action": [str(self.attempt_1.id), str(attempt_other.id)],
        })

        assert resp.status_code == 302
        assert resp.url == changelist_url
        assert ProctorReattemptAuthorization.objects.count() == 0

    def test_admin_change_form_renders_button_and_disables_when_already_authorized(self):
        """Admin change form shows action button for eligible attempt, and disabled badge when authorized."""
        self.client.force_login(self.admin)
        change_url = reverse("admin:assessments_testattempt_change", args=[self.attempt_1.id])

        # Initial state: Eligible, shows button
        resp = self.client.get(change_url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Give Student Another Chance" in content

        # Now authorize it
        auth_url = reverse("admin:assessments_testattempt_give_another_chance", args=[self.attempt_1.id])
        self.client.post(auth_url, {
            "confirm": "1",
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Hardware glitch",
        })

        # Reload change form: shows already authorized badge, NO actionable button
        resp_after = self.client.get(change_url)
        assert resp_after.status_code == 200
        content_after = resp_after.content.decode()
        assert "Reattempt already authorized" in content_after
        # Action button should no longer be present
        assert 'href="' + auth_url + '"' not in content_after
