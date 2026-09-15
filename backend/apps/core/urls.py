from django.urls import path
from .views import (
    HealthCheckView,
    SystemInfoView,
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    AdminNotificationSendView,
    AdminStudentListView,
)

app_name = 'core'

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('info/', SystemInfoView.as_view(), name='system-info'),

    # Notification endpoints
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('notifications/send/', AdminNotificationSendView.as_view(), name='notification-admin-send'),
    path('notifications/students/', AdminStudentListView.as_view(), name='notification-admin-students'),
]
