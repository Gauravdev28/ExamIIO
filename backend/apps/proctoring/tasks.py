import base64
import logging
from celery import shared_task
from django.utils import timezone
from apps.proctoring.models import ProctoringSession, EventSource, EventSeverity
from apps.proctoring.services import (
    ProctoringAIService,
    ProctoringRiskService,
    ProctoringSessionService,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_proctoring_frame_task(self, session_id: str, raw_bytes_b64: str, sequence_number: int = 0):
    """
    Asynchronous Celery Task for computer vision frame analysis.
    Executes out-of-band and never blocks Monaco editor typing, autosave, or code execution.
    """
    try:
        session = ProctoringSession.objects.filter(id=session_id).first()
        if not session or session.status not in ['ACTIVE', 'DEGRADED']:
            return {"status": "SKIPPED", "reason": "Session not active"}

        raw_bytes = base64.b64decode(raw_bytes_b64)
        signals = ProctoringAIService.analyze_frame_data(session, raw_bytes, sequence_number)

        for sig in signals:
            event_type = sig['event_type']
            if event_type == 'AI_INFERENCE_FAILURE':
                ProctoringSessionService.degrade_session(session, reason="AI Inference Failure")
            else:
                ProctoringRiskService.record_event(
                    session=session,
                    event_type=event_type,
                    source=EventSource.AI,
                    severity=sig.get('severity', EventSeverity.LOW),
                    confidence=sig.get('confidence', 1.0),
                    started_at=timezone.now(),
                    metadata=sig.get('metadata', {}),
                    evidence=sig.get('evidence')
                )

        return {"status": "SUCCESS", "signals_count": len(signals)}

    except Exception as exc:
        logger.error(f"Error processing frame for session {session_id}: {exc}", exc_info=True)
        try:
            session = ProctoringSession.objects.filter(id=session_id).first()
            if session:
                ProctoringSessionService.degrade_session(session, reason=f"Worker Error: {str(exc)}")
        except Exception:
            pass
        return {"status": "ERROR", "error": str(exc)}


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_proctoring_audio_task(self, session_id: str, raw_bytes_b64: str, client_rms_db: float = 0.0):
    """
    Asynchronous Celery Task for acoustic Voice Activity Detection (VAD).
    """
    try:
        session = ProctoringSession.objects.filter(id=session_id).first()
        if not session or session.status not in ['ACTIVE', 'DEGRADED']:
            return {"status": "SKIPPED", "reason": "Session not active"}

        raw_bytes = base64.b64decode(raw_bytes_b64)
        vad_result = ProctoringAIService.analyze_audio_data(session, raw_bytes, client_rms_db)

        if vad_result.get('is_speech'):
            ProctoringRiskService.record_event(
                session=session,
                event_type='AUDIO_ACTIVITY',
                source=EventSource.AI,
                severity=EventSeverity.MEDIUM,
                confidence=vad_result.get('confidence', 0.85),
                started_at=timezone.now(),
                metadata={'client_rms_db': client_rms_db, 'vad_speech': True},
                evidence=vad_result.get('evidence')
            )

        return {"status": "SUCCESS", "speech_detected": vad_result.get('is_speech', False)}

    except Exception as exc:
        logger.error(f"Error processing audio for session {session_id}: {exc}", exc_info=True)
        return {"status": "ERROR", "error": str(exc)}


@shared_task(bind=True, name='apps.proctoring.tasks.expire_window_termination_task')
def expire_window_termination_task(self, attempt_id: str):
    """
    Celery task scheduled with countdown=120 as a scheduling trigger.
    The task itself re-evaluates `timezone.now() >= attempt.termination_deadline`
    authoritatively under a select_for_update() row lock.
    """
    from apps.proctoring.services import AttemptTerminationPolicyService
    return AttemptTerminationPolicyService.check_and_expire_termination(attempt_id)


@shared_task(bind=True, name='apps.proctoring.tasks.check_websocket_disconnect_task')
def check_websocket_disconnect_task(self, attempt_id: str, disconnect_token: str):
    """
    10-second Celery countdown task initiated when a student WebSocket disconnects.
    If the socket reconnects within 10 seconds, the countdown token is cancelled.
    If it reaches 0 and the disconnect token remains valid, triggers standard termination protocol.
    """
    import time
    from django.core.cache import cache
    from django.conf import settings
    from django.db import transaction
    from apps.assessments.models import TestAttempt, AttemptStatus
    from apps.proctoring.services import AttemptTerminationPolicyService

    cache_key = f"ws_disconnect_{attempt_id}"
    disconnect_data = cache.get(cache_key)

    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        if disconnect_data and isinstance(disconnect_data, dict):
            disconnected_at = disconnect_data.get('disconnected_at', 0)
            if time.time() - disconnected_at < 9.5:
                return {"status": "EAGER_SKIPPED", "reason": "10s grace period pending"}

    if not disconnect_data or (isinstance(disconnect_data, dict) and disconnect_data.get('token') != disconnect_token):
        return {"status": "CANCELLED", "reason": "Reconnected within grace period"}

    with transaction.atomic():
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).first()
        if not attempt or attempt.status != AttemptStatus.IN_PROGRESS:
            return {"status": "SKIPPED", "reason": "Attempt not in progress"}

        attempt.disqualification_reason = "EXAMINATION TERMINATED — CONNECTION LOST"
        return AttemptTerminationPolicyService._execute_expiration_locked(attempt)
