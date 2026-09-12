import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeguard.settings')

import django
django.setup()

from datetime import timedelta
from django.utils import timezone
from apps.accounts.models import User
from apps.assessments.models import Assessment, TestAttempt
from apps.proctoring.models import ProctoringSession

def setup():
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

    admin = User.objects.filter(role__in=['ADMIN', 'SUPERADMIN']).first()
    assessment = Assessment.objects.filter(status='PUBLISHED').first()
    if not assessment:
        assessment = Assessment.objects.create(
            title='Real Chrome Integrity E2E Assessment',
            description='Assessment for testing tab-switch and focus-loss integrity',
            duration_minutes=60,
            status='PUBLISHED',
            proctoring_enabled=True,
            camera_required=False,
            created_by=admin,
            start_datetime=timezone.now() - timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=7),
        )

    TestAttempt.objects.filter(student=student, assessment=assessment).delete()

    attempt = TestAttempt.objects.create(
        student=student,
        assessment=assessment,
        status='IN_PROGRESS',
        started_at=timezone.now(),
        ip_address='127.0.0.1',
    )

    ProctoringSession.objects.filter(attempt=attempt).delete()
    ProctoringSession.objects.create(
        attempt=attempt,
        status='ACTIVE',
    )

    print(f"SUCCESS: attempt_id={attempt.id} student_email={student.email} assessment_id={assessment.id}")

if __name__ == '__main__':
    setup()
