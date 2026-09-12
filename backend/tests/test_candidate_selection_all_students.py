import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, Section
from apps.accounts.services import StudentService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    ResultVisibility,
)
from apps.assessments.services import (
    AssessmentService,
    AssessmentAudienceService,
    resolve_student_users,
)
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    VersionStatus,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="society_admin@craftsociety.test",
        password="AdminPassword123!",
        role=Role.ADMIN,
        display_name="Society Admin",
    )


@pytest.fixture
def student_population(db, admin_user):
    """
    Creates a diverse student population in Craft Society:
    - 5 active students in various sections
    - 3 active students without any section
    - 2 inactive/deactivated students
    Total = 10 students
    """
    sec1 = Section.objects.create(code="SEC-A", name="Section A", is_active=True)
    sec2 = Section.objects.create(code="SEC-B", name="Section B", is_active=True)

    students = []
    # 5 students with sections
    for i in range(1, 6):
        sec = sec1 if i <= 3 else sec2
        s, _ = StudentService.create_student(
            email=f"student{i}@craftsociety.test",
            roll_number=f"CS-2026-00{i}",
            section=sec,
            actor=admin_user,
        )
        students.append(s)

    # 3 students without section
    for i in range(6, 9):
        s, _ = StudentService.create_student(
            email=f"student{i}@craftsociety.test",
            roll_number=f"CS-2026-00{i}",
            section=None,
            actor=admin_user,
        )
        students.append(s)

    # 2 inactive students (one with section, one without)
    s9, _ = StudentService.create_student(
        email="student9@craftsociety.test",
        roll_number="CS-2026-009",
        section=sec1,
        actor=admin_user,
    )
    s9.is_active = False
    s9.save(update_fields=["is_active"])
    students.append(s9)

    s10, _ = StudentService.create_student(
        email="student10@craftsociety.test",
        roll_number="CS-2026-010",
        section=None,
        actor=admin_user,
    )
    s10.is_active = False
    s10.save(update_fields=["is_active"])
    students.append(s10)

    return students


@pytest.fixture
def draft_exam(db, admin_user):
    now = timezone.now()
    exam = Assessment.objects.create(
        title="Craft Society Annual Assessment",
        description="Comprehensive assessment for all members",
        created_by=admin_user,
        status=AssessmentStatus.DRAFT,
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=3),
        duration_minutes=60,
        total_points=10,
        passing_percentage=50.00,
        attempt_limit=1,
        result_visibility=ResultVisibility.AFTER_DEADLINE,
    )

    # Add 1 published question worth 10 points
    q = Question.objects.create(created_by=admin_user)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="Sample Question",
        question_type=QuestionType.MCQ,
        description="What is the result of 2 + 2?",
        status=VersionStatus.PUBLISHED,
        points=10,
        created_by=admin_user,
    )
    AssessmentService.add_question(
        assessment=exam,
        question_version=qv,
        actor=admin_user,
        points=10,
    )
    return exam


@pytest.mark.django_db
class TestCandidateSelectionAllStudents:
    def test_all_students_targets_complete_craft_society_population(
        self, draft_exam, student_population, admin_user
    ):
        """
        'All Students' must target every student in Craft Society (10 total),
        including inactive students and students without any section.
        """
        total_students = User.objects.filter(role=Role.STUDENT).count()
        assert total_students == 10

        res = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            target_all_students=True,
            actor=admin_user,
        )

        assert res["total_eligible"] == 10
        assert res["target_all_students"] is True
        assert res["audience_mode"] == "ALL_STUDENTS"
        assert len(res["eligible_student_ids"]) == 10

        # Verify all student IDs are included
        all_ids = set(str(s.id) for s in student_population)
        assert set(res["eligible_student_ids"]) == all_ids

    def test_all_students_does_not_filter_active_only(
        self, draft_exam, student_population, admin_user
    ):
        """
        Inactive students are explicitly included under 'All Students'.
        """
        inactive_ids = [str(s.id) for s in student_population if not s.is_active]
        assert len(inactive_ids) == 2

        res = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            target_all_students=True,
            actor=admin_user,
        )

        for inact_id in inactive_ids:
            assert inact_id in res["eligible_student_ids"]

    def test_all_students_includes_students_outside_selected_candidates(
        self, draft_exam, student_population, admin_user
    ):
        """
        Switching from specific candidates to All Students overrides the selection
        and targets the full population.
        """
        # First configure only 2 specific students
        selected_2 = [str(student_population[0].id), str(student_population[1].id)]
        res_specific = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            student_ids=selected_2,
            target_all_students=False,
            actor=admin_user,
        )
        assert res_specific["total_eligible"] == 2
        assert res_specific["audience_mode"] == "SPECIFIC"

        # Now configure All Students
        res_all = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            target_all_students=True,
            actor=admin_user,
        )
        assert res_all["total_eligible"] == 10
        assert res_all["audience_mode"] == "ALL_STUDENTS"

        # All other 8 students outside the 2 previously selected are included
        for s in student_population:
            assert str(s.id) in res_all["eligible_student_ids"]

    def test_selected_candidates_only_targets_only_explicit_candidates(
        self, draft_exam, student_population, admin_user
    ):
        """
        'Selected Candidates Only' mode targets strictly the selected students.
        """
        selected_subset = [student_population[0], student_population[4], student_population[7]]
        selected_ids = [str(s.id) for s in selected_subset]

        res = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            student_ids=selected_ids,
            target_all_students=False,
            actor=admin_user,
        )

        assert res["total_eligible"] == 3
        assert res["audience_mode"] == "SPECIFIC"
        assert set(res["eligible_student_ids"]) == set(selected_ids)

        # Non-selected students are NOT eligible
        unselected_ids = set(str(s.id) for s in student_population) - set(selected_ids)
        for uid in unselected_ids:
            assert uid not in res["eligible_student_ids"]

    def test_publishing_with_all_students_creates_assignments_idempotently(
        self, draft_exam, student_population, admin_user
    ):
        """
        When published, all 10 students receive AssessmentAssignment records.
        Repeated calls remain idempotent.
        """
        AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            target_all_students=True,
            actor=admin_user,
        )

        published = AssessmentService.publish_assessment(
            assessment=draft_exam,
            actor=admin_user,
        )
        assert published.status == AssessmentStatus.PUBLISHED

        assignments = AssessmentAssignment.objects.filter(assessment=published, status=AssignmentStatus.ASSIGNED)
        assert assignments.count() == 10

        assigned_user_ids = set(str(a.student_id) for a in assignments)
        all_student_ids = set(str(s.id) for s in student_population)
        assert assigned_user_ids == all_student_ids

        # Assign again — idempotent
        AssessmentService.assign_students(
            assessment=published,
            student_ids=list(all_student_ids),
            actor=admin_user,
        )
        assert AssessmentAssignment.objects.filter(assessment=published, status=AssignmentStatus.ASSIGNED).count() == 10

    def test_audience_preview_api_returns_all_students(
        self, draft_exam, student_population, admin_user
    ):
        """
        API POST /api/v1/admin/assessments/<id>/audience/preview/
        returns all students when target_all_students=True.
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/audience/preview/",
            {"target_all_students": True},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert data["total_eligible"] == 10
        assert data["target_all_students"] is True
        assert data["audience_mode"] == "ALL_STUDENTS"
        assert len(data["eligible_student_ids"]) == 10

    def test_audience_configure_api_persists_all_students(
        self, draft_exam, student_population, admin_user
    ):
        """
        API POST /api/v1/admin/assessments/<id>/audience/
        persists All Students targeting.
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/audience/",
            {"target_all_students": True},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert data["total_eligible"] == 10
        assert data["target_all_students"] is True
        assert data["audience_mode"] == "ALL_STUDENTS"

        # GET check
        get_res = client.get(f"/api/v1/admin/assessments/{draft_exam.id}/audience/")
        assert get_res.status_code == status.HTTP_200_OK
        get_data = get_res.json()["data"]
        assert get_data["total_eligible"] == 10
        assert get_data["target_all_students"] is True
        assert get_data["audience_mode"] == "ALL_STUDENTS"

    def test_assessment_patch_with_target_all_students_publishes_all_assignments(
        self, draft_exam, student_population, admin_user
    ):
        """
        When editor saves draft via PATCH with target_all_students=True,
        publishing creates assignments for ALL canonical eligible students (10).
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        # Editor saves draft with target_all_students=True
        patch_res = client.patch(
            f"/api/v1/admin/assessments/{draft_exam.id}/",
            {"target_all_students": True, "target_student_ids": []},
            format="json",
        )
        assert patch_res.status_code == status.HTTP_200_OK

        # Publish assessment
        pub_res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/publish/",
            format="json",
        )
        assert pub_res.status_code == status.HTTP_200_OK

        # Verify all 10 assignments created
        assignments = AssessmentAssignment.objects.filter(assessment=draft_exam, status=AssignmentStatus.ASSIGNED)
        assert assignments.count() == 10
        assigned_user_ids = set(str(a.student_id) for a in assignments)
        all_student_ids = set(str(s.id) for s in student_population)
        assert assigned_user_ids == all_student_ids

    def test_assessment_patch_with_specific_students_publishes_only_selected(
        self, draft_exam, student_population, admin_user
    ):
        """
        When editor saves draft via PATCH with target_all_students=False and specific IDs,
        publishing creates assignments strictly for selected students (2).
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        selected_ids = [str(student_population[0].id), str(student_population[1].id)]
        patch_res = client.patch(
            f"/api/v1/admin/assessments/{draft_exam.id}/",
            {"target_all_students": False, "target_student_ids": selected_ids},
            format="json",
        )
        assert patch_res.status_code == status.HTTP_200_OK

        # Publish assessment
        pub_res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/publish/",
            format="json",
        )
        assert pub_res.status_code == status.HTTP_200_OK

        # Verify strictly 2 assignments created
        assignments = AssessmentAssignment.objects.filter(assessment=draft_exam, status=AssignmentStatus.ASSIGNED)
        assert assignments.count() == 2
        assigned_user_ids = set(str(a.student_id) for a in assignments)
        assert assigned_user_ids == set(selected_ids)

    def test_ineligible_orphan_student_excluded_consistently_from_all_students_and_picker(
        self, draft_exam, student_population, admin_user
    ):
        """
        Critical check: An orphan User with role=STUDENT but missing StudentProfile
        must be excluded from BOTH All Students and the candidate picker.
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        # Create an orphan student user without StudentProfile (mimics test_student_exp@test.com)
        orphan_user = User.objects.create_user(
            email="orphan_no_profile@craftsociety.test",
            password="Password123!",
            role=Role.STUDENT,
            is_active=False
        )
        assert not hasattr(orphan_user, 'student_profile') or orphan_user.student_profile is None

        # 1. Check Canonical Querysets
        canonical_profiles_count = StudentService.get_canonical_students_queryset(active_only=False).count()
        canonical_users_count = StudentService.get_canonical_student_users_queryset(active_only=False).count()
        assert canonical_profiles_count == 10  # from student_population fixture
        assert canonical_users_count == 10
        assert orphan_user.id not in StudentService.get_canonical_student_users_queryset(active_only=False).values_list('id', flat=True)

        # 2. Check Candidate Picker endpoint (GET /api/v1/admin/students/)
        picker_res = client.get("/api/v1/admin/students/?page_size=100")
        assert picker_res.status_code == status.HTTP_200_OK
        picker_results = picker_res.json()["data"]["results"]
        assert len(picker_results) == 10
        picker_emails = [r["email"] for r in picker_results]
        assert "orphan_no_profile@craftsociety.test" not in picker_emails

        # 3. Check All Students Preview (POST /api/v1/admin/assessments/<id>/audience/preview/)
        preview_res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/audience/preview/",
            {"target_all_students": True, "target_student_ids": [], "target_section_ids": []},
            format="json",
        )
        assert preview_res.status_code == status.HTTP_200_OK
        preview_data = preview_res.json()["data"]
        assert preview_data["total_eligible"] == 10
        assert preview_data["total_craft_society_students"] == 10
        assert preview_data["all_students_count"] == 10
        assert str(orphan_user.id) not in preview_data["eligible_student_ids"]

        # 4. Check All Students Configuration (POST /api/v1/admin/assessments/<id>/audience/)
        config_res = client.post(
            f"/api/v1/admin/assessments/{draft_exam.id}/audience/",
            {"target_all_students": True, "student_ids": [], "section_ids": []},
            format="json",
        )
        assert config_res.status_code == status.HTTP_200_OK
        config_data = config_res.json()["data"]
        assert config_data["total_eligible"] == 10
        assert config_data["all_students_count"] == 10
        assert str(orphan_user.id) not in config_data["eligible_student_ids"]

        # 5. Check GET Assessment Audience (GET /api/v1/admin/assessments/<id>/audience/)
        get_res = client.get(f"/api/v1/admin/assessments/{draft_exam.id}/audience/")
        assert get_res.status_code == status.HTTP_200_OK
        assert get_res.json()["data"]["total_eligible"] == 10

        # 6. Verify that resolve_student_users rejects orphan user
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError):
            resolve_student_users([str(orphan_user.id)])

    def test_administrators_are_not_counted_as_students(
        self, draft_exam, student_population, admin_user
    ):
        """
        Critical check: Administrator accounts must never be counted in student audience.
        """
        # Create additional admin
        extra_admin = User.objects.create_user(
            email="another_admin@craftsociety.test",
            password="AdminPassword123!",
            role=Role.ADMIN,
            display_name="Another Admin",
            is_staff=True
        )

        res = AssessmentAudienceService.configure_audience(
            assessment=draft_exam,
            target_all_students=True,
            actor=admin_user,
        )

        assert res["total_eligible"] == 10
        assert str(admin_user.id) not in res["eligible_student_ids"]
        assert str(extra_admin.id) not in res["eligible_student_ids"]

        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError):
            resolve_student_users([str(extra_admin.id)])

    def test_duplicate_coin_joins_cannot_inflate_canonical_student_count(
        self, draft_exam, student_population, admin_user
    ):
        """
        Critical check: Multiple related coin ledger entries must never inflate student counts.
        """
        from apps.results.models import StudentCoinLedger
        from apps.assessments.models import AssessmentSnapshot, TestAttempt

        target_student = student_population[0]
        snapshot = AssessmentSnapshot.objects.create(
            assessment=draft_exam,
            version_number=1,
            snapshot_data={"title": draft_exam.title},
            server_evaluation_bundle={}
        )
        attempt = TestAttempt.objects.create(
            assessment=draft_exam,
            assessment_snapshot=snapshot,
            student=target_student,
            attempt_number=1
        )
        StudentCoinLedger.objects.create(
            student=target_student,
            attempt=attempt,
            question_id="q_coin_1",
            coins_awarded=3
        )
        StudentCoinLedger.objects.create(
            student=target_student,
            attempt=attempt,
            question_id="q_coin_2",
            coins_awarded=3
        )

        # Count must remain exactly 10
        profiles_qs = StudentService.get_canonical_students_queryset(active_only=False)
        assert profiles_qs.count() == 10
        users_qs = StudentService.get_canonical_student_users_queryset(active_only=False)
        assert users_qs.count() == 10

        res = AssessmentAudienceService.configure_audience(assessment=draft_exam, target_all_students=True, actor=admin_user)
        assert res["total_craft_society_students"] == 10
        assert res["total_eligible"] == 10
