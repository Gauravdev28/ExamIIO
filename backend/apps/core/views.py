import os
import time
from django.db import connection
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
from .responses import APIResponse

class HealthCheckView(APIView):
    """
    System Health Check Endpoint.
    Tests database connectivity and cache responsiveness.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        health_status = {
            "application": "CODEGUARD Assessment Platform",
            "version": "1.0.0-phase1",
            "timestamp": timezone.now().isoformat(),
            "environment": os.getenv('DJANGO_ENV', 'development'),
            "services": {}
        }
        overall_healthy = True

        # 1. Test Database Connectivity
        db_start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            db_duration_ms = round((time.time() - db_start) * 1000, 2)
            health_status["services"]["database"] = {
                "status": "healthy",
                "engine": connection.vendor,
                "latency_ms": db_duration_ms
            }
        except Exception as e:
            overall_healthy = False
            health_status["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # 2. Test Cache / Channel Layer
        cache_start = time.time()
        channel_backend = settings.CHANNEL_LAYERS.get('default', {}).get('BACKEND', '')
        is_in_memory = 'InMemoryChannelLayer' in channel_backend or getattr(settings, 'TESTING', False)

        if is_in_memory:
            health_status["services"]["redis"] = {
                "status": "healthy",
                "mode": "in-memory (testing/dev)",
                "latency_ms": 0.0
            }
        else:
            try:
                import redis
                redis_client = redis.from_url(settings.REDIS_URL, socket_timeout=1)
                redis_client.ping()
                cache_duration_ms = round((time.time() - cache_start) * 1000, 2)
                health_status["services"]["redis"] = {
                    "status": "healthy",
                    "latency_ms": cache_duration_ms
                }
            except Exception as e:
                if settings.DEBUG:
                    health_status["services"]["redis"] = {
                        "status": "degraded",
                        "message": "Redis unavailable (using development fallback)",
                        "error": str(e)
                    }
                else:
                    overall_healthy = False
                    health_status["services"]["redis"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }

        http_status = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        # For public unauthenticated callers, expose only high-level status without leaking infrastructure details
        is_admin = request.user.is_authenticated and getattr(request.user, 'role', '') == 'ADMIN'
        is_test = getattr(settings, 'TESTING', False)

        if not (is_admin or is_test):
            return APIResponse(
                data={"status": "healthy" if overall_healthy else "degraded"},
                message="System is operational" if overall_healthy else "System is experiencing degraded service",
                status_code=http_status
            )

        health_status["status"] = "healthy" if overall_healthy else "degraded"
        return APIResponse(
            data=health_status,
            message="System is operational" if overall_healthy else "System is experiencing degraded service",
            status_code=http_status
        )


class SystemInfoView(APIView):
    """
    Public system metadata endpoint exposing API capabilities.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return APIResponse(
            data={
                "name": "CODEGUARD API",
                "version": "1.0.0",
                "supported_languages": ["python", "cpp", "java"],
                "phase": "Phase 1: Foundation",
                "docs_url": "/api/docs/"
            },
            message="CODEGUARD API Gateway"
        )


# ============================================================================
# NOTIFICATION SYSTEM VIEWS
# ============================================================================

from apps.accounts.permissions import IsAdmin, IsActiveUser
from apps.accounts.models import User, Role
from apps.accounts.services import AuditService
from .models import Notification, NotificationType, NotificationAudience
from .serializers import (
    NotificationSerializer,
    AdminSendNotificationSerializer,
    StudentOptionSerializer,
)


class NotificationListView(APIView):
    """
    Candidate and User notification inbox.
    Retrieves notifications strictly addressed to the authenticated user.
    """
    permission_classes = [IsActiveUser]

    def get(self, request):
        unread_only = request.query_params.get('unread_only', '').lower() == 'true'
        queryset = Notification.objects.filter(recipient=request.user).select_related('sender', 'assessment')

        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        total_count = queryset.count()

        if unread_only:
            queryset = queryset.filter(is_read=False)

        # Limit to latest 50 notifications for responsive delivery
        notifications = queryset[:50]
        serializer = NotificationSerializer(notifications, many=True)

        return APIResponse(
            data={
                "notifications": serializer.data,
                "unread_count": unread_count,
                "total_count": total_count,
            },
            message="Notifications retrieved successfully."
        )


class NotificationUnreadCountView(APIView):
    """
    Lightweight endpoint returning the authoritative unread notification count.
    """
    permission_classes = [IsActiveUser]

    def get(self, request):
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return APIResponse(
            data={"unread_count": unread_count},
            message="Unread notification count retrieved."
        )


class NotificationMarkReadView(APIView):
    """
    Marks a single notification as read for the authenticated recipient.
    Strictly prevents IDOR by filtering on recipient=request.user.
    """
    permission_classes = [IsActiveUser]

    def patch(self, request, pk):
        notification = Notification.objects.filter(id=pk, recipient=request.user).first()
        if not notification:
            return APIResponse(
                message="Notification not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        notification.mark_as_read()
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

        serializer = NotificationSerializer(notification)
        return APIResponse(
            data={
                "notification": serializer.data,
                "unread_count": unread_count,
            },
            message="Notification marked as read."
        )

    def post(self, request, pk):
        return self.patch(request, pk)


class NotificationMarkAllReadView(APIView):
    """
    Marks all unread notifications as read for the authenticated user.
    """
    permission_classes = [IsActiveUser]

    def post(self, request):
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

        return APIResponse(
            data={
                "marked_count": updated_count,
                "unread_count": 0,
            },
            message=f"Marked {updated_count} notifications as read."
        )


class AdminNotificationSendView(APIView):
    """
    Administrative endpoint for authoring and delivering notifications.
    Supports individual student targeting and whole-cohort announcements.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = AdminSendNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                data=serializer.errors,
                message="Validation failed.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data
        audience = validated_data['audience']
        title = validated_data['title']
        message = validated_data['message']
        notification_type = validated_data['notification_type']
        assessment = validated_data.get('assessment_obj')

        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))

        if audience == NotificationAudience.INDIVIDUAL:
            recipient = validated_data['recipient_user']
            notification = Notification.objects.create(
                recipient=recipient,
                sender=request.user,
                title=title,
                message=message,
                notification_type=notification_type,
                audience=NotificationAudience.INDIVIDUAL,
                assessment=assessment,
            )

            try:
                AuditService.log(
                    action="NOTIFICATION_SENT",
                    actor=request.user,
                    target_user=recipient,
                    ip_address=client_ip,
                    metadata={
                        "audience": audience,
                        "notification_type": notification_type,
                        "title": title,
                        "recipient_email": recipient.email,
                    }
                )
            except Exception:
                pass

            return APIResponse(
                data={
                    "sent_count": 1,
                    "audience": audience,
                    "notification": NotificationSerializer(notification).data,
                },
                message=f"Notification dispatched to student {recipient.email}.",
                status_code=status.HTTP_201_CREATED
            )

        else:  # ALL_STUDENTS
            students = list(User.objects.filter(role=Role.STUDENT, is_active=True))
            if not students:
                return APIResponse(
                    data={"sent_count": 0, "audience": audience},
                    message="No active students found in the platform.",
                    status_code=status.HTTP_200_OK
                )

            batch = [
                Notification(
                    recipient=student,
                    sender=request.user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    audience=NotificationAudience.ALL_STUDENTS,
                    assessment=assessment,
                )
                for student in students
            ]
            Notification.objects.bulk_create(batch)

            try:
                AuditService.log(
                    action="NOTIFICATION_BROADCAST",
                    actor=request.user,
                    ip_address=client_ip,
                    metadata={
                        "audience": audience,
                        "notification_type": notification_type,
                        "title": title,
                        "recipient_count": len(batch),
                    }
                )
            except Exception:
                pass

            return APIResponse(
                data={
                    "sent_count": len(batch),
                    "audience": audience,
                },
                message=f"Announcement broadcast to {len(batch)} active students.",
                status_code=status.HTTP_201_CREATED
            )


class AdminStudentListView(APIView):
    """
    Returns active student candidates for the admin notification recipient selector.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        search_query = request.query_params.get('q', '').strip()
        queryset = User.objects.filter(role=Role.STUDENT, is_active=True).select_related('student_profile')

        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(display_name__icontains=search_query) |
                Q(student_profile__roll_number__icontains=search_query) |
                Q(student_profile__euid__icontains=search_query)
            )

        students = queryset.order_by('display_name', 'email')[:100]
        serializer = StudentOptionSerializer(students, many=True)
        return APIResponse(
            data={"students": serializer.data},
            message="Active students retrieved successfully."
        )

