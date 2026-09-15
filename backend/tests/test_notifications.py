import pytest
from rest_framework import status
from apps.accounts.models import User, Role, StudentProfile
from apps.core.models import Notification, NotificationType, NotificationAudience


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        email='test_admin_notif@exam.edu',
        password='AdminPassword123!',
        role=Role.ADMIN,
        display_name='Admin Tester',
    )
    return user


@pytest.fixture
def student_one(db):
    user = User.objects.create_user(
        email='student_one_notif@exam.edu',
        password='StudentPassword123!',
        role=Role.STUDENT,
        display_name='Student One',
    )
    StudentProfile.objects.create(
        user=user,
        roll_number='ROLL-NOTIF-001',
        euid='EUID-NOTIF-001',
        certificate_name='Student One'
    )
    return user


@pytest.fixture
def student_two(db):
    user = User.objects.create_user(
        email='student_two_notif@exam.edu',
        password='StudentPassword123!',
        role=Role.STUDENT,
        display_name='Student Two',
    )
    StudentProfile.objects.create(
        user=user,
        roll_number='ROLL-NOTIF-002',
        euid='EUID-NOTIF-002',
        certificate_name='Student Two'
    )
    return user


@pytest.mark.django_db
class TestNotificationSystem:
    def test_unauthenticated_access_denied(self, client):
        res = client.get('/api/v1/notifications/')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        res = client.post('/api/v1/notifications/send/', {})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_cannot_send_notification(self, client, student_one, student_two):
        client.force_login(student_one)
        payload = {
            'audience': NotificationAudience.INDIVIDUAL,
            'recipient_id': str(student_two.id),
            'title': 'Hacked Message',
            'message': 'Attempting unauthorized send',
            'notification_type': NotificationType.NOTICE,
        }
        res = client.post('/api/v1/notifications/send/', payload, content_type='application/json')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_send_to_individual_student(self, client, admin_user, student_one):
        client.force_login(admin_user)
        payload = {
            'audience': NotificationAudience.INDIVIDUAL,
            'recipient_id': str(student_one.id),
            'title': 'Exam Reminder',
            'message': 'Your examination starts at 10:00 AM tomorrow.',
            'notification_type': NotificationType.REMINDER,
        }
        res = client.post('/api/v1/notifications/send/', payload, content_type='application/json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()['data']
        assert data['sent_count'] == 1
        assert data['audience'] == 'INDIVIDUAL'

        # Verify persisted in database
        notif = Notification.objects.filter(recipient=student_one).first()
        assert notif is not None
        assert notif.title == 'Exam Reminder'
        assert notif.notification_type == NotificationType.REMINDER
        assert notif.sender == admin_user
        assert not notif.is_read

    def test_admin_cannot_send_to_invalid_recipient(self, client, admin_user):
        client.force_login(admin_user)
        # 1. Non-existent UUID
        payload = {
            'audience': NotificationAudience.INDIVIDUAL,
            'recipient_id': '00000000-0000-0000-0000-000000000000',
            'title': 'Invalid',
            'message': 'Invalid recipient',
            'notification_type': NotificationType.NOTICE,
        }
        res = client.post('/api/v1/notifications/send/', payload, content_type='application/json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Cannot send to another admin
        other_admin = User.objects.create_user(
            email='other_admin_notif@exam.edu',
            password='AdminPassword123!',
            role=Role.ADMIN,
        )
        payload['recipient_id'] = str(other_admin.id)
        res = client.post('/api/v1/notifications/send/', payload, content_type='application/json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'student' in str(res.json()).lower()

    def test_admin_send_to_all_students(self, client, admin_user, student_one, student_two):
        client.force_login(admin_user)
        payload = {
            'audience': NotificationAudience.ALL_STUDENTS,
            'title': 'Campus Wide Notice',
            'message': 'The test laboratory will open at 09:30 AM.',
            'notification_type': NotificationType.ANNOUNCEMENT,
        }
        res = client.post('/api/v1/notifications/send/', payload, content_type='application/json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()['data']
        assert data['sent_count'] >= 2

        # Both students must have their own individual materialized notification
        notif_1 = Notification.objects.filter(recipient=student_one, title='Campus Wide Notice').first()
        notif_2 = Notification.objects.filter(recipient=student_two, title='Campus Wide Notice').first()
        assert notif_1 is not None
        assert notif_2 is not None
        assert notif_1.id != notif_2.id
        assert not notif_1.is_read
        assert not notif_2.is_read

    def test_student_isolation_and_unread_count(self, client, admin_user, student_one, student_two):
        # Create notification for student one only
        notif_1 = Notification.objects.create(
            recipient=student_one,
            sender=admin_user,
            title='Secret for Student One',
            message='Private information',
            notification_type=NotificationType.NOTICE,
        )

        # Student Two checks notifications: must be empty
        client.force_login(student_two)
        res = client.get('/api/v1/notifications/')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert len(data['notifications']) == 0
        assert data['unread_count'] == 0

        # Student Two checks unread count endpoint
        res = client.get('/api/v1/notifications/unread-count/')
        assert res.status_code == status.HTTP_200_OK
        assert res.json()['data']['unread_count'] == 0

        # Student One checks notifications: sees their notification
        client.force_login(student_one)
        res = client.get('/api/v1/notifications/')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert len(data['notifications']) == 1
        assert data['notifications'][0]['id'] == str(notif_1.id)
        assert data['unread_count'] == 1

    def test_read_state_isolation_and_mark_read(self, client, admin_user, student_one, student_two):
        notif_1 = Notification.objects.create(
            recipient=student_one,
            sender=admin_user,
            title='Notice One',
            message='For student 1',
            notification_type=NotificationType.NOTICE,
        )

        # Student Two attempts to mark Student One's notification as read -> 404 (IDOR prevented)
        client.force_login(student_two)
        res = client.patch(f'/api/v1/notifications/{notif_1.id}/read/')
        assert res.status_code == status.HTTP_404_NOT_FOUND
        notif_1.refresh_from_db()
        assert not notif_1.is_read

        # Student One marks their own notification as read -> 200
        client.force_login(student_one)
        res = client.patch(f'/api/v1/notifications/{notif_1.id}/read/')
        assert res.status_code == status.HTTP_200_OK
        assert res.json()['data']['notification']['is_read'] is True
        assert res.json()['data']['unread_count'] == 0
        notif_1.refresh_from_db()
        assert notif_1.is_read is True
        assert notif_1.read_at is not None

    def test_mark_all_read(self, client, admin_user, student_one):
        Notification.objects.create(
            recipient=student_one,
            sender=admin_user,
            title='Notice A',
            message='Body A',
        )
        Notification.objects.create(
            recipient=student_one,
            sender=admin_user,
            title='Notice B',
            message='Body B',
        )

        client.force_login(student_one)
        res = client.post('/api/v1/notifications/mark-all-read/')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['marked_count'] == 2
        assert data['unread_count'] == 0

        # Verify DB records
        unread = Notification.objects.filter(recipient=student_one, is_read=False).count()
        assert unread == 0
