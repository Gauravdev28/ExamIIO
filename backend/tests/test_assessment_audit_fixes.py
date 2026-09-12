import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status

from apps.assessments.models import Assessment, AssessmentStatus, AssignmentStatus, AssessmentQuestion
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus
from apps.accounts.models import User, Role


@pytest.fixture
def student_user_1(db):
    return User.objects.create_user(
        email="student1_audit@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def student_user_2(db):
    return User.objects.create_user(
        email="student2_audit@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def published_mcq_version(admin_user):
    q = Question.objects.create(question_type=QuestionType.MCQ, created_by=admin_user)
    return QuestionVersion.objects.create(
        question=q,
        version_number=1,
        question_type=QuestionType.MCQ,
        title="Sample MCQ Question",
        description="MCQ Description",
        points=10,
        status=VersionStatus.PUBLISHED,
        created_by=admin_user,
        type_config={
            "options": [
                {"id": "A", "text": "Option A"},
                {"id": "B", "text": "Option B"},
            ],
            "correct_option": "A",
        }
    )


@pytest.fixture
def published_assessment(admin_user, published_mcq_version, student_user_1):
    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Published Technical Assessment",
        description="Initial Description",
        instructions="Initial Instructions",
        start_datetime=now + timedelta(hours=1),
        end_datetime=now + timedelta(hours=4),
        duration_minutes=60,
        total_points=10,
        passing_percentage=50.00,
        status=AssessmentStatus.DRAFT,
        created_by=admin_user
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=published_mcq_version,
        order=1,
        points=10
    )
    assessment.target_students.add(student_user_1)
    
    # Publish the assessment
    from apps.assessments.services import AssessmentService
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)
    return published


@pytest.mark.django_db
class TestAssessmentAuditFixes:
    def test_published_assessment_metadata_editable(self, api_client, admin_user, published_assessment):
        """A1: Non-structural metadata (title, description, instructions, end_datetime) can be updated when published."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('assessments:admin-assessment-detail', kwargs={'pk': published_assessment.id})

        new_end = published_assessment.end_datetime + timedelta(hours=2)
        payload = {
            "title": "Updated Technical Assessment Title",
            "description": "Updated assessment description for candidates.",
            "instructions": "New exam instructions.",
            "end_datetime": new_end.isoformat(),
        }

        res = api_client.patch(url, payload, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['title'] == "Updated Technical Assessment Title"
        assert data['description'] == "Updated assessment description for candidates."

        published_assessment.refresh_from_db()
        assert published_assessment.title == "Updated Technical Assessment Title"
        assert published_assessment.description == "Updated assessment description for candidates."

    def test_published_assessment_total_points_modification_rejected(self, api_client, admin_user, published_assessment):
        """A1: Structural fields like total_points cannot be altered on a published assessment."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('assessments:admin-assessment-detail', kwargs={'pk': published_assessment.id})

        payload = {
            "total_points": 50,  # Snapshot is frozen at 10
        }

        res = api_client.patch(url, payload, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN or res.status_code == status.HTTP_400_BAD_REQUEST

    def test_published_assessment_cannot_be_deleted(self, api_client, admin_user, published_assessment):
        """A5: Published assessments cannot be hard deleted."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('assessments:admin-assessment-detail', kwargs={'pk': published_assessment.id})

        res = api_client.delete(url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot delete a published or archived assessment" in str(res.data)

    def test_draft_assessment_can_be_deleted(self, api_client, admin_user):
        """A5: Draft assessments can be cleanly deleted."""
        api_client.force_authenticate(user=admin_user)
        now = timezone.now()
        draft = Assessment.objects.create(
            title="Unpublished Draft Assessment",
            description="Draft",
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=30,
            status=AssessmentStatus.DRAFT,
            created_by=admin_user
        )

        url = reverse('assessments:admin-assessment-detail', kwargs={'pk': draft.id})
        res = api_client.delete(url)
        assert res.status_code == status.HTTP_200_OK
        assert not Assessment.objects.filter(id=draft.id).exists()

    def test_assign_and_revoke_students_lifecycle(self, api_client, admin_user, published_assessment, student_user_2):
        """A4: Individual and batch student assignments create ASSIGNED records and can be revoked."""
        api_client.force_authenticate(user=admin_user)

        # 1. Assign student_user_2
        url_assign = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': published_assessment.id})
        res = api_client.post(url_assign, {"student_ids": [str(student_user_2.id)]}, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert len(res.data['data']) >= 1

        # Verify record exists in DB
        assignment = published_assessment.assignments.get(student=student_user_2)
        assert assignment.status == AssignmentStatus.ASSIGNED

        # 2. Revoke student_user_2
        url_revoke = reverse('assessments:admin-assessment-assignment-revoke', kwargs={
            'pk': published_assessment.id,
            'student_id': str(student_user_2.id)
        })
        res_revoke = api_client.delete(url_revoke)
        assert res_revoke.status_code == status.HTTP_200_OK

        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.REVOKED
