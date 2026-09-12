"""
Manual Verification Test Script for Phase 17:
Scenario: Assessment for test 001 - Full Second-Chance Flow via Proctoring Timeline

Follows the exact 21 steps:
1. Create/use: Assessment for test 001
2. Student starts Attempt #1.
3. Student changes browser window.
4. Safe Browser detects WINDOW_FOCUS_LOST.
5. Attempt #1 becomes CANCELLED / DISQUALIFIED.
6. Admin opens: Assessment for test 001 -> Proctoring.
7. Find the disqualified student.
8. Click: Inspect Timeline.
9. Verify the existing four Human Review Verdict options are still present.
10. Verify a separate: "Give Student Another Chance" section exists.
11. Click it.
12. Select: Technical problem.
13. Enter a note.
14. Confirm.
15. Verify: Attempt #1 = CANCELLED, Reattempt = AUTHORIZED, No Attempt #2 exists yet.
16. Verify 60-second server-authoritative preparation state.
17. Start Attempt #2 as the student.
18. Verify: Attempt #2 = IN_PROGRESS, Attempt number = 2, Attempt #1 remains CANCELLED.
19. Return to Proctoring Timeline.
20. Verify: Reattempt = CONSUMED, New Attempt = #2.
21. Verify there is no option to authorize Attempt #3.
"""
from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, StudentProfile, Role
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
)


@pytest.mark.django_db(transaction=True)
def test_manual_verification_scenario_phase_17():
    print("\n" + "=" * 70)
    print("STARTING PHASE 17 MANUAL VERIFICATION SCENARIO (STEPS 1-21)")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # STEP 1: Create/use: Assessment for test 001
    # -------------------------------------------------------------------------
    admin = User.objects.create_user(
        email="admin_verif@example.com",
        password="AdminPass123!",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )

    student_user = User.objects.create_user(
        email="candidate_001@example.com",
        password="StudentPass123!",
        role=Role.STUDENT,
    )
    student = StudentProfile.objects.create(
        user=student_user,
        roll_number="TEST-001",
        euid="EUID-001",
        certificate_name="Candidate 001",
    )

    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Assessment for test 001",
        instructions="Proctored assessment test 001",
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=5),
        duration_minutes=60,
        passing_percentage=50,
        attempt_limit=1,
        created_by=admin,
    )

    q = Question.objects.create(question_type=QuestionType.MCQ, created_by=admin)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="MCQ Question 1",
        question_type=QuestionType.MCQ,
        points=10,
        status=VersionStatus.PUBLISHED,
        created_by=admin,
        type_config={"options": [{"id": "o1", "text": "Correct", "is_correct": True}]},
    )
    snap = AssessmentSnapshot.objects.create(
        assessment=assessment,
        version_number=1,
    )
    AssessmentSnapshotQuestion.objects.create(
        snapshot=snap,
        question_version=qv,
        snapshot_question_id=str(q.id),
        order=1,
        points=10,
        question_type=qv.question_type,
        type_config=qv.type_config,
    )

    assignment = AssessmentAssignment.objects.create(
        assessment=assessment,
        student=student_user,
        assigned_by=admin,
        status=AssignmentStatus.ASSIGNED,
    )

    print("✓ Step 1: Created 'Assessment for test 001' and candidate_001 assignment.")

    # -------------------------------------------------------------------------
    # STEP 2: Student starts Attempt #1.
    # -------------------------------------------------------------------------
    attempt_1, is_new = AttemptService.start_attempt(student_user, str(assessment.id))
    assert is_new is True
    assert attempt_1.attempt_number == 1
    assert attempt_1.status == AttemptStatus.IN_PROGRESS

    proc_session = ProctoringSession.objects.create(
        attempt=attempt_1,
        status=ProctoringSessionStatus.ACTIVE,
    )

    client_student = APIClient()
    client_student.force_authenticate(user=student_user)

    print("✓ Step 2: Student started Attempt #1 (IN_PROGRESS, attempt_number=1).")

    # -------------------------------------------------------------------------
    # STEP 3 & 4: Student changes browser window -> Safe Browser detects WINDOW_FOCUS_LOST
    # -------------------------------------------------------------------------
    security_event_url = f"/api/v1/student/attempts/{attempt_1.id}/proctoring/events/"
    sec_resp = client_student.post(
        security_event_url,
        {"event_type": "WINDOW_FOCUS_LOST", "metadata": {"reason": "Tab switched"}},
        format="json",
    )
    assert sec_resp.status_code == status.HTTP_202_ACCEPTED
    assert sec_resp.data["status"] == "RECORDED"

    print("✓ Steps 3 & 4: Safe Browser reported WINDOW_FOCUS_LOST.")

    # -------------------------------------------------------------------------
    # STEP 5: Attempt #1 becomes CANCELLED / DISQUALIFIED.
    # -------------------------------------------------------------------------
    attempt_1.refresh_from_db()
    assert attempt_1.status == AttemptStatus.CANCELLED
    assert attempt_1.is_disqualified is True
    print(f"✓ Step 5: Attempt #1 is CANCELLED / DISQUALIFIED (disqualification_reason: {attempt_1.disqualification_reason}).")

    # -------------------------------------------------------------------------
    # STEP 6 & 7: Admin opens Assessment for test 001 -> Proctoring, finds student
    # -------------------------------------------------------------------------
    client_admin = APIClient()
    client_admin.force_authenticate(user=admin)

    list_url = f"/api/v1/admin/assessments/{assessment.id}/proctoring/sessions/"
    list_resp = client_admin.get(list_url)
    assert list_resp.status_code == status.HTTP_200_OK

    student_sessions = [
        s for s in list_resp.data["results"]
        if s["student"]["id"] == str(student_user.id) or "candidate_001" in s["student"]["email"]
    ]
    assert len(student_sessions) >= 1
    target_session = student_sessions[0]
    assert target_session["is_disqualified"] is True
    assert target_session["attempt_status"] in [AttemptStatus.CANCELLED, "DISQUALIFIED"]

    print("✓ Steps 6 & 7: Admin opened Proctoring dashboard and located disqualified student.")

    # -------------------------------------------------------------------------
    # STEP 8: Click "Inspect Timeline" -> Proctoring Timeline & Evidence Review modal
    # -------------------------------------------------------------------------
    detail_url = f"/api/v1/admin/proctoring/sessions/{proc_session.id}/"
    detail_resp = client_admin.get(detail_url)
    assert detail_resp.status_code == status.HTTP_200_OK
    session_data = detail_resp.data

    print("✓ Step 8: Loaded Proctoring Timeline & Evidence Review detail.")

    # -------------------------------------------------------------------------
    # STEP 9: Verify the existing four Human Review Verdict options are present
    # -------------------------------------------------------------------------
    allowed_verdicts = {choice[0] for choice in ProctoringReview._meta.get_field('decision').choices}
    expected_verdicts = {
        "REVIEWED_CLEAN",
        "SUSPICIOUS_CONFIRMED",
        "REQUIRES_FURTHER_INSPECTION",
        "DISMISSED_FALSE_POSITIVE",
    }
    assert allowed_verdicts == expected_verdicts
    assert "REATTEMPT" not in allowed_verdicts
    assert "GIVE_ANOTHER_CHANCE" not in allowed_verdicts

    print("✓ Step 9: Confirmed existing 4 Human Review Verdict options are strictly preserved and untouched.")

    # -------------------------------------------------------------------------
    # STEP 10: Verify a separate "Give Student Another Chance" section exists
    # -------------------------------------------------------------------------
    assert session_data["can_grant_reattempt"] is True
    assert session_data["reattempt"] is None
    assert session_data["attempt_number"] == 1
    assert session_data["is_already_reattempt"] is False
    assert session_data["attempt_status"] in [AttemptStatus.CANCELLED, "DISQUALIFIED"]

    print("✓ Step 10: Verified separate Second-Chance Action section is eligible (can_grant_reattempt=True).")

    # -------------------------------------------------------------------------
    # STEP 11, 12, 13, 14: Click action, select "Technical problem", enter note, confirm
    # -------------------------------------------------------------------------
    reattempt_url = f"/api/v1/proctor/attempts/{attempt_1.id}/reattempt/"
    auth_resp = client_admin.post(
        reattempt_url,
        {
            "reason": ReattemptReason.TECHNICAL_PROBLEM,
            "note": "Candidate encountered OS notification blur issue during window switch",
        },
    )
    assert auth_resp.status_code == status.HTTP_201_CREATED
    assert auth_resp.data["status"] == ReattemptAuthStatus.AUTHORIZED
    assert auth_resp.data["reason"] == ReattemptReason.TECHNICAL_PROBLEM
    print("✓ Steps 11-14: Confirmed & authorized second chance with TECHNICAL_PROBLEM and note.")

    # -------------------------------------------------------------------------
    # STEP 15: Verify: Attempt #1 = CANCELLED, Reattempt = AUTHORIZED, No Attempt #2 exists yet
    # -------------------------------------------------------------------------
    attempt_1.refresh_from_db()
    assert attempt_1.status == AttemptStatus.CANCELLED
    assert attempt_1.is_disqualified is True

    attempt_count = TestAttempt.objects.filter(assessment=assessment, student=student_user).count()
    assert attempt_count == 1
    assert not TestAttempt.objects.filter(assessment=assessment, student=student_user, attempt_number=2).exists()

    auth = ProctorReattemptAuthorization.objects.get(original_attempt=attempt_1)
    assert auth.status == ReattemptAuthStatus.AUTHORIZED
    assert auth.new_attempt_id is None

    print("✓ Step 15: Verified Attempt #1 is permanently CANCELLED and NO Attempt #2 exists yet.")

    # -------------------------------------------------------------------------
    # STEP 16: Verify 60-second server-authoritative preparation state
    # -------------------------------------------------------------------------
    # Before 60 seconds have elapsed, AttemptService.start_attempt must reject
    with pytest.raises(Exception) as exc_info:
        AttemptService.start_attempt(student_user, str(assessment.id))
    assert "preparing" in str(exc_info.value).lower() or "reattempt_preparing" in str(exc_info.value).lower()

    # Timeline session detail reflects AUTHORIZED state and remaining_seconds
    detail_resp = client_admin.get(detail_url)
    assert detail_resp.data["can_grant_reattempt"] is False
    assert detail_resp.data["reattempt"]["status"] == ReattemptAuthStatus.AUTHORIZED
    assert detail_resp.data["reattempt"]["remaining_seconds"] is not None
    assert 0 <= detail_resp.data["reattempt"]["remaining_seconds"] <= 60

    print("✓ Step 16: Verified 60-second server-authoritative preparation state (start before 60s rejected).")

    # -------------------------------------------------------------------------
    # STEP 17 & 18: Start Attempt #2 as the student
    # -------------------------------------------------------------------------
    # Simulate elapsed 60 seconds
    auth.available_at = timezone.now() - timedelta(seconds=1)
    auth.save()

    attempt_2, is_new_2 = AttemptService.start_attempt(student_user, str(assessment.id))
    assert is_new_2 is True
    assert attempt_2.attempt_number == 2
    assert attempt_2.status == AttemptStatus.IN_PROGRESS

    # Verify Attempt #1 remains CANCELLED
    attempt_1.refresh_from_db()
    assert attempt_1.status == AttemptStatus.CANCELLED

    print("✓ Steps 17 & 18: Student started Attempt #2 (attempt_number=2, IN_PROGRESS). Attempt #1 remains CANCELLED.")

    # -------------------------------------------------------------------------
    # STEP 19 & 20: Return to Proctoring Timeline -> Reattempt = CONSUMED, New Attempt = #2
    # -------------------------------------------------------------------------
    detail_resp = client_admin.get(detail_url)
    assert detail_resp.status_code == status.HTTP_200_OK
    assert detail_resp.data["can_grant_reattempt"] is False
    assert detail_resp.data["reattempt"]["status"] == ReattemptAuthStatus.CONSUMED
    assert detail_resp.data["reattempt"]["new_attempt_number"] == 2
    assert detail_resp.data["reattempt"]["new_attempt_id"] == str(attempt_2.id)

    print("✓ Steps 19 & 20: Timeline modal confirms Reattempt=CONSUMED, New Attempt=#2.")

    # -------------------------------------------------------------------------
    # STEP 21: Verify there is no option to authorize Attempt #3
    # -------------------------------------------------------------------------
    # A) Attempt #1 timeline detail has can_grant_reattempt=False
    assert detail_resp.data["can_grant_reattempt"] is False

    # B) Attempt #2 timeline detail has is_already_reattempt=True and can_grant_reattempt=False
    proc_session_2 = ProctoringSession.objects.create(
        attempt=attempt_2,
        status=ProctoringSessionStatus.ACTIVE,
    )
    detail_2_url = f"/api/v1/admin/proctoring/sessions/{proc_session_2.id}/"
    detail_2_resp = client_admin.get(detail_2_url)
    assert detail_2_resp.status_code == status.HTTP_200_OK
    assert detail_2_resp.data["is_already_reattempt"] is True
    assert detail_2_resp.data["can_grant_reattempt"] is False
    assert detail_2_resp.data["attempt_number"] == 2

    # C) Direct API call to authorize reattempt on Attempt #2 fails
    attempt_2.status = AttemptStatus.CANCELLED
    attempt_2.is_disqualified = True
    attempt_2.save()

    illegal_auth_resp = client_admin.post(
        f"/api/v1/proctor/attempts/{attempt_2.id}/reattempt/",
        {"reason": ReattemptReason.TECHNICAL_PROBLEM, "note": "Illegal 3rd chance attempt"},
    )
    assert illegal_auth_resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    print("✓ Step 21: Verified Attempt #3 is strictly impossible across UI and authoritative API.")
    print("=" * 70)
    print("PHASE 17 MANUAL VERIFICATION SCENARIO PASSED ALL 21 STEPS!")
    print("=" * 70 + "\n")
