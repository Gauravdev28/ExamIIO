import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    AssessmentQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    VersionStatus,
)
from apps.evaluator.models import (
    CodeSubmission,
    CodeTestCaseResult,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
    TestCaseVerdict,
)
from apps.results.models import (
    AssessmentResult,
    QuestionResult,
    ResultStatus,
)
from apps.assessments.services import AssessmentSnapshotService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_review@codeguard.local",
        password="AdminPassword123!",
        role=Role.ADMIN,
        display_name="Admin Reviewer",
        is_active=True
    )


@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="proctor_review@codeguard.local",
        password="ProctorPassword123!",
        role=Role.PROCTOR,
        display_name="Proctor Reviewer",
        is_active=True
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_review@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Student Display",
        is_active=True
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="ROLL-REV-101",
        euid="EUID-REV-101",
        certificate_name="Student Official Name",
        first_login_required=False
    )
    return user


@pytest.fixture
def full_assessment_setup(db, admin_user, student_user):
    now = timezone.now()

    # 1. Create Assessment
    assessment = Assessment.objects.create(
        title="Comprehensive Review Assessment",
        description="Testing admin answer review",
        duration_minutes=60,
        total_points=50,
        passing_percentage=50.00,
        status=AssessmentStatus.DRAFT,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(hours=5),
        created_by=admin_user
    )

    from apps.questions.models import CodingQuestionConfig, TestCase, SQLQuestionConfig

    # 2. Questions in Question Bank
    # Q1: MCQ
    q_mcq = Question.objects.create(created_by=admin_user, question_type=QuestionType.MCQ)
    qv_mcq = QuestionVersion.objects.create(
        question=q_mcq,
        version_number=1,
        status=VersionStatus.PUBLISHED,
        question_type=QuestionType.MCQ,
        title="What is the output of 2 + 2 in Python?",
        description="Basic arithmetic evaluation",
        difficulty="EASY",
        type_config={
            "options": [
                {"id": "opt_1", "text": "3"},
                {"id": "opt_2", "text": "4"},
                {"id": "opt_3", "text": "5"},
            ],
            "correct_options": ["opt_2"]
        },
        created_by=admin_user
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_mcq,
        order=1,
        points=10
    )

    # Q2: MULTI_SELECT
    q_ms = Question.objects.create(created_by=admin_user, question_type=QuestionType.MULTI_SELECT)
    qv_ms = QuestionVersion.objects.create(
        question=q_ms,
        version_number=1,
        status=VersionStatus.PUBLISHED,
        question_type=QuestionType.MULTI_SELECT,
        title="Select all prime numbers",
        description="Select all primes from list",
        difficulty="MEDIUM",
        type_config={
            "options": [
                {"id": "opt_m1", "text": "2"},
                {"id": "opt_m2", "text": "3"},
                {"id": "opt_m3", "text": "4"},
                {"id": "opt_m4", "text": "5"},
            ],
            "correct_options": ["opt_m1", "opt_m2", "opt_m4"]
        },
        created_by=admin_user
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_ms,
        order=2,
        points=10
    )

    # Q3: SHORT_ANSWER
    q_sa = Question.objects.create(created_by=admin_user, question_type=QuestionType.SHORT_ANSWER)
    qv_sa = QuestionVersion.objects.create(
        question=q_sa,
        version_number=1,
        status=VersionStatus.PUBLISHED,
        question_type=QuestionType.SHORT_ANSWER,
        title="What keyword defines a function in Python?",
        description="Enter the python function keyword",
        difficulty="EASY",
        type_config={
            "exact_matches": ["def", "def "],
            "case_sensitive": False
        },
        created_by=admin_user
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_sa,
        order=3,
        points=10
    )

    # Q4: CODING
    q_code = Question.objects.create(created_by=admin_user, question_type=QuestionType.CODING)
    qv_code = QuestionVersion.objects.create(
        question=q_code,
        version_number=1,
        status=VersionStatus.PUBLISHED,
        question_type=QuestionType.CODING,
        title="Sum of two numbers",
        description="Write a program to sum two integers from stdin",
        difficulty="MEDIUM",
        created_by=admin_user
    )
    coding_cfg = CodingQuestionConfig.objects.create(
        question_version=qv_code,
        problem_statement="Write a program to sum two integers from stdin",
        allowed_languages=["PYTHON"]
    )
    TestCase.objects.create(
        coding_config=coding_cfg,
        execution_order=1,
        is_hidden=False,
        points=5,
        input_data="2 3\n",
        expected_output="5\n"
    )
    TestCase.objects.create(
        coding_config=coding_cfg,
        execution_order=2,
        is_hidden=True,
        points=5,
        input_data="100 200\n",
        expected_output="300\n"
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_code,
        order=4,
        points=10
    )

    # Q5: SQL
    q_sql = Question.objects.create(created_by=admin_user, question_type=QuestionType.SQL)
    qv_sql = QuestionVersion.objects.create(
        question=q_sql,
        version_number=1,
        status=VersionStatus.PUBLISHED,
        question_type=QuestionType.SQL,
        title="Select all active users",
        description="Write a query to fetch all active users",
        difficulty="EASY",
        created_by=admin_user
    )
    SQLQuestionConfig.objects.create(
        question_version=qv_sql,
        problem_statement="Write a query to fetch all active users",
        schema_setup_sql="CREATE TABLE users (id INT, is_active BOOLEAN);",
        expected_result_definition="SELECT * FROM users WHERE is_active = TRUE;",
        allowed_dialect="POSTGRESQL"
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_sql,
        order=5,
        points=10
    )

    assessment.status = AssessmentStatus.PUBLISHED
    assessment.save()

    # 3. Create Immutable Snapshot
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, admin_user)

    # 4. Create Attempt
    attempt = TestAttempt.objects.create(
        student=student_user,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=AttemptStatus.SUBMITTED,
        started_at=now - timedelta(minutes=45),
        submitted_at=now - timedelta(minutes=5)
    )

    snap_questions = list(snapshot.snapshot_questions.all().order_by('order'))
    sq1, sq2, sq3, sq4, sq5 = snap_questions

    # 5. Candidate Answers
    ans1 = AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sq1,
        question_id=sq1.snapshot_question_id,
        question_type=sq1.question_type,
        selected_options=["opt_2"],
        is_answered=True
    )
    ans2 = AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sq2,
        question_id=sq2.snapshot_question_id,
        question_type=sq2.question_type,
        selected_options=["opt_m1", "opt_m3"],  # Partial/incorrect choice
        is_answered=True
    )
    ans3 = AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sq3,
        question_id=sq3.snapshot_question_id,
        question_type=sq3.question_type,
        text_response="def",
        is_answered=True
    )
    ans4 = AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sq4,
        question_id=sq4.snapshot_question_id,
        question_type=sq4.question_type,
        code_response="a, b = map(int, input().split()); print(a + b)",
        code_language="PYTHON",
        is_answered=True
    )
    ans5 = AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sq5,
        question_id=sq5.snapshot_question_id,
        question_type=sq5.question_type,
        sql_response="SELECT * FROM users WHERE is_active = TRUE;",
        is_answered=True
    )

    # Code submission for Q4
    code_sub = CodeSubmission.objects.create(
        attempt=attempt,
        snapshot_question=sq4,
        submission_type=SubmissionType.SUBMIT,
        language="PYTHON",
        source_code="a, b = map(int, input().split()); print(a + b)",
        status=SubmissionStatus.COMPLETED,
        verdict=CodeVerdict.ACCEPTED,
        passed_test_cases=2,
        total_test_cases=2,
        score_awarded=Decimal("10.00"),
        execution_time_ms=45,
        memory_used_kb=1024
    )
    # Test case results for code submission
    CodeTestCaseResult.objects.create(
        submission=code_sub,
        test_case_index=1,
        is_hidden=False,
        verdict=TestCaseVerdict.PASSED,
        points_awarded=Decimal("5.00"),
        max_points=Decimal("5.00"),
        execution_time_ms=20,
        memory_used_kb=512,
        public_input="2 3\n",
        expected_output="5\n",
        actual_output="5\n"
    )
    CodeTestCaseResult.objects.create(
        submission=code_sub,
        test_case_index=2,
        is_hidden=True,
        verdict=TestCaseVerdict.PASSED,
        points_awarded=Decimal("5.00"),
        max_points=Decimal("5.00"),
        execution_time_ms=25,
        memory_used_kb=512,
        public_input=None,
        expected_output=None,
        actual_output=None
    )

    # 6. Evaluated Assessment Result
    result = AssessmentResult.objects.create(
        attempt=attempt,
        student=student_user,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=ResultStatus.FINALIZED,
        total_score_earned=Decimal("40.00"),
        total_possible_score=Decimal("50.00"),
        percentage=Decimal("80.00"),
        is_passed=True,
        total_questions=5,
        answered_questions=5,
        correct_questions=4,
        partially_correct_questions=0,
        incorrect_questions=1,
        skipped_questions=0,
        time_spent_seconds=2400,
        finalized_at=now
    )

    # Question Results
    qr1 = QuestionResult.objects.create(
        assessment_result=result,
        snapshot_question=sq1,
        question_id=sq1.snapshot_question_id,
        question_type=sq1.question_type,
        earned_points=Decimal("10.00"),
        max_points=Decimal("10.00"),
        is_correct=True,
        is_partially_correct=False,
        is_skipped=False,
        time_spent_seconds=300,
        evaluation_details={"user_selected": ["opt_2"], "is_correct": True}
    )
    qr2 = QuestionResult.objects.create(
        assessment_result=result,
        snapshot_question=sq2,
        question_id=sq2.snapshot_question_id,
        question_type=sq2.question_type,
        earned_points=Decimal("0.00"),
        max_points=Decimal("10.00"),
        is_correct=False,
        is_partially_correct=False,
        is_skipped=False,
        time_spent_seconds=400,
        evaluation_details={"user_selected": ["opt_m1", "opt_m3"], "is_correct": False}
    )
    qr3 = QuestionResult.objects.create(
        assessment_result=result,
        snapshot_question=sq3,
        question_id=sq3.snapshot_question_id,
        question_type=sq3.question_type,
        earned_points=Decimal("10.00"),
        max_points=Decimal("10.00"),
        is_correct=True,
        is_partially_correct=False,
        is_skipped=False,
        time_spent_seconds=200,
        evaluation_details={"user_text": "def", "is_correct": True}
    )
    qr4 = QuestionResult.objects.create(
        assessment_result=result,
        snapshot_question=sq4,
        question_id=sq4.snapshot_question_id,
        question_type=sq4.question_type,
        earned_points=Decimal("10.00"),
        max_points=Decimal("10.00"),
        is_correct=True,
        is_partially_correct=False,
        is_skipped=False,
        time_spent_seconds=1000,
        evaluation_details={
            "submission_id": str(code_sub.id),
            "verdict": "ACCEPTED",
            "passed_test_cases": 2,
            "total_test_cases": 2
        }
    )
    qr5 = QuestionResult.objects.create(
        assessment_result=result,
        snapshot_question=sq5,
        question_id=sq5.snapshot_question_id,
        question_type=sq5.question_type,
        earned_points=Decimal("10.00"),
        max_points=Decimal("10.00"),
        is_correct=True,
        is_partially_correct=False,
        is_skipped=False,
        time_spent_seconds=500,
        evaluation_details={
            "sql_query": "SELECT * FROM users WHERE is_active = TRUE;",
            "is_correct": True,
            "verdict": "ACCEPTED"
        }
    )

    return {
        "assessment": assessment,
        "snapshot": snapshot,
        "attempt": attempt,
        "result": result,
        "student": student_user,
        "admin": admin_user,
        "q_mcq": q_mcq,
        "qv_mcq": qv_mcq,
        "code_sub": code_sub,
    }


@pytest.mark.django_db
class TestAdminCandidateResultReview:

    def test_01_admin_receives_detailed_result(self, api_client, admin_user, full_assessment_setup):
        """Admin can access candidate result review with complete schema."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        payload = response.data
        data = payload.get("data", payload)

        # Top level verification
        assert str(data["id"]) == str(setup["result"].id)
        assert str(data["attempt_id"]) == str(setup["attempt"].id)
        assert str(data["assessment_id"]) == str(setup["assessment"].id)
        assert data["assessment_title"] == setup["assessment"].title
        assert data["status"] == "EVALUATED"
        assert Decimal(str(data["total_score_earned"])) == Decimal("40.00")
        assert Decimal(str(data["total_possible_score"])) == Decimal("50.00")
        assert Decimal(str(data["percentage"])) == Decimal("80.00")
        assert data["is_passed"] is True
        assert data["total_questions"] == 5
        assert data["answered_questions"] == 5
        assert data["correct_questions"] == 4
        assert data["incorrect_questions"] == 1
        assert data["skipped_questions"] == 0

        # Student identification
        student_data = data["student"]
        assert str(student_data["id"]) == str(setup["student"].id)
        assert student_data["email"] == setup["student"].email
        assert student_data["official_name"] == "Student Official Name"
        assert student_data["roll_number"] == "ROLL-REV-101"
        assert student_data["euid"] == "EUID-REV-101"

        # Questions array
        assert len(data["questions"]) == 5

    def test_02_student_receives_403(self, api_client, student_user, full_assessment_setup):
        """Student receives HTTP 403 Forbidden on the admin answer review endpoint."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=student_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_03_unauthenticated_and_proctor_forbidden(self, api_client, proctor_user, full_assessment_setup):
        """Unauthenticated returns 401 and Proctor receives 403."""
        setup = full_assessment_setup
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        # Unauthenticated
        api_client.logout()
        resp_anon = api_client.get(url)
        assert resp_anon.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Proctor
        api_client.force_authenticate(user=proctor_user)
        resp_proc = api_client.get(url)
        assert resp_proc.status_code == status.HTTP_403_FORBIDDEN

    def test_04_assessment_mismatch_returns_404(self, api_client, admin_user, full_assessment_setup):
        """IDOR Prevention: Mismatch between assessment_id and result_id returns HTTP 404."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)

        # Create Assessment B
        other_assessment = Assessment.objects.create(
            title="Assessment B",
            description="Separate assessment",
            duration_minutes=30,
            total_points=10,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=timezone.now() - timedelta(hours=1),
            end_datetime=timezone.now() + timedelta(hours=2),
            created_by=admin_user
        )

        # Assessment A url + Result from Assessment B -> 404
        mismatch_url = f"/api/v1/admin/assessments/{other_assessment.id}/results/{setup['result'].id}/"
        response = api_client.get(mismatch_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Random UUID assessment -> 404
        from uuid import uuid4
        fake_url = f"/api/v1/admin/assessments/{uuid4()}/results/{setup['result'].id}/"
        response = api_client.get(fake_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_05_student_answer_is_returned(self, api_client, admin_user, full_assessment_setup):
        """Student responses for various question types are returned accurately."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        questions = response.data.get("data", response.data)["questions"]

        # Q1 MCQ
        q1 = questions[0]
        assert q1["student_answer"]["selected_options"] == ["opt_2"]
        assert q1["student_answer"]["is_answered"] is True

        # Q2 MULTI_SELECT
        q2 = questions[1]
        assert set(q2["student_answer"]["selected_options"]) == {"opt_m1", "opt_m3"}

        # Q3 SHORT_ANSWER
        q3 = questions[2]
        assert q3["student_answer"]["text_response"] == "def"

        # Q4 CODING
        q4 = questions[3]
        assert "print(a + b)" in q4["student_answer"]["code_response"]

        # Q5 SQL
        q5 = questions[4]
        assert "SELECT * FROM users" in q5["student_answer"]["sql_response"]

    def test_06_correct_answer_is_returned(self, api_client, admin_user, full_assessment_setup):
        """Correct answers are returned with option markers and matching criteria."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        questions = response.data.get("data", response.data)["questions"]

        # Q1 MCQ options
        q1 = questions[0]
        options_q1 = q1["correct_answer"]["options"]
        opt_2 = next(opt for opt in options_q1 if opt["id"] == "opt_2")
        assert opt_2["is_correct"] is True
        assert opt_2["is_selected"] is True
        opt_1 = next(opt for opt in options_q1 if opt["id"] == "opt_1")
        assert opt_1["is_correct"] is False
        assert opt_1["is_selected"] is False

        # Q2 MULTI_SELECT
        q2 = questions[1]
        options_q2 = q2["correct_answer"]["options"]
        opt_m3 = next(opt for opt in options_q2 if opt["id"] == "opt_m3")
        assert opt_m3["is_correct"] is False
        assert opt_m3["is_selected"] is True  # Student selected incorrect option

        # Q3 SHORT_ANSWER
        q3 = questions[2]
        assert "def" in q3["correct_answer"]["exact_matches"]
        assert q3["correct_answer"]["case_sensitive"] is False

        # Q5 SQL
        q5 = questions[4]
        assert "SELECT * FROM users WHERE is_active = TRUE;" in q5["correct_answer"]["expected_result_definition"]

    def test_07_question_marks_are_returned(self, api_client, admin_user, full_assessment_setup):
        """Authoritative points, earned_points, and marks are returned."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        questions = response.data.get("data", response.data)["questions"]

        q1 = questions[0]
        assert Decimal(q1["points"]) == Decimal("10.00")
        assert Decimal(q1["earned_points"]) == Decimal("10.00")
        assert Decimal(q1["max_points"]) == Decimal("10.00")
        assert q1["is_correct"] is True
        assert q1["is_skipped"] is False

        q2 = questions[1]
        assert Decimal(q2["earned_points"]) == Decimal("0.00")
        assert q2["is_correct"] is False

    def test_08_snapshot_question_data_used(self, api_client, admin_user, full_assessment_setup):
        """Historical integrity: new versions or bank changes do not affect snapshot review."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)

        # Create a v2 of the question in the question bank with different content
        QuestionVersion.objects.create(
            question=setup["q_mcq"],
            version_number=2,
            status=VersionStatus.PUBLISHED,
            question_type=QuestionType.MCQ,
            title="NEW V2 TITLE IN QUESTION BANK",
            description="New description",
            difficulty="HARD",
            type_config={
                "options": [{"id": "opt_99", "text": "Different"}],
                "correct_options": ["opt_99"]
            },
            created_by=admin_user
        )

        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"
        response = api_client.get(url)
        q1 = response.data.get("data", response.data)["questions"][0]

        # Snapshot data remains preserved
        assert q1["title"] == "What is the output of 2 + 2 in Python?"
        assert any(opt["id"] == "opt_2" for opt in q1["correct_answer"]["options"])

    def test_09_raw_server_evaluation_bundle_never_returned(self, api_client, admin_user, full_assessment_setup):
        """Raw server_evaluation_bundle must NEVER be leaked in the response."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        data = response.data.get("data", response.data)

        assert "server_evaluation_bundle" not in data
        for q in data["questions"]:
            assert "server_evaluation_bundle" not in q
            assert "server_coding_eval" not in q
            assert "server_sql_eval" not in q

    def test_10_hidden_coding_test_case_internals_never_exposed(self, api_client, admin_user, full_assessment_setup):
        """Hidden test cases never expose input, expected output, or actual output."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        questions = response.data.get("data", response.data)["questions"]
        q_code = next(q for q in questions if q["question_type"] == "CODING")

        # In correct_answer test_cases summary:
        for tc in q_code["correct_answer"].get("test_cases", []):
            if tc["is_hidden"]:
                assert "input_data" not in tc
                assert "expected_output" not in tc

        # In code_submission test_cases results:
        submission = q_code["code_submission"]
        for tc in submission["test_cases"]:
            if tc["is_hidden"]:
                assert "public_input" not in tc
                assert "expected_output" not in tc
                assert "actual_output" not in tc
                assert "error_message" not in tc
            else:
                # Public test case can have safe data
                assert tc["public_input"] == "2 3\n"
                assert tc["expected_output"] == "5\n"

    def test_11_coding_submission_details_returned(self, api_client, admin_user, full_assessment_setup):
        """Authoritative code submission details are present."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        response = api_client.get(url)
        questions = response.data.get("data", response.data)["questions"]
        q_code = next(q for q in questions if q["question_type"] == "CODING")

        sub = q_code["code_submission"]
        assert sub is not None
        assert sub["language"] == "PYTHON"
        assert sub["verdict"] == "ACCEPTED"
        assert sub["passed_test_cases"] == 2
        assert sub["total_test_cases"] == 2
        assert len(sub["test_cases"]) == 2

    def test_12_query_count_stays_bounded(self, api_client, admin_user, full_assessment_setup):
        """Query count for full result review remains bounded to target (<= 7 queries)."""
        setup = full_assessment_setup
        api_client.force_authenticate(user=admin_user)
        url = f"/api/v1/admin/assessments/{setup['assessment'].id}/results/{setup['result'].id}/"

        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK

        query_count = len(queries)
        # Verify query count is bounded and well within the target range (no per-question N+1)
        assert query_count <= 7, f"Expected <= 7 queries, got {query_count}: {[q['sql'] for q in queries]}"

    def test_13_existing_student_result_endpoint_remains_sanitized(self, api_client, student_user, full_assessment_setup):
        """Existing student result endpoint must NOT leak correct answers or options keys."""
        from apps.assessments.models import ResultVisibility
        setup = full_assessment_setup
        api_client.force_authenticate(user=student_user)

        # Allow student view by setting visibility to IMMEDIATE and releasing
        Assessment.objects.filter(pk=setup["assessment"].pk).update(result_visibility=ResultVisibility.IMMEDIATE)
        AssessmentResult.objects.filter(pk=setup["result"].pk).update(is_released=True)
        setup["result"].refresh_from_db()

        url = f"/api/v1/student/attempts/{setup['attempt'].id}/result/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data.get("data", response.data)
        assert "server_evaluation_bundle" not in data
        assert "server_eval" not in str(data)

        # If question_results present, ensure no 'correct_options' or answer keys
        if "question_results" in data:
            for qr in data["question_results"]:
                assert "correct_answer" not in qr
                assert "correct_options" not in qr
