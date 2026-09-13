import uuid
import pytest
from datetime import timedelta
from django.utils import timezone
from django.db import connection
from rest_framework import status

from apps.accounts.models import User, Role, AuditLog
from apps.assessments.models import Assessment, AssessmentStatus
from apps.assessments.serializers import AssessmentAdminListSerializer, AssessmentAdminDetailSerializer
from apps.assessments.services import AssessmentSnapshotService


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="regression_admin@codeguard.local",
        password="AdminSecurePassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def creator_user(db):
    return User.objects.create_user(
        email="original_creator@codeguard.local",
        password="CreatorSecurePassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def dangling_assessment(db, creator_user):
    from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus
    from apps.assessments.models import AssessmentQuestion

    q = Question.objects.create(question_type=QuestionType.MCQ, created_by=creator_user)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        question_type=QuestionType.MCQ,
        title="Sample MCQ Question",
        description="MCQ Description",
        points=10,
        status=VersionStatus.PUBLISHED,
        created_by=creator_user,
        type_config={
            "options": [
                {"id": "A", "text": "Option A"},
                {"id": "B", "text": "Option B"},
            ],
            "correct_option": "A",
        }
    )

    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Dangling Creator Assessment",
        description="Assessment created by a user who will be deleted or orphaned",
        start_datetime=now + timedelta(hours=1),
        end_datetime=now + timedelta(hours=5),
        duration_minutes=60,
        total_points=10,
        created_by=creator_user,
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv,
        order=1,
        points=10
    )
    # Simulate orphan / dangling foreign key
    non_existent_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        Assessment.objects.filter(id=assessment.id).update(created_by_id=non_existent_id)
        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
    assessment.refresh_from_db()
    return assessment


@pytest.mark.django_db
class TestDanglingCreatedByRegression:

    def test_admin_assessment_list_returns_dangling_created_by_assessment(self, api_client, admin_user, dangling_assessment):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/admin/assessments/")

        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", {})
        assert data.get("count", 0) >= 1
        results = data.get("results", [])
        assert len(results) >= 1

        matching = [r for r in results if r["id"] == str(dangling_assessment.id)]
        assert len(matching) == 1
        assert matching[0]["title"] == "Dangling Creator Assessment"
        assert matching[0]["created_by_email"] is None

    def test_admin_assessment_detail_returns_dangling_created_by_assessment(self, api_client, admin_user, dangling_assessment):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/v1/admin/assessments/{dangling_assessment.id}/")

        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", {})
        assert data.get("id") == str(dangling_assessment.id)
        assert data.get("title") == "Dangling Creator Assessment"
        assert data.get("created_by_email") is None

    def test_missing_creator_serialized_safely(self, dangling_assessment):
        list_serializer = AssessmentAdminListSerializer(dangling_assessment)
        assert list_serializer.data["created_by_email"] is None

        detail_serializer = AssessmentAdminDetailSerializer(dangling_assessment)
        assert detail_serializer.data["created_by_email"] is None

    def test_valid_creator_serializes_normally(self, admin_user):
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Valid Creator Assessment",
            description="Assessment created by valid admin",
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=5),
            duration_minutes=60,
            total_points=50,
            created_by=admin_user,
        )

        list_serializer = AssessmentAdminListSerializer(assessment)
        assert list_serializer.data["created_by_email"] == admin_user.email

        detail_serializer = AssessmentAdminDetailSerializer(assessment)
        assert detail_serializer.data["created_by_email"] == admin_user.email

    def test_assessment_snapshot_service_with_dangling_created_by(self, dangling_assessment):
        # Create snapshot without passing an actor, so it falls back to assessment.created_by
        snapshot = AssessmentSnapshotService.create_snapshot(dangling_assessment, actor=None)
        assert snapshot is not None
        assert snapshot.assessment_id == dangling_assessment.id

        # Verify audit log logged successfully with actor=None and created_by_id in metadata
        audit = AuditLog.objects.filter(
            action="SNAPSHOT_CREATED",
            target_id=str(snapshot.id)
        ).first()
        assert audit is not None
        assert audit.actor is None
        assert audit.metadata.get("created_by_id") == str(dangling_assessment.created_by_id)
