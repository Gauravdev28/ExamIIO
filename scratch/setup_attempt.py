from datetime import timedelta
from django.utils import timezone
from apps.accounts.models import User
from apps.assessments.models import Assessment, AssessmentSnapshot, TestAttempt
from apps.proctoring.models import ProctoringSession

student, _ = User.objects.get_or_create(
    email='chrome_test_student@example.com',
    defaults={
        'first_name': 'Chrome',
        'last_name': 'Tester',
        'role': 'STUDENT',
        'is_active': True,
    }
)
student.set_password('Password123!')
student.role = 'STUDENT'
student.is_active = True
student.save()

assessment = Assessment.objects.filter(title='Sample 001').first()
if not assessment:
    assessment = Assessment.objects.filter(status='PUBLISHED').first()

snapshot = AssessmentSnapshot.objects.filter(assessment=assessment).order_by('-version_number').first()
raw_questions = snapshot.snapshot_data.get('questions', []) if snapshot and snapshot.snapshot_data else []
q_ids = [q['snapshot_question_id'] for q in raw_questions]

# Remove prior attempts for this student on this assessment
TestAttempt.objects.filter(student=student, assessment=assessment).delete()

attempt = TestAttempt.objects.create(
    student=student,
    assessment=assessment,
    assessment_snapshot=snapshot,
    status='IN_PROGRESS',
    started_at=timezone.now(),
    expires_at=timezone.now() + timedelta(hours=1),
    randomization_seed='test-seed-12345',
    question_order=q_ids,
)

ProctoringSession.objects.filter(attempt=attempt).delete()
ProctoringSession.objects.create(
    attempt=attempt,
    status='ACTIVE',
)

print(f"READY: attempt_id={str(attempt.id)} student_email={student.email}")
