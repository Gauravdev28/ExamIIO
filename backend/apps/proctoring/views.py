import base64
import time
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from django.db import transaction
from apps.accounts.permissions import IsAdmin, IsStudent
from apps.assessments.models import Assessment, TestAttempt, AttemptStatus
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    ProctoringReview,
    IntegrityIncident,
    EventSource,
    EventSeverity,
    ReviewStatus,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    ProctoringRiskService,
    ProctoringWarningService,
    get_cache_val,
    set_cache_val,
)
from apps.proctoring.serializers import (
    StudentProctoringSessionSerializer,
    StudentProctoringEventIngestSerializer,
    StudentProctoringFrameUploadSerializer,
    StudentProctoringAudioUploadSerializer,
    ProctoringWarningSerializer,
    AdminProctoringSessionListSerializer,
    AdminProctoringSessionDetailSerializer,
    AdminProctoringReviewSerializer,
)
from apps.proctoring.tasks import (
    process_proctoring_frame_task,
    process_proctoring_audio_task,
)


def _check_token_bucket(key: str, capacity: int = 5, fill_rate: float = 0.5) -> bool:
    """
    Redis / In-memory token bucket rate limiter.
    capacity: burst allowance (default: 5 tokens)
    fill_rate: tokens per second (default: 0.5 tokens/sec = 1 token / 2.0s)
    """
    now = time.time()
    data = get_cache_val(key)
    if data:
        try:
            tokens, last_time = map(float, data.split(':'))
            tokens = min(float(capacity), tokens + (now - last_time) * fill_rate)
        except Exception:
            tokens = float(capacity)
    else:
        tokens = float(capacity)

    if tokens >= 1.0:
        tokens -= 1.0
        set_cache_val(key, f"{tokens}:{now}", ex_seconds=60)
        return True
    else:
        set_cache_val(key, f"{tokens}:{now}", ex_seconds=60)
        return False


# ==============================================================================
# Student Endpoints
# ==============================================================================

class StudentProctoringStartView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student').first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You are not authorized to start proctoring for this attempt.")

        session = ProctoringSessionService.start_session(attempt)
        serializer = StudentProctoringSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentProctoringHeartbeatView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student').first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You are not authorized to send heartbeat for this attempt.")

        session = ProctoringSessionService.get_or_create_session(attempt)
        ProctoringSessionService.record_heartbeat(session)

        now = timezone.now()
        if attempt.termination_pending and attempt.termination_deadline and now >= attempt.termination_deadline:
            from apps.proctoring.services import AttemptTerminationPolicyService
            AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
            attempt.refresh_from_db()
            session.refresh_from_db()

        warning = ProctoringWarning.objects.filter(session=session, acknowledged_at__isnull=True).order_by('-issued_at').first()
        warning_data = ProctoringWarningSerializer(warning).data if warning else None
        is_disqualified = (session.status == ProctoringSessionStatus.TERMINATED or attempt.is_disqualified or attempt.status == AttemptStatus.CANCELLED)

        termination_rem_sec = max(0, int((attempt.termination_deadline - now).total_seconds())) if (attempt.termination_pending and attempt.termination_deadline) else None

        return Response({
            "status": "HEALTHY",
            "session_status": session.status,
            "server_time": now.isoformat(),
            "warning": warning_data,
            "warnings_count": session.total_warnings_count,
            "confirmed_violations_count": session.total_warnings_count,
            "disqualified": is_disqualified,
            "disqualified_reason": getattr(attempt, 'disqualification_reason', None) if is_disqualified else None,
            "attempt_status": attempt.status,
            "state_version": getattr(attempt, 'state_version', 0),
            "termination_pending": attempt.termination_pending,
            "termination_deadline": attempt.termination_deadline.isoformat() if attempt.termination_deadline else None,
            "termination_remaining_seconds": termination_rem_sec,
            "termination_reason": attempt.termination_reason,
        }, status=status.HTTP_200_OK)


class StudentProctoringEventIngestionView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [JSONParser]

    def post(self, request, attempt_id):
        serializer = StudentProctoringEventIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_type = serializer.validated_data['event_type']
        client_incident_id = serializer.validated_data.get('client_incident_id')
        client_detected_at = serializer.validated_data.get('client_detected_at')
        metadata = serializer.validated_data.get('metadata', {})
        now = timezone.now()

        from apps.proctoring.security_policy import BrowserSecurityPolicy

        # 1. Authoritative Immediate Security Cancellation (Zero grace period)
        if BrowserSecurityPolicy.is_immediate_cancellation_event(event_type):
            from apps.proctoring.services import BrowserSecurityCancellationService
            res = BrowserSecurityCancellationService.cancel_for_security_violation(
                attempt_id=str(attempt_id),
                student=request.user,
                event_type=event_type,
                metadata=metadata,
                client_incident_id=client_incident_id,
                client_detected_at=client_detected_at,
                actor=request.user,
                request=request
            )
            attempt = res['attempt']
            session = res['session']
            event = res['event']

            is_disqualified = (
                session.status == ProctoringSessionStatus.TERMINATED or
                attempt.is_disqualified or
                attempt.status == AttemptStatus.CANCELLED
            )

            confirmed_count = ProctoringEvent.objects.filter(
                session=session,
                event_type__in=['TAB_SWITCH', 'FULLSCREEN_EXIT', 'PHONE_DETECTED', 'MULTIPLE_FACES'],
                is_confirmed=True
            ).count()

            return Response({
                "event_id": str(event.id) if event else None,
                "status": "RECORDED",
                "source": EventSource.BROWSER,
                "server_received_at": now.isoformat(),
                "warning_issued": False,
                "warning": None,
                "warnings_count": confirmed_count,
                "confirmed_violations_count": confirmed_count,
                "disqualified": is_disqualified,
                "disqualified_reason": getattr(attempt, 'disqualification_reason', None) if is_disqualified else None,
                "attempt_status": attempt.status,
                "state_version": getattr(attempt, 'state_version', 0),
                "termination_pending": attempt.termination_pending,
                "termination_deadline": attempt.termination_deadline.isoformat() if attempt.termination_deadline else None,
                "termination_remaining_seconds": None,
                "termination_reason": attempt.termination_reason,
                "server_time": now.isoformat(),
            }, status=status.HTTP_202_ACCEPTED)

        # 2. Telemetry and Legacy 120-Second Termination Workflow
        with transaction.atomic():
            attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student').first()
            if not attempt:
                raise NotFound("Test attempt not found.")
            if attempt.student != request.user:
                raise PermissionDenied("You are not authorized to report telemetry for this attempt.")

            session = ProctoringSessionService.get_or_create_session(attempt)

            is_first_creation = True
            if client_incident_id:
                incident, created = IntegrityIncident.objects.get_or_create(
                    attempt=attempt,
                    client_incident_id=client_incident_id,
                    defaults={
                        'incident_type': event_type,
                        'metadata': metadata,
                    }
                )
                is_first_creation = created

            event = ProctoringRiskService.record_event(
                session=session,
                event_type=event_type,
                source=EventSource.BROWSER,
                severity=EventSeverity.LOW,
                confidence=1.0,
                started_at=now,
                client_detected_at=client_detected_at,
                metadata=metadata
            )

            # Auto-acknowledge fullscreen warning when fullscreen is re-entered
            if event_type == 'FULLSCREEN_ENTER':
                ProctoringWarning.objects.filter(
                    session=session,
                    warning_type='FULLSCREEN',
                    acknowledged_at__isnull=True
                ).update(acknowledged_at=now)

            # Legacy 2-minute examination termination policy on focus loss (preserved for WINDOW_BLUR & PAGE_VISIBILITY_CHANGE)
            is_legacy_focus_loss = (
                event_type == 'WINDOW_BLUR' or
                (event_type == 'PAGE_VISIBILITY_CHANGE' and (metadata.get('state') == 'hidden' or metadata.get('hidden') is True))
            )
            if is_legacy_focus_loss and is_first_creation and attempt.status == AttemptStatus.IN_PROGRESS:
                from apps.proctoring.services import AttemptTerminationPolicyService
                AttemptTerminationPolicyService.trigger_termination_pending(
                    str(attempt.id),
                    reason="EXAM WINDOW LOST FOCUS"
                )

            attempt.refresh_from_db()
            session.refresh_from_db()

            # Check if overdue
            if attempt.termination_pending and attempt.termination_deadline and now >= attempt.termination_deadline:
                from apps.proctoring.services import AttemptTerminationPolicyService
                AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
                attempt.refresh_from_db()
                session.refresh_from_db()

            is_disqualified = (session.status == ProctoringSessionStatus.TERMINATED or attempt.is_disqualified or attempt.status == AttemptStatus.CANCELLED)

            warning = ProctoringWarning.objects.filter(session=session, acknowledged_at__isnull=True).order_by('-issued_at').first()
            if not warning and event_type != 'FULLSCREEN_ENTER':
                latest = ProctoringWarning.objects.filter(session=session).order_by('-issued_at').first()
                if latest and (now - latest.issued_at).total_seconds() < 10 and latest.warning_type != 'FULLSCREEN':
                    warning = latest
            warning_data = ProctoringWarningSerializer(warning).data if warning else None

            confirmed_count = ProctoringEvent.objects.filter(
                session=session,
                event_type__in=['TAB_SWITCH', 'FULLSCREEN_EXIT', 'PHONE_DETECTED', 'MULTIPLE_FACES'],
                is_confirmed=True
            ).count()

            termination_rem_sec = max(0, int((attempt.termination_deadline - now).total_seconds())) if (attempt.termination_pending and attempt.termination_deadline) else None

            return Response({
                "event_id": str(event.id) if event else None,
                "status": "RECORDED",
                "source": EventSource.BROWSER,
                "server_received_at": now.isoformat(),
                "warning_issued": bool(warning_data),
                "warning": warning_data,
                "warnings_count": confirmed_count,
                "confirmed_violations_count": confirmed_count,
                "disqualified": is_disqualified,
                "disqualified_reason": getattr(attempt, 'disqualification_reason', None) if is_disqualified else None,
                "attempt_status": attempt.status,
                "state_version": getattr(attempt, 'state_version', 0),
                "termination_pending": attempt.termination_pending,
                "termination_deadline": attempt.termination_deadline.isoformat() if attempt.termination_deadline else None,
                "termination_remaining_seconds": termination_rem_sec,
                "termination_reason": attempt.termination_reason,
                "server_time": now.isoformat(),
            }, status=status.HTTP_202_ACCEPTED)


class StudentProctoringFrameUploadView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student').first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You are not authorized to upload frames for this attempt.")

        # Rate Limiter: Redis Token Bucket (Capacity 5, refill 0.5/s)
        rate_key = f"proct_frame_bucket:{attempt.student.id}"
        if not _check_token_bucket(rate_key, capacity=5, fill_rate=0.5):
            return Response(
                {"detail": "Frame submission rate limit exceeded. Please maintain normal sampling intervals."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        session = ProctoringSessionService.get_or_create_session(attempt)
        serializer = StudentProctoringFrameUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frame_file = serializer.validated_data['frame']
        sequence_number = serializer.validated_data.get('sequence_number', 0)

        raw_bytes = frame_file.read()
        raw_bytes_b64 = base64.b64encode(raw_bytes).decode('utf-8')

        # Asynchronous Celery task
        process_proctoring_frame_task.delay(str(session.id), raw_bytes_b64, sequence_number)

        session.refresh_from_db()
        attempt.refresh_from_db()
        warning = ProctoringWarning.objects.filter(session=session, acknowledged_at__isnull=True).order_by('-issued_at').first()
        if not warning:
            latest = ProctoringWarning.objects.filter(session=session).order_by('-issued_at').first()
            if latest and (timezone.now() - latest.issued_at).total_seconds() < 10:
                warning = latest
        warning_data = ProctoringWarningSerializer(warning).data if warning else None
        is_disqualified = (session.status == ProctoringSessionStatus.TERMINATED)

        return Response({
            "status": "QUEUED_FOR_INFERENCE",
            "sequence_number": sequence_number,
            "warning_issued": bool(warning_data),
            "warning": warning_data,
            "warnings_count": session.total_warnings_count,
            "confirmed_violations_count": session.total_warnings_count,
            "disqualified": is_disqualified,
            "disqualified_reason": getattr(attempt, 'disqualification_reason', None) if is_disqualified else None,
        }, status=status.HTTP_202_ACCEPTED)


class StudentProctoringAudioUploadView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student').first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You are not authorized to upload audio for this attempt.")

        # Rate Limiter: Max 6 per minute
        rate_key = f"proct_audio_bucket:{attempt.student.id}"
        if not _check_token_bucket(rate_key, capacity=2, fill_rate=0.1):
            return Response(
                {"detail": "Audio submission rate limit exceeded."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        session = ProctoringSessionService.get_or_create_session(attempt)
        serializer = StudentProctoringAudioUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        audio_file = serializer.validated_data['audio']
        rms_db = serializer.validated_data.get('rms_db', 0.0)

        raw_bytes = audio_file.read()
        raw_bytes_b64 = base64.b64encode(raw_bytes).decode('utf-8')

        process_proctoring_audio_task.delay(str(session.id), raw_bytes_b64, rms_db)

        return Response({
            "status": "QUEUED_FOR_VAD_ANALYSIS"
        }, status=status.HTTP_202_ACCEPTED)


class StudentProctoringWarningAckView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, attempt_id, warning_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student').first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You are not authorized to acknowledge warnings for this attempt.")

        session = ProctoringSessionService.get_or_create_session(attempt)
        warning = ProctoringWarning.objects.filter(id=warning_id, session=session).first()
        if not warning:
            raise NotFound("Proctoring warning not found.")

        warning.acknowledged_at = timezone.now()
        warning.save(update_fields=['acknowledged_at'])

        return Response({
            "status": "ACKNOWLEDGED",
            "acknowledged_at": warning.acknowledged_at.isoformat()
        }, status=status.HTTP_200_OK)


# ==============================================================================
# Admin Endpoints
# ==============================================================================

class AdminProctoringSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, assessment_id):
        assessment = Assessment.objects.filter(id=assessment_id).first()
        if not assessment:
            raise NotFound("Assessment not found.")

        queryset = ProctoringSession.objects.filter(
            attempt__assessment=assessment
        ).select_related(
            'attempt', 'attempt__assessment', 'attempt__student', 'attempt__student__student_profile'
        ).prefetch_related('warnings', 'events').order_by('-created_at')

        risk_band = request.query_params.get('risk_band')
        if risk_band:
            bands = [b.strip() for b in risk_band.split(',')]
            queryset = queryset.filter(risk_band__in=bands)

        review_status = request.query_params.get('review_status')
        if review_status:
            queryset = queryset.filter(review_status=review_status)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                attempt__student__email__icontains=search
            ) | queryset.filter(
                attempt__student__student_profile__euid__icontains=search
            )

        serializer = AdminProctoringSessionListSerializer(queryset, many=True)
        return Response({
            "count": len(serializer.data),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


class AdminProctoringSessionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, session_id):
        session = ProctoringSession.objects.filter(id=session_id).select_related(
            'attempt',
            'attempt__assessment',
            'attempt__student',
            'attempt__student__student_profile',
            'review',
            'review__reviewer'
        ).prefetch_related('events', 'warnings').first()

        if not session:
            raise NotFound("Proctoring session not found.")

        serializer = AdminProctoringSessionDetailSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProctoringEvidenceStreamView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, evidence_id):
        evidence = ProctoringEvidence.objects.filter(id=evidence_id).first()
        if not evidence:
            raise NotFound("Proctoring evidence not found.")

        # Verify storage path existence and read bytes
        if not default_storage.exists(evidence.storage_path):
            raise NotFound("Evidence file not found in storage.")

        file_obj = default_storage.open(evidence.storage_path, 'rb')
        content_type = 'image/jpeg' if evidence.media_type == 'IMAGE_JPEG' else 'audio/webm'
        response = FileResponse(file_obj, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{evidence_id}.jpg"'
        return response


class AdminProctoringReviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, session_id):
        session = ProctoringSession.objects.filter(id=session_id).first()
        if not session:
            raise NotFound("Proctoring session not found.")

        decision = request.data.get('decision')
        notes = request.data.get('notes', '')

        if not decision:
            raise ValidationError("Review decision is required.")

        review, created = ProctoringReview.objects.update_or_create(
            session=session,
            defaults={
                'reviewer': request.user,
                'decision': decision,
                'notes': notes,
                'reviewed_at': timezone.now()
            }
        )

        # Update session review status
        if decision == 'REVIEWED_CLEAN':
            session.review_status = ReviewStatus.REVIEWED
        elif decision == 'DISMISSED_FALSE_POSITIVE':
            session.review_status = ReviewStatus.DISMISSED
        elif decision == 'REQUIRES_FURTHER_INSPECTION':
            session.review_status = ReviewStatus.ESCALATED
        elif decision == 'SUSPICIOUS_CONFIRMED':
            session.review_status = ReviewStatus.UNDER_REVIEW
        session.save(update_fields=['review_status', 'updated_at'])

        serializer = AdminProctoringReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_200_OK)
