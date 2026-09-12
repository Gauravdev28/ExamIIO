import uuid
import pytest
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError as DRFValidationError

from datetime import timedelta
from django.utils import timezone
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
from apps.questions.services import QuestionService
from apps.questions.serializers import QuestionVersionAdminDetailSerializer
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    AttemptAnswer,
    AssessmentStatus,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_lifecycle@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN,
    )


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.mark.django_db
class TestQuestionBankLifecycle:
    """
    Comprehensive tests for the simplified Question Bank lifecycle:
    DRAFT -> PUBLISHED
    """

    # =========================================================================
    # A. CREATE & DRAFT
    # =========================================================================

    def test_01_create_question_creates_question_and_v1_in_draft(self, admin_user):
        """1. create_question creates Question and v1 in DRAFT."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Initial Question Title",
            description="Initial description",
            points=5,
            difficulty=Difficulty.MEDIUM,
            type_config={
                "options": [
                    {"id": "A", "text": "Option 1", "is_correct": True},
                    {"id": "B", "text": "Option 2", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        assert q is not None
        assert v1 is not None
        assert q.status == "ACTIVE"
        assert v1.status == VersionStatus.DRAFT
        assert v1.version_number == 1
        assert v1.title == "Initial Question Title"
        assert q.versions.count() == 1

    def test_02_saving_incomplete_draft_succeeds_and_remains_draft(self, admin_user):
        """2. Saving incomplete draft (blank title/statement/options) succeeds and remains DRAFT."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="",  # blank title
            description="",  # blank description
            points=1,
            difficulty=Difficulty.EASY,
            type_config={"options": []},
            actor=admin_user,
        )
        assert q.status == "ACTIVE"
        assert v1.status == VersionStatus.DRAFT
        assert v1.title == "Untitled Question"
        assert v1.version_number == 1

    def test_03_multiple_successive_draft_saves_update_v1_without_creating_new_versions(self, admin_user):
        """3. Multiple successive draft saves update v1 without creating new versions (version_number remains 1)."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Draft v1",
            description="Draft desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={"options": []},
            actor=admin_user,
        )
        assert q.versions.count() == 1
        assert v1.version_number == 1

        # First edit
        v1_updated = QuestionService.update_draft_version(v1, title="Draft v1 Edited Once", actor=admin_user)
        assert v1_updated.id == v1.id
        assert v1_updated.version_number == 1
        assert q.versions.count() == 1

        # Second edit
        v1_updated_2 = QuestionService.update_draft_version(v1_updated, title="Draft v1 Edited Twice", actor=admin_user)
        assert v1_updated_2.id == v1.id
        assert v1_updated_2.version_number == 1
        assert q.versions.count() == 1
        assert v1_updated_2.title == "Draft v1 Edited Twice"

    def test_04_draft_question_is_editable_via_api(self, api_client, admin_user):
        """4. Draft question is editable via API (PATCH/PUT)."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="API Draft",
            description="API desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Option 1", "is_correct": True},
                ]
            },
            actor=admin_user,
        )
        url = reverse("questions:admin-question-version-detail", kwargs={"pk": q.id, "version_number": 1})
        resp = api_client.patch(url, {
            "title": "API Draft Updated",
            "points": 10,
        }, format="json")
        assert resp.status_code == 200
        v1.refresh_from_db()
        assert v1.title == "API Draft Updated"
        assert v1.points == 10

    def test_05_draft_question_can_be_deleted_via_delete(self, api_client, admin_user):
        """5. Draft question can be deleted via DELETE."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Draft To Delete",
            description="To be deleted",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={"options": []},
            actor=admin_user,
        )
        url = reverse("questions:admin-question-detail", kwargs={"pk": q.id})
        resp = api_client.delete(url)
        assert resp.status_code == 200
        assert not Question.objects.filter(id=q.id).exists()
        assert not QuestionVersion.objects.filter(id=v1.id).exists()

    def test_06_draft_question_detail_serializer_flags(self, admin_user):
        """6. Draft question detail serializer returns is_editable=True, is_deletable=True."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Draft Serializer Check",
            description="Checking flags",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        data = QuestionVersionAdminDetailSerializer(v1).data
        assert data["is_editable"] is True
        assert data["is_deletable"] is True
        assert data["status"] == VersionStatus.DRAFT

    # =========================================================================
    # B. PUBLISH
    # =========================================================================

    def test_07_publishing_draft_with_valid_data_changes_status_to_published(self, admin_user):
        """7. Publishing draft with valid data changes status to PUBLISHED."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Valid Question To Publish",
            description="Good statement",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        published_v = QuestionService.publish_version(v1, actor=admin_user)
        assert published_v.status == VersionStatus.PUBLISHED
        q.refresh_from_db()
        assert q.status == "ACTIVE"

    def test_08_publishing_draft_with_invalid_data_fails_validation(self, admin_user):
        """8. Publishing draft with invalid/incomplete data (e.g. missing correct option) fails validation."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Incomplete MCQ",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": False},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        with pytest.raises(DRFValidationError):
            QuestionService.publish_version(v1, actor=admin_user)
        v1.refresh_from_db()
        assert v1.status == VersionStatus.DRAFT

    def test_09_published_question_is_permanently_immutable(self, admin_user):
        """9. Published question is permanently immutable: direct updates fail with PermissionDenied."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Immutable Published Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)
        v1.refresh_from_db()
        assert v1.status == VersionStatus.PUBLISHED

        # Direct model update blocked
        v1.title = "Attempted Model Update"
        with pytest.raises(PermissionDenied):
            v1.save()

        # Service update blocked
        with pytest.raises(PermissionDenied):
            QuestionService.update_draft_version(v1, title="Attempted Service Update", actor=admin_user)

    def test_10_published_question_detail_serializer_returns_not_editable(self, admin_user):
        """10. Published question detail serializer returns is_editable=False."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Published Serializer Check",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)
        v1.refresh_from_db()
        data = QuestionVersionAdminDetailSerializer(v1).data
        assert data["is_editable"] is False
        assert data["status"] == VersionStatus.PUBLISHED

    # =========================================================================
    # C. NO VERSION BRANCHING
    # =========================================================================

    def test_11_cannot_create_new_version_from_published(self, admin_user):
        """11. Attempting to create another draft version from a published question fails with ValidationError."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="No Branching Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        with pytest.raises(DRFValidationError) as exc:
            QuestionService.get_or_create_draft_version(q, actor=admin_user)
        assert "immutable" in str(exc.value).lower()
        assert q.versions.count() == 1

    def test_12_version_creation_api_rejected(self, api_client, admin_user):
        """12. POST to /api/v1/admin/questions/{id}/versions/ fails with 400 Bad Request if question has a published version."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="API No Branching",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        url = reverse("questions:admin-question-version-list", kwargs={"pk": q.id})
        resp = api_client.post(url, {})
        assert resp.status_code == 400
        assert "immutable" in str(resp.json()).lower()

    def test_13_admin_question_list_and_detail_do_not_expose_branching_actions(self, api_client, admin_user):
        """13. Admin question list & detail responses do NOT expose branching actions."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="List Check Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        detail_url = reverse("questions:admin-question-version-detail", kwargs={"pk": q.id, "version_number": 1})
        resp = api_client.get(detail_url)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "create_new_version" not in data
        assert "can_branch" not in data
        assert data["is_editable"] is False

    # =========================================================================
    # D. DUPLICATE
    # =========================================================================

    def test_14_duplicate_creates_completely_new_question(self, api_client, admin_user):
        """14. POST /api/v1/admin/questions/{id}/duplicate/ creates completely NEW Question with new UUID."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Original Question",
            description="Original description",
            points=5,
            difficulty=Difficulty.MEDIUM,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt 1", "is_correct": True},
                    {"id": "B", "text": "Opt 2", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        url = reverse("questions:admin-question-duplicate", kwargs={"pk": q.id})
        resp = api_client.post(url)
        assert resp.status_code == 201
        data = resp.json()["data"]
        new_q_id = data["question_id"]
        assert new_q_id != str(q.id)
        assert Question.objects.filter(id=new_q_id).exists()

    def test_15_duplicated_question_has_v1_draft_and_copy_title(self, api_client, admin_user):
        """15. The duplicated question has version 1 in DRAFT status, with title '${original_title} (Copy)'."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Source Question",
            description="Source description",
            points=5,
            difficulty=Difficulty.MEDIUM,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt 1", "is_correct": True},
                    {"id": "B", "text": "Opt 2", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        url = reverse("questions:admin-question-duplicate", kwargs={"pk": q.id})
        resp = api_client.post(url)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["version_number"] == 1
        assert data["status"] == VersionStatus.DRAFT
        assert data["title"] == "Source Question (Copy)"

    def test_16_duplicated_question_copies_all_configs_and_test_cases(self, admin_user):
        """16. The duplicated question copies all options, test cases, configs, and tags correctly."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Two Sum Problem",
            description="Find two numbers",
            points=10,
            difficulty=Difficulty.HARD,
            tags=["algorithms", "arrays"],
            type_config={
                "allowed_languages": ["PYTHON", "CPP"],
                "default_language": "PYTHON",
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
                "starter_code": {"PYTHON": "def twoSum(nums, target): pass"},
                "solution_template": "def twoSum(nums, target): return []",
                "test_cases": [
                    {"input": "[2,7,11,15], 9", "expected_output": "[0,1]", "is_hidden": False, "points": 5},
                    {"input": "[3,2,4], 6", "expected_output": "[1,2]", "is_hidden": True, "points": 5},
                ],
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        new_q, new_v = QuestionService.duplicate_question(q, actor=admin_user)
        assert new_q.id != q.id
        assert new_v.coding_config is not None
        assert new_v.coding_config.allowed_languages == ["PYTHON", "CPP"]
        assert new_v.coding_config.time_limit_ms == 2000
        assert new_v.coding_config.test_cases.count() == 2
        assert set(new_v.tags.values_list("name", flat=True)) == {"algorithms", "arrays"}

    def test_17_duplicated_question_is_editable_without_affecting_original(self, admin_user):
        """17. The duplicated question is fully editable and its edits do NOT affect the original published question."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Original Immutable",
            description="Original statement",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        new_q, new_v = QuestionService.duplicate_question(q, actor=admin_user)
        QuestionService.update_draft_version(new_v, title="Modified Copy Title", points=20, actor=admin_user)

        new_v.refresh_from_db()
        v1.refresh_from_db()
        assert new_v.title == "Modified Copy Title"
        assert new_v.points == 20
        assert v1.title == "Original Immutable"
        assert v1.points == 5
        assert v1.status == VersionStatus.PUBLISHED

    # =========================================================================
    # E. DELETE
    # =========================================================================

    def test_18_hard_delete_unused_published_question_succeeds(self, api_client, admin_user):
        """18. Hard deleting an UNUSED published question succeeds (removes Question, versions, and configs from DB)."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Unused Published Question",
            description="Never used",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        # Check usage
        usage = QuestionService.get_question_usage(q)
        assert usage["is_deletable"] is True
        assert usage["assessment_count"] == 0

        url = reverse("questions:admin-question-detail", kwargs={"pk": q.id})
        resp = api_client.delete(url)
        assert resp.status_code == 200
        assert not Question.objects.filter(id=q.id).exists()
        assert not QuestionVersion.objects.filter(id=v1.id).exists()

    def test_19_hard_delete_unused_draft_question_succeeds(self, api_client, admin_user):
        """19. Hard deleting an UNUSED draft question succeeds."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Unused Draft Question",
            description="Draft",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={"options": []},
            actor=admin_user,
        )
        url = reverse("questions:admin-question-detail", kwargs={"pk": q.id})
        resp = api_client.delete(url)
        assert resp.status_code == 200
        assert not Question.objects.filter(id=q.id).exists()

    def test_20_delete_used_question_fails_with_clear_message(self, api_client, admin_user):
        """20. Attempting to delete a question used in an active assessment fails with exact message."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Used In Assessment",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        now = timezone.now()
        ass = Assessment.objects.create(
            title="Midterm Exam 2026",
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=2),
            passing_percentage=50.0,
            created_by=admin_user,
            status=AssessmentStatus.DRAFT,
        )
        AssessmentQuestion.objects.create(assessment=ass, question_version=v1, order=1, points=5)
        ass.status = AssessmentStatus.PUBLISHED
        ass.save()

        url = reverse("questions:admin-question-detail", kwargs={"pk": q.id})
        resp = api_client.delete(url)
        assert resp.status_code == 400
        data = resp.json()
        assert "Cannot delete this question because it is used in 1 assessment" in data["error"]["message"]

    def test_21_usage_endpoint_returns_using_assessments(self, api_client, admin_user):
        """21. Usage endpoint returns is_deletable=False and lists the assessments using it."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Usage Check Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        now = timezone.now()
        ass = Assessment.objects.create(
            title="Final Exam 2026",
            duration_minutes=90,
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=2),
            passing_percentage=60.0,
            created_by=admin_user,
            status=AssessmentStatus.DRAFT,
        )
        AssessmentQuestion.objects.create(assessment=ass, question_version=v1, order=1, points=5)
        ass.status = AssessmentStatus.PUBLISHED
        ass.save()

        usage_url = reverse("questions:admin-question-usage", kwargs={"pk": q.id})
        resp = api_client.get(usage_url)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_deletable"] is False
        assert data["assessment_count"] == 1
        assert len(data["assessments"]) == 1
        assert data["assessments"][0]["title"] == "Final Exam 2026"
        assert "Cannot delete this question because it is used in 1 assessment" in data["reason_blocked"]

    def test_22_delete_fails_if_referenced_in_snapshot_or_attempt(self, api_client, admin_user):
        """22. Attempting to delete a question referenced in an AssessmentSnapshot or AttemptAnswer fails."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Snapshot Reference Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        now = timezone.now()
        ass = Assessment.objects.create(
            title="Snapshot Assessment",
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=2),
            passing_percentage=50.0,
            created_by=admin_user,
            status=AssessmentStatus.PUBLISHED,
        )
        snap = AssessmentSnapshot.objects.create(
            assessment=ass,
            version_number=1,
            snapshot_data={"questions": []},
        )
        AssessmentSnapshotQuestion.objects.create(
            snapshot=snap,
            question_version=v1,
            order=1,
            points=5,
        )

        url = reverse("questions:admin-question-detail", kwargs={"pk": q.id})
        resp = api_client.delete(url)
        assert resp.status_code == 400
        assert "snapshot" in resp.json()["error"]["message"].lower()

    # =========================================================================
    # F. ARCHIVE
    # =========================================================================

    def test_23_question_bank_list_filters_published_and_draft(self, api_client, admin_user):
        """23. Question Bank list API supports ALL, PUBLISHED, DRAFT filters."""
        # Create 1 draft
        q1, _ = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Draft Filter Test",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={"options": []},
            actor=admin_user,
        )
        # Create 1 published
        q2, v2 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Published Filter Test",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v2, actor=admin_user)

        list_url = reverse("questions:admin-question-list")

        # Test ALL
        resp_all = api_client.get(list_url)
        assert resp_all.status_code == 200

        # Test PUBLISHED
        resp_pub = api_client.get(list_url, {"version_status": "PUBLISHED"})
        assert resp_pub.status_code == 200
        results_pub = resp_pub.json()["data"]["results"]
        pub_titles = [item["latest_version"]["title"] for item in results_pub if item.get("latest_version")]
        assert "Published Filter Test" in pub_titles
        assert "Draft Filter Test" not in pub_titles

        # Test DRAFT
        resp_draft = api_client.get(list_url, {"version_status": "DRAFT"})
        assert resp_draft.status_code == 200
        results_draft = resp_draft.json()["data"]["results"]
        draft_titles = [item["latest_version"]["title"] for item in results_draft if item.get("latest_version")]
        assert "Draft Filter Test" in draft_titles
        assert "Published Filter Test" not in draft_titles

    def test_24_historical_archived_records_do_not_break_list_or_detail(self, api_client, admin_user):
        """24. Historical ARCHIVED records (if any exist in DB) do not break Question Bank list or detail."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Historical Archived Question",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)
        # Directly set to ARCHIVED as historical data
        Question.objects.filter(id=q.id).update(status=VersionStatus.ARCHIVED)
        QuestionVersion.objects.filter(id=v1.id).update(status=VersionStatus.ARCHIVED)

        list_url = reverse("questions:admin-question-list")
        resp = api_client.get(list_url)
        assert resp.status_code == 200

        detail_url = reverse("questions:admin-question-version-detail", kwargs={"pk": q.id, "version_number": 1})
        resp_detail = api_client.get(detail_url)
        assert resp_detail.status_code == 200
        assert resp_detail.json()["data"]["status"] == VersionStatus.ARCHIVED

    def test_25_archive_endpoint_is_not_part_of_active_workflow(self, api_client, admin_user):
        """25. Admin question detail serializer does not provide an archive action flag."""
        q, v1 = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Archive Workflow Check",
            description="Desc",
            points=5,
            difficulty=Difficulty.EASY,
            type_config={
                "options": [
                    {"id": "A", "text": "Opt A", "is_correct": True},
                    {"id": "B", "text": "Opt B", "is_correct": False},
                ]
            },
            actor=admin_user,
        )
        QuestionService.publish_version(v1, actor=admin_user)

        detail_url = reverse("questions:admin-question-version-detail", kwargs={"pk": q.id, "version_number": 1})
        resp = api_client.get(detail_url)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "can_archive" not in data
        assert "archive" not in data.get("actions", [])
