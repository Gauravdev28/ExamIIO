import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile
from apps.accounts.services import StudentService
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
)
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
    ResultVisibility,
)
from apps.assessments.services import AttemptService, AssessmentAttendanceService
from apps.results.models import (
    Certificate,
    CertificateStatus,
    AssessmentResult,
    ResultStatus,
)
from apps.results.services import ResultFinalizationService
from apps.results.certificate_service import CertificateService


@pytest.mark.django_db(transaction=True)
def test_craft_society_golden_path_e2e():
    """
    Complete Golden Path End-to-End Test for Craft Society:
    1. Admin onboards student with roll number
    2. Student logs in (first login required), supplies certificate_name, changes password
    3. Student logs in with roll number and new password
    4. Admin authors exam, adds questions, publishes exam
    5. Student starts attempt
    6. Student submits attempt
    7. Result evaluation finalizes score
    8. Global Attendance records ATTENDED
    9. Participation Certificate generated with printed_name snapshot
    10. Admin releases results
    11. Student accesses result and downloads participation certificate
    """
    client = APIClient()

    # 1. Admin Setup
    admin = User.objects.create_user(
        email="exam_convenor@craftsociety.test",
        password="AdminSecurePassword123!",
        role=Role.ADMIN,
        display_name="Exam Convenor"
    )

    # Bulk / Roll Number Onboarding
    temp_password = "TempPassword123!"
    student, profile = StudentService.create_student(
        roll_number="CS-2026-999",
        initial_password=temp_password,
        actor=admin
    )
    assert student.first_login_required is True
    assert student.email == "cs-2026-999@student.craftsociety.internal"

    # 2. Student First Login & Certificate Name Setup
    login_res = client.post("/api/v1/auth/login/", {
        "email": student.email,
        "password": temp_password
    })
    assert login_res.status_code == status.HTTP_200_OK
    assert login_res.json()['data']['user']['first_login_required'] is True

    # Authenticate as student
    client.force_authenticate(user=student)

    # Change password and set Full Name for Certificate Printing
    pw_res = client.post("/api/v1/auth/change-password/", {
        "current_password": temp_password,
        "new_password": "StudentPermanentPass123!",
        "confirm_password": "StudentPermanentPass123!",
        "certificate_name": "Eleanor Vance, B.Eng"
    })
    assert pw_res.status_code == status.HTTP_200_OK

    student.refresh_from_db()
    assert student.first_login_required is False
    assert student.student_profile.certificate_name == "Eleanor Vance, B.Eng"

    # 3. Dual Login via Roll Number and New Password
    client.logout()
    roll_login_res = client.post("/api/v1/auth/login/", {
        "email": "CS-2026-999",
        "password": "StudentPermanentPass123!"
    })
    assert roll_login_res.status_code == status.HTTP_200_OK
    assert roll_login_res.json()['data']['user']['first_login_required'] is False

    # 4. Admin Authors Exam & Publishes
    now = timezone.now()
    exam = Assessment.objects.create(
        title="Craft Society Annual Software Challenge",
        description="Official software engineering assessment",
        created_by=admin,
        status=AssessmentStatus.DRAFT,
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=90,
        passing_percentage=Decimal('50.00'),
        attempt_limit=1,
        proctoring_enabled=True,
        camera_required=True,
        max_confirmed_violations=3,
        result_visibility=ResultVisibility.MANUAL,
    )

    # Assign candidate
    assignment = AssessmentAssignment.objects.create(
        assessment=exam,
        student=student,
        status=AssignmentStatus.ASSIGNED,
        assigned_by=admin
    )

    # Add an MCQ question
    q = Question.objects.create(created_by=admin)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="What is idempotency?",
        description="Select the correct definition",
        question_type=QuestionType.MCQ,
        difficulty=Difficulty.EASY,
        status=VersionStatus.PUBLISHED,
        points=Decimal('10.00'),
        type_config={
            "options": [
                {"id": "opt_1", "text": "Operation produces the same result when executed multiple times"},
                {"id": "opt_2", "text": "Operation runs in constant time O(1)"}
            ],
            "correct_options": ["opt_1"]
        }
    )
    aq = AssessmentQuestion.objects.create(
        assessment=exam,
        question_version=qv,
        order=1,
        points=10
    )

    # Freeze Snapshot & Publish
    snapshot = AssessmentSnapshot.objects.create(
        assessment=exam,
        version_number=1,
        snapshot_data={
            "title": exam.title,
            "passing_percentage": 50.0
        },
        server_evaluation_bundle={
            "questions_eval": {
                "q_1": {
                    "correct_type_config": {
                        "correct_options": ["opt_1"]
                    }
                }
            }
        }
    )
    sq = AssessmentSnapshotQuestion.objects.create(
        snapshot=snapshot,
        question_version=qv,
        snapshot_question_id="q_1",
        order=1,
        title=qv.title,
        description=qv.description,
        question_type=QuestionType.MCQ,
        points=10,
        type_config=qv.type_config
    )

    exam.status = AssessmentStatus.PUBLISHED
    exam.published_at = timezone.now()
    exam.total_points = 10
    exam.save()

    # 5. Student Starts Attempt
    attempt, created = AttemptService.start_attempt(
        student=student,
        assessment_id=str(exam.id)
    )
    assert created is True
    assert attempt.status == AttemptStatus.IN_PROGRESS

    # Save student answer (selects opt_1)
    ans = AttemptAnswer.objects.get(
        attempt=attempt,
        snapshot_question=sq
    )
    ans.is_answered = True
    ans.selected_options = ["opt_1"]
    ans.save()

    # 6. Student Submits Attempt
    submitted_attempt = AttemptService.submit_attempt(
        student=student,
        attempt_id=str(attempt.id)
    )
    assert submitted_attempt.status == AttemptStatus.SUBMITTED

    # 7. Finalize Result Scoring
    result = ResultFinalizationService.finalize_attempt(attempt_id=str(submitted_attempt.id))
    assert result.status == ResultStatus.FINALIZED
    assert result.total_score_earned == Decimal('10.00')
    assert result.percentage == Decimal('100.00')
    assert result.is_passed is True

    # 8. Check Global Attendance
    att_data = AssessmentAttendanceService.get_attendance_data(assessment=exam)
    assert att_data['summary']['total_attended'] == 1
    assert att_data['summary']['total_disqualified'] == 0
    candidate_record = att_data['results'][0]
    assert candidate_record['attendance_status'] == 'ATTENDED'
    assert candidate_record['student_name'] == 'Eleanor Vance, B.Eng'

    # 9. Verify Participation Certificate Generated
    cert = Certificate.objects.filter(exam=exam, student=student).first()
    assert cert is not None
    assert cert.attempt_id == attempt.id
    assert cert.printed_name == "Eleanor Vance, B.Eng"
    assert cert.status == CertificateStatus.ISSUED
    assert cert.certificate_id.startswith("CS-CERT-")
    assert bool(cert.pdf_file)

    # 10. Admin Releases Results
    result.is_released = True
    result.save(update_fields=['is_released'])

    # 11. Student Downloads Certificate PDF
    client.force_authenticate(user=student)
    cert_res = client.get(f"/api/v1/student/certificates/{cert.id}/download/")
    assert cert_res.status_code == status.HTTP_200_OK
    assert cert_res['Content-Type'] == 'application/pdf'

    # Public Verification
    client.logout()  # Anonymous
    verify_res = client.get(f"/api/v1/public/certificates/verify/{cert.certificate_id}/")
    assert verify_res.status_code == status.HTTP_200_OK
    verify_data = verify_res.json()['data']
    assert verify_data['is_valid'] is True
    assert verify_data['printed_name'] == "Eleanor Vance, B.Eng"
    assert verify_data['exam_title'] == exam.title
