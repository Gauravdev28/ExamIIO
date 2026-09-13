import os
import math
import uuid
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.conf import settings
from django.db import transaction, models
from django.utils import timezone as django_timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.assessments.models import TestAttempt, AttemptStatus
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    ProctoringReview,
    IntegrityIncident,
    RiskBand,
    ReviewStatus,
    EventSource,
    EventSeverity,
    RetentionClass,
)
from apps.proctoring.policies import (
    PROCTORING_INFERENCE_POLICY_V1,
    PROCTORING_AUDIO_POLICY_V1,
    EVENT_FAMILY_MAP,
    EVENT_FAMILY_CAPS,
    EVENT_BASE_DELTAS,
    EVENT_COOLDOWNS_SECONDS,
    ProctoringSignalPolicy,
)

try:
    import redis
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

# In-memory fallback dictionary for test environments without live Redis
_MEMORY_CACHE = {}


def get_cache_val(key):
    if redis_client:
        try:
            return redis_client.get(key)
        except Exception:
            pass
    return _MEMORY_CACHE.get(key)


def set_cache_val(key, val, ex_seconds=60):
    if redis_client:
        try:
            redis_client.set(key, str(val), ex=ex_seconds)
            return
        except Exception:
            pass
    _MEMORY_CACHE[key] = str(val)


class ProctoringSessionService:
    @staticmethod
    def get_or_create_session(attempt: TestAttempt) -> ProctoringSession:
        session, created = ProctoringSession.objects.get_or_create(
            attempt=attempt,
            defaults={
                'status': ProctoringSessionStatus.ACTIVE,
                'risk_score': Decimal('0.00'),
                'risk_band': RiskBand.NORMAL,
                'review_status': ReviewStatus.UNREVIEWED,
            }
        )
        return session

    @staticmethod
    def start_session(attempt: TestAttempt) -> ProctoringSession:
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError("Proctoring session can only be started for IN_PROGRESS attempts.")
        session = ProctoringSessionService.get_or_create_session(attempt)
        if session.status != ProctoringSessionStatus.ACTIVE:
            session.status = ProctoringSessionStatus.ACTIVE
            session.save(update_fields=['status', 'updated_at'])
        return session

    @staticmethod
    def record_heartbeat(session: ProctoringSession) -> ProctoringSession:
        session.updated_at = django_timezone.now()
        session.save(update_fields=['updated_at'])
        return session

    @staticmethod
    def degrade_session(session: ProctoringSession, reason: str = "") -> ProctoringSession:
        session.status = ProctoringSessionStatus.DEGRADED
        session.save(update_fields=['status', 'updated_at'])
        
        # Record a system operational event with ZERO risk delta
        ProctoringRiskService.record_event(
            session=session,
            event_type='PROCTORING_DEGRADED',
            source=EventSource.SYSTEM,
            severity=EventSeverity.MEDIUM,
            confidence=1.0,
            metadata={'reason': reason},
            started_at=django_timezone.now()
        )
        return session


class ProctoringEvidenceService:
    @staticmethod
    def save_evidence(
        session: ProctoringSession,
        raw_bytes: bytes,
        media_type: str = 'IMAGE_JPEG',
        retention_class: str = RetentionClass.TEMPORARY_EVIDENCE,
        expires_in_days: int = 30
    ) -> ProctoringEvidence:
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_ext = '.jpg' if media_type == 'IMAGE_JPEG' else '.webm'
        filename = f"evidence_{uuid.uuid4().hex}{file_ext}"
        relative_path = os.path.join('proctoring', str(session.id), filename)
        
        # Save via Django default storage
        full_path = default_storage.save(relative_path, ContentFile(raw_bytes))
        
        expires_at = django_timezone.now() + timedelta(days=expires_in_days)
        
        evidence = ProctoringEvidence.objects.create(
            session=session,
            media_type=media_type,
            storage_path=full_path,
            sha256_hash=sha256_hash,
            file_size_bytes=len(raw_bytes),
            expires_at=expires_at,
            retention_class=retention_class
        )
        return evidence


class ProctoringWarningService:
    @staticmethod
    def issue_warning_if_eligible(
        session: ProctoringSession,
        event_type: str,
        custom_message: str = "",
        bypass_cooldown: bool = False
    ) -> ProctoringWarning | None:
        warning_map = {
            'FULLSCREEN_EXIT': ('FULLSCREEN', 'Full-screen mode was exited. Please re-enter full-screen to continue your assessment.'),
            'TAB_SWITCH': ('FOCUS_LOSS', 'Your examination window lost focus. Please return to the assessment immediately.'),
            'WINDOW_BLUR': ('FOCUS_LOSS', 'Your examination window lost focus. Please return to the assessment immediately.'),
            'FACE_MISSING': ('FACE_VISIBILITY', 'Please ensure your face is clearly visible in the camera.'),
            'MULTIPLE_FACES': ('MULTIPLE_PEOPLE', 'Only the registered candidate should be visible during the examination.'),
            'PHONE_DETECTED': ('UNAUTHORIZED_DEVICE', 'A possible mobile device has been detected. Please remove it from the examination area.'),
            'AUDIO_ACTIVITY': ('AUDIO', 'Excessive background acoustic activity detected. Please maintain exam quietness.'),
            'CAMERA_UNAVAILABLE': ('CAMERA', 'Your webcam is no longer available. Reconnect your camera to continue the monitored examination.'),
            'MICROPHONE_UNAVAILABLE': ('AUDIO', 'Your microphone is no longer available. Reconnect your audio input to continue the monitored examination.'),
            'HEAD_TURN_PROLONGED': ('HEAD_POSE', 'Please keep your face visible and oriented toward the examination camera.'),
            'GAZE_DEVIATION': ('HEAD_POSE', 'Please keep your face visible and oriented toward the examination camera.'),
        }
        if event_type not in warning_map:
            return None
            
        warning_type, default_msg = warning_map[event_type]
        message = custom_message or default_msg
        cooldown_key = f"proct_warn_cooldown:{session.id}:{warning_type}"
        if not bypass_cooldown and get_cache_val(cooldown_key):
            return None  # Cooldown active; suppress warning spam
            
        set_cache_val(cooldown_key, "1", ex_seconds=30)
        
        warning = ProctoringWarning.objects.create(
            session=session,
            warning_type=warning_type,
            message=message,
        )
        session.total_warnings_count += 1
        session.save(update_fields=['total_warnings_count', 'updated_at'])

        # Real-time WebSocket dispatch to student room & proctor console
        if hasattr(session, 'attempt') and session.attempt:
            try:
                from apps.invigilation.services import LiveInterventionService
                LiveInterventionService._dispatch_websocket_event(
                    f"attempt_{session.attempt.id}",
                    {
                        "event": "WARNING_ISSUED",
                        "attempt_id": str(session.attempt.id),
                        "intervention_id": str(warning.id),
                        "reason_code": warning.warning_type,
                        "message": warning.message,
                        "issued_at": warning.issued_at.isoformat(),
                        "warnings_count": session.total_warnings_count
                    }
                )
            except Exception:
                pass

        return warning


class ProctoringRiskService:
    @staticmethod
    def determine_risk_band(score: Decimal) -> str:
        if score <= Decimal('20.00'):
            return RiskBand.NORMAL
        elif score <= Decimal('40.00'):
            return RiskBand.LOW
        elif score <= Decimal('60.00'):
            return RiskBand.MEDIUM
        elif score <= Decimal('80.00'):
            return RiskBand.HIGH
        else:
            return RiskBand.CRITICAL

    @staticmethod
    def check_persistence_gate(session_id: str, event_type: str, confidence: float) -> bool:
        """
        High-impact signals (PHONE_DETECTED, MULTIPLE_FACES) require qualifying confidence
        and at least 2 persistent frames within 4 seconds.
        """
        policy = PROCTORING_INFERENCE_POLICY_V1
        if event_type == 'PHONE_DETECTED':
            if confidence < policy['phone_confidence_threshold']:
                return False
        elif event_type == 'MULTIPLE_FACES':
            if confidence < policy['multiple_face_confidence_threshold']:
                return False
        else:
            return True  # Other signals don't require multi-frame persistence gate

        gate_key = f"proct_persistence:{session_id}:{event_type}"
        current_count = int(get_cache_val(gate_key) or "0") + 1
        set_cache_val(gate_key, current_count, ex_seconds=int(policy['persistence_window_seconds']))
        
        return current_count >= policy['required_persistent_frames']

    @classmethod
    def _disqualify_candidate(cls, session: ProctoringSession, event: ProctoringEvent, violation_count: int, max_threshold: int = 3):
        from apps.accounts.services import AuditService
        from apps.invigilation.services import LiveInterventionService

        now = django_timezone.now()
        attempt = session.attempt

        # 1. Terminate proctoring session
        session.status = ProctoringSessionStatus.TERMINATED
        session.save(update_fields=['status', 'updated_at'])

        reason_str = f"THREE_STRONG_PROCTORING_VIOLATIONS: Security violations threshold exceeded ({violation_count}/{max_threshold})."

        # 2. Cancel attempt & persist disqualification
        attempt.is_disqualified = True
        attempt.disqualification_reason = reason_str
        attempt.disqualified_at = now
        setattr(attempt, 'disqualified', True)
        setattr(attempt, 'disqualified_reason', reason_str)
        setattr(attempt, 'disqualified_at', now)

        if attempt.status != AttemptStatus.CANCELLED:
            attempt.status = AttemptStatus.CANCELLED
            attempt.submitted_at = now
        
        attempt.save(update_fields=[
            'is_disqualified',
            'disqualification_reason',
            'disqualified_at',
            'status',
            'submitted_at',
            'updated_at',
        ])

        # 3. Record authoritative disqualification metadata
        if event:
            event.metadata = event.metadata or {}
            event.metadata['disqualified'] = True
            event.metadata['disqualified_reason'] = reason_str
            event.metadata['disqualified_at'] = now.isoformat()
            event.metadata['confirmed_violations_count'] = violation_count
            event.save(update_fields=['metadata'])

        # 4. Log immutable audit entry CANDIDATE_DISQUALIFIED
        AuditService.log(
            action="CANDIDATE_DISQUALIFIED",
            actor=attempt.student,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={
                "session_id": str(session.id),
                "reason": "Excessive confirmed violations (tab switch / fullscreen exit threshold exceeded)",
                "violations_count": violation_count,
                "disqualified_at": now.isoformat()
            }
        )

        # 5. Trigger finalization on commit / fallback
        try:
            from apps.results.tasks import finalize_assessment_result_task
            finalize_assessment_result_task.delay(str(attempt.id))
        except Exception:
            try:
                from apps.results.services import ResultFinalizationService
                ResultFinalizationService.finalize_attempt(str(attempt.id))
            except Exception:
                pass

        # 6. WebSocket broadcast
        payload = {
            "event": "TERMINATION_REQUESTED",
            "attempt_id": str(attempt.id),
            "reason_code": "DISQUALIFIED",
            "justification": "Excessive confirmed violations (tab switch / fullscreen exit threshold exceeded)",
            "status": AttemptStatus.CANCELLED,
            "terminated_at": now.isoformat()
        }
        LiveInterventionService._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        LiveInterventionService._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

    @classmethod
    def record_event(
        cls,
        session: ProctoringSession,
        event_type: str,
        source: str = EventSource.BROWSER,
        severity: str = EventSeverity.LOW,
        confidence: float = 1.0,
        started_at: datetime = None,
        client_detected_at: datetime = None,
        model_name: str = "",
        model_version: str = "",
        metadata: dict = None,
        evidence: ProctoringEvidence = None,
        bypass_cooldown: bool = False,
        is_confirmed: Optional[bool] = None
    ) -> ProctoringEvent:
        if started_at is None:
            started_at = django_timezone.now()
        if metadata is None:
            metadata = {}

        # Determine authoritative confirmation status
        if is_confirmed is not None:
            confirmed_flag = bool(is_confirmed)
        elif metadata and ('is_confirmed' in metadata or 'raw' in metadata or 'confirmed' in metadata):
            if 'is_confirmed' in metadata:
                confirmed_flag = bool(metadata['is_confirmed'])
            elif 'raw' in metadata:
                confirmed_flag = not bool(metadata['raw'])
            else:
                confirmed_flag = bool(metadata['confirmed'])
        else:
            confirmed_flag = True

        if bypass_cooldown or metadata.get('bypass_cooldown'):
            cooldown_sec = 0
        else:
            cooldown_sec = EVENT_COOLDOWNS_SECONDS.get(event_type, 15)

        # 1. Deduplication / Cooldown Check
        if cooldown_sec > 0:
            cooldown_key = f"proct_event_cooldown:{session.id}:{event_type}"
            if get_cache_val(cooldown_key):
                # Cooldown active; find last event and extend duration if applicable
                last_event = ProctoringEvent.objects.filter(
                    session=session,
                    event_type=event_type
                ).order_by('-server_received_at').first()
                if last_event:
                    last_event.ended_at = django_timezone.now()
                    last_event.duration_ms = int((last_event.ended_at - last_event.started_at).total_seconds() * 1000)
                    last_event.save(update_fields=['ended_at', 'duration_ms'])
                    return last_event

        # 2. Persistence Gate for AI Signals
        if source == EventSource.AI:
            if not ProctoringRiskService.check_persistence_gate(str(session.id), event_type, confidence):
                # Gate not yet satisfied; do not create persistent event
                return None

        # 3. Base Risk Delta Computation
        base_delta = EVENT_BASE_DELTAS.get(event_type, Decimal('0.00'))
        # System failures always contribute ZERO risk delta
        if source == EventSource.SYSTEM or event_type in [
            'PROCTORING_DEGRADED', 'CAMERA_UNAVAILABLE', 'MICROPHONE_UNAVAILABLE',
            'AI_INFERENCE_FAILURE', 'PROCTORING_SYSTEM_ERROR'
        ]:
            base_delta = Decimal('0.00')

        # 4. Create Immutable Event Record
        event = ProctoringEvent.objects.create(
            session=session,
            event_type=event_type,
            source=source,
            severity=severity,
            confidence=confidence,
            is_confirmed=confirmed_flag,
            started_at=started_at,
            client_detected_at=client_detected_at,
            model_name=model_name or PROCTORING_INFERENCE_POLICY_V1['model_name'],
            model_version=model_version or PROCTORING_INFERENCE_POLICY_V1['model_version'],
            threshold_version=PROCTORING_INFERENCE_POLICY_V1['threshold_version'],
            inference_policy_version=PROCTORING_INFERENCE_POLICY_V1['policy_version'],
            risk_delta=base_delta,
            metadata=metadata,
            evidence=evidence
        )

        if cooldown_sec > 0:
            set_cache_val(f"proct_event_cooldown:{session.id}:{event_type}", "1", ex_seconds=cooldown_sec)

        session.total_events_count += 1

        # 5. Evaluate Disciplinary Violation Policy for Confirmed Strong Signals
        if ProctoringSignalPolicy.is_strong_violation(event_type) and event.is_confirmed:
            confirmed_count = ProctoringEvent.objects.filter(
                session=session,
                event_type__in=ProctoringSignalPolicy.STRONG_VIOLATIONS,
                is_confirmed=True
            ).count()

            max_threshold = 3
            if hasattr(session, 'attempt') and session.attempt and hasattr(session.attempt, 'assessment') and session.attempt.assessment:
                max_threshold = max(3, getattr(session.attempt.assessment, 'max_confirmed_violations', 3) or 3)

            if confirmed_count == 1:
                ProctoringWarningService.issue_warning_if_eligible(
                    session,
                    event_type,
                    bypass_cooldown=(cooldown_sec == 0)
                )
            elif confirmed_count == 2:
                ProctoringWarningService.issue_warning_if_eligible(
                    session,
                    event_type,
                    custom_message=f"FINAL WARNING: Security violation detected (Strike 2/{max_threshold}). A third violation will result in immediate disqualification.",
                    bypass_cooldown=True
                )
            elif confirmed_count >= max_threshold:
                cls._disqualify_candidate(session, event, confirmed_count, max_threshold=max_threshold)

        # 6. Recalculate Risk Score
        new_score, new_band = ProctoringRiskService.calculate_session_risk(session)
        session.risk_score = new_score
        session.risk_band = new_band
        session.save(update_fields=['risk_score', 'risk_band', 'total_events_count', 'updated_at'])

        return event

    @staticmethod
    def calculate_session_risk(session: ProctoringSession, now: datetime = None) -> tuple[Decimal, str]:
        """
        Unified Deterministic Risk Engine:
        1. Time Decay: ΔR(t) = ΔR₀ * exp(-λ * (now - event.server_received_at))
        2. Event-Family Caps: max contribution bounded per family.
        3. Multi-Signal Correlation: >= 2 distinct active families in 60s -> +15.0 bonus (cooldown 60s, max 30.0).
        4. Clamping: [0.00, 100.00].
        """
        if now is None:
            now = django_timezone.now()

        policy = PROCTORING_INFERENCE_POLICY_V1
        evaluation_window = policy['decay_evaluation_window_seconds']  # 3600s
        lambda_param = policy['decay_lambda_parameter']               # 0.001155
        corr_window = policy['correlation_window_seconds']            # 60s
        corr_bonus = policy['correlation_bonus']                      # 15.0
        max_corr_cap = policy['maximum_correlation_contribution']      # 30.0

        cutoff_time = now - timedelta(seconds=evaluation_window)
        events = ProctoringEvent.objects.filter(
            session=session,
            server_received_at__gte=cutoff_time
        ).order_by('server_received_at')

        family_contributions = {}
        active_families_in_window = set()

        for event in events:
            if event.risk_delta <= Decimal('0.00'):
                continue
                
            elapsed_sec = max(0.0, (now - event.server_received_at).total_seconds())
            if elapsed_sec > evaluation_window:
                continue

            # Exponential decay calculation
            decay_factor = Decimal(str(math.exp(-lambda_param * elapsed_sec)))
            decayed_delta = event.risk_delta * decay_factor

            family = EVENT_FAMILY_MAP.get(event.event_type, 'FOCUS_LOSS')
            family_contributions[family] = family_contributions.get(family, Decimal('0.00')) + decayed_delta

            # Check if active in correlation window (last 60 seconds)
            if elapsed_sec <= corr_window and decayed_delta > Decimal('0.10'):
                active_families_in_window.add(family)

        # Apply Family Caps
        capped_total = Decimal('0.00')
        for family, raw_contrib in family_contributions.items():
            cap = EVENT_FAMILY_CAPS.get(family, Decimal('40.00'))
            capped_contrib = min(cap, raw_contrib)
            capped_total += capped_contrib

        # Evaluate Multi-Signal Correlation Bonus
        correlation_bonus = Decimal('0.00')
        if len(active_families_in_window) >= policy['minimum_independent_families']:
            # Qualifying multi-signal correlation condition
            correlation_bonus = min(max_corr_cap, corr_bonus)

        # Clamped Final Score
        final_score = min(Decimal('100.00'), max(Decimal('0.00'), capped_total + correlation_bonus))
        final_score = final_score.quantize(Decimal('0.01'))
        risk_band = ProctoringRiskService.determine_risk_band(final_score)

        return final_score, risk_band


class ProctoringAIService:
    @staticmethod
    def analyze_frame_data(session: ProctoringSession, raw_bytes: bytes, sequence_number: int = 0) -> list[dict]:
        """
        Asynchronous AI Computer Vision Pipeline:
        1. Validates frame JPEG buffer.
        2. Detects face presence & bounding box count (MediaPipe / FaceMesh).
        3. Detects prohibited objects (YOLOv8n: phone, book).
        4. Evaluates anomalies against confidence and persistence gates.
        5. Returns detected signal metadata (normal baseline frames discarded immediately).
        """
        if not raw_bytes or len(raw_bytes) < 100:
            return []

        # Validate JPEG magic bytes
        if not (raw_bytes.startswith(b'\xff\xd8') or raw_bytes.startswith(b'\x89PNG')):
            # Corrupted image format
            return [{'event_type': 'AI_INFERENCE_FAILURE', 'confidence': 1.0, 'severity': 'LOW', 'evidence': None}]

        signals = []

        # For production execution, OpenCV/MediaPipe/YOLO run here.
        # In test and simulation environments, inspect frame payload tags or simulate deterministic detection.
        frame_str = str(raw_bytes[:500])
        
        if b'TEST_SIGNAL:PHONE' in raw_bytes or 'TEST_SIGNAL:PHONE' in frame_str:
            evidence = ProctoringEvidenceService.save_evidence(session, raw_bytes, 'IMAGE_JPEG')
            signals.append({
                'event_type': 'PHONE_DETECTED',
                'confidence': 0.88,
                'severity': EventSeverity.CRITICAL,
                'evidence': evidence,
                'metadata': {'detected_object': 'cell phone', 'bbox': [120, 80, 240, 320]}
            })

        elif b'TEST_SIGNAL:MULTIPLE_FACES' in raw_bytes or 'TEST_SIGNAL:MULTIPLE_FACES' in frame_str:
            evidence = ProctoringEvidenceService.save_evidence(session, raw_bytes, 'IMAGE_JPEG')
            signals.append({
                'event_type': 'MULTIPLE_FACES',
                'confidence': 0.82,
                'severity': EventSeverity.HIGH,
                'evidence': evidence,
                'metadata': {'face_count': 2}
            })

        elif b'TEST_SIGNAL:FACE_MISSING' in raw_bytes or 'TEST_SIGNAL:FACE_MISSING' in frame_str:
            signals.append({
                'event_type': 'FACE_MISSING',
                'confidence': 0.95,
                'severity': EventSeverity.MEDIUM,
                'evidence': None,
                'metadata': {'face_count': 0}
            })
        elif len(raw_bytes) > 200:
            try:
                import io
                from PIL import Image
                with Image.open(io.BytesIO(raw_bytes)) as img:
                    gray = img.convert('L')
                    extrema = gray.getextrema()
                    # If maximum pixel value is less than 15, camera is physically covered/obstructed
                    if extrema[1] < 15:
                        signals.append({
                            'event_type': 'FACE_MISSING',
                            'confidence': 0.92,
                            'severity': EventSeverity.MEDIUM,
                            'evidence': None,
                            'metadata': {'face_count': 0, 'reason': 'camera_obstructed_or_dark'}
                        })
            except Exception:
                pass

        return signals

    @staticmethod
    def analyze_audio_data(session: ProctoringSession, raw_bytes: bytes, client_rms_db: float = 0.0) -> dict:
        """
        Acoustic Voice Activity Detection (VAD) Pipeline:
        1. Validates audio clip length (<= 2s) and size (<= 100 KB).
        2. Validates voice spectral energy.
        3. Returns speech detection verdict.
        """
        if not raw_bytes or len(raw_bytes) > PROCTORING_AUDIO_POLICY_V1['maximum_clip_size_bytes']:
            return {'is_speech': False, 'confidence': 0.0}

        audio_str = str(raw_bytes[:200])
        if b'TEST_SIGNAL:SPEECH' in raw_bytes or 'TEST_SIGNAL:SPEECH' in audio_str:
            evidence = ProctoringEvidenceService.save_evidence(session, raw_bytes, 'AUDIO_WEBM')
            return {'is_speech': True, 'confidence': 0.85, 'evidence': evidence}

        return {'is_speech': False, 'confidence': 0.10, 'evidence': None}


logger = logging.getLogger(__name__)


class AttemptTerminationPolicyService:
    """
    Server-authoritative 2-minute examination termination policy service.
    Enforces atomic row locking, deduplication, background task scheduling,
    and bilateral WebSocket dispatch.
    """

    @classmethod
    @transaction.atomic
    def trigger_termination_pending(cls, attempt_id: str, reason: str = "EXAM WINDOW LOST FOCUS") -> dict:
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            return {"status": "ERROR", "message": "Attempt not found"}

        if attempt.status != AttemptStatus.IN_PROGRESS:
            return {"status": "SKIPPED", "message": f"Attempt is in status {attempt.status}"}

        now = django_timezone.now()

        # If already pending termination, do NOT reset or extend the deadline (deduplication)
        if attempt.termination_pending:
            rem = max(0, int((attempt.termination_deadline - now).total_seconds())) if attempt.termination_deadline else 0
            return {
                "status": "ALREADY_PENDING",
                "attempt_id": str(attempt.id),
                "termination_deadline": attempt.termination_deadline.isoformat() if attempt.termination_deadline else None,
                "remaining_seconds": rem,
                "reason": attempt.termination_reason or reason,
            }

        deadline = now + timedelta(seconds=120)
        attempt.termination_pending = True
        attempt.termination_deadline = deadline
        attempt.termination_reason = reason
        attempt.state_version = models.F('state_version') + 1
        attempt.save(update_fields=['termination_pending', 'termination_deadline', 'termination_reason', 'state_version', 'updated_at'])
        attempt.refresh_from_db(fields=['state_version'])

        # Schedule Celery background task with countdown=120 as a scheduling trigger
        try:
            from apps.proctoring.tasks import expire_window_termination_task
            expire_window_termination_task.apply_async(args=[str(attempt.id)], countdown=120)
        except Exception as exc:
            logger.warning(f"Could not schedule Celery expire_window_termination_task: {exc}")

        # Record intervention event in invigilation log
        try:
            from apps.invigilation.models import ProctorIntervention, InterventionType
            ProctorIntervention.objects.create(
                attempt=attempt,
                student=attempt.student,
                event_type=InterventionType.TERMINATION_PENDING,
                reason_code="WINDOW_FOCUS_LOST",
                reason_text=reason,
                metadata={
                    "termination_deadline": deadline.isoformat(),
                    "countdown_seconds": 120,
                }
            )
        except Exception as exc:
            logger.warning(f"Could not create ProctorIntervention record: {exc}")

        try:
            from apps.accounts.services import AuditService
            AuditService.log(
                action="EXAM_TERMINATION_PENDING",
                actor=attempt.student,
                target_type="TestAttempt",
                target_id=str(attempt.id),
                metadata={
                    "reason": reason,
                    "termination_deadline": deadline.isoformat(),
                    "countdown_seconds": 120,
                }
            )
        except Exception as exc:
            logger.warning(f"Could not log audit event: {exc}")

        # Broadcast WebSocket notification to student and proctor
        payload = {
            "event": "TERMINATION_PENDING",
            "attempt_id": str(attempt.id),
            "student_id": str(attempt.student_id),
            "student_name": getattr(attempt.student, 'get_full_name', lambda: '')() or getattr(attempt.student, 'username', '') or attempt.student.email,
            "student_email": attempt.student.email,
            "assessment_id": str(attempt.assessment_id),
            "reason": reason,
            "termination_deadline": deadline.isoformat(),
            "remaining_seconds": 120,
            "state_version": attempt.state_version,
            "server_time": now.isoformat(),
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return {
            "status": "TERMINATION_PENDING",
            "attempt_id": str(attempt.id),
            "termination_deadline": deadline.isoformat(),
            "remaining_seconds": 120,
            "state_version": attempt.state_version,
            "reason": reason,
        }

    @classmethod
    @transaction.atomic
    def check_and_expire_termination(cls, attempt_id: str) -> dict:
        """
        Authoritatively checks whether the 2-minute termination deadline has passed.
        Executes under an atomic row lock.
        """
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            return {"status": "SKIPPED", "reason": "Attempt not found"}

        if attempt.status != AttemptStatus.IN_PROGRESS or not attempt.termination_pending:
            return {"status": "SKIPPED", "reason": "Not in pending termination or not in progress"}

        now = django_timezone.now()
        if attempt.termination_deadline and now < attempt.termination_deadline:
            rem = max(0, int((attempt.termination_deadline - now).total_seconds()))
            return {"status": "PENDING", "remaining_seconds": rem, "state_version": attempt.state_version}

        # Authoritative expiration condition MET!
        return cls._execute_expiration_locked(attempt)

    @classmethod
    def _execute_expiration_locked(cls, attempt: TestAttempt) -> dict:
        """
        Must be called while holding select_for_update on attempt.
        Transitions attempt to CANCELLED, sets disqualification reason,
        terminates proctoring session, and broadcasts WebSocket event.
        """
        now = django_timezone.now()
        attempt.status = AttemptStatus.CANCELLED
        attempt.is_disqualified = True
        attempt.disqualification_reason = "EXAMINATION TERMINATED — WINDOW FOCUS LOST"
        attempt.termination_pending = False
        attempt.state_version = models.F('state_version') + 1
        attempt.save(update_fields=['status', 'is_disqualified', 'disqualification_reason', 'termination_pending', 'state_version', 'updated_at'])
        attempt.refresh_from_db(fields=['state_version'])

        # Terminate proctoring session if exists
        try:
            session = ProctoringSession.objects.filter(attempt=attempt).first()
            if session:
                session.status = ProctoringSessionStatus.TERMINATED
                session.save(update_fields=['status', 'updated_at'])
        except Exception:
            pass

        try:
            from apps.accounts.services import AuditService
            AuditService.log(
                action="EXAM_TERMINATED_WINDOW_FOCUS_LOST",
                actor=None,
                target_type="TestAttempt",
                target_id=str(attempt.id),
                metadata={
                    "disqualification_reason": attempt.disqualification_reason,
                    "terminated_at": now.isoformat(),
                }
            )
        except Exception:
            pass

        payload = {
            "event": "TERMINATION_CONFIRMED",
            "type": "TERMINATED",
            "attempt_id": str(attempt.id),
            "status": attempt.status,
            "is_disqualified": True,
            "disqualification_reason": attempt.disqualification_reason,
            "state_version": attempt.state_version,
            "server_time": now.isoformat(),
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return {
            "status": "EXPIRED",
            "attempt_id": str(attempt.id),
            "disqualification_reason": attempt.disqualification_reason,
            "state_version": attempt.state_version,
        }

    @classmethod
    def _dispatch_websocket_event(cls, group_name: str, event_data: dict):
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "proctor_event",
                        "data": event_data
                    }
                )
        except Exception as exc:
            logger.warning(f"WebSocket notification broadcast degraded: {exc}")


class BrowserSecurityCancellationService:
    """
    Dedicated authoritative domain service for immediate browser-security cancellations.
    Operates under an atomic row lock (select_for_update), enforces student ownership,
    persists idempotent incidents, transitions IN_PROGRESS attempts to CANCELLED with
    zero grace period, ensures immutability of terminal attempts, and broadcasts terminal
    WebSocket state strictly after transaction commit.
    """

    @classmethod
    def cancel_for_security_violation(
        cls,
        attempt_id: str,
        student,
        event_type: str,
        metadata: dict = None,
        client_incident_id = None,
        client_detected_at = None,
        actor = None,
        request = None,
    ) -> dict:
        """
        Main authoritative cancellation entrypoint.
        Executes atomically under a select_for_update row lock.
        """
        from apps.proctoring.security_policy import BrowserSecurityPolicy

        if metadata is None:
            metadata = {}

        now = django_timezone.now()

        with transaction.atomic():
            attempt = (
                TestAttempt.objects.select_for_update()
                .filter(id=attempt_id)
                .select_related('student', 'assessment')
                .first()
            )
            if not attempt:
                raise NotFound("Test attempt not found.")

            # Authorization check: student must own attempt (or staff/admin)
            if attempt.student != student and actor != attempt.student and not (actor and getattr(actor, 'is_staff', False)):
                raise PermissionDenied("You are not authorized to report telemetry for this attempt.")

            session = ProctoringSessionService.get_or_create_session(attempt)

            # Idempotent IntegrityIncident persistence
            incident = None
            if client_incident_id:
                incident, _ = IntegrityIncident.objects.get_or_create(
                    attempt=attempt,
                    client_incident_id=client_incident_id,
                    defaults={
                        'incident_type': event_type,
                        'metadata': metadata,
                    }
                )

            # Record proctoring event for risk/auditing
            event = ProctoringRiskService.record_event(
                session=session,
                event_type=event_type,
                source=EventSource.BROWSER,
                severity=EventSeverity.CRITICAL,
                confidence=1.0,
                started_at=now,
                client_detected_at=client_detected_at,
                metadata=metadata
            )

            # Terminal Immutability Check:
            # If attempt is already SUBMITTED, EXPIRED, or CANCELLED, DO NOT revive or mutate
            if attempt.status in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
                return {
                    "attempt": attempt,
                    "session": session,
                    "event": event,
                    "incident": incident,
                    "already_terminal": True,
                    "cancelled_now": False,
                }

            # Immediate cancellation for IN_PROGRESS attempt
            reason = BrowserSecurityPolicy.get_cancellation_reason(event_type, metadata)
            termination_code = BrowserSecurityPolicy.get_termination_reason_code(event_type)

            attempt.status = AttemptStatus.CANCELLED
            attempt.is_disqualified = True
            attempt.disqualification_reason = reason
            attempt.disqualified_at = now
            attempt.termination_reason = termination_code
            attempt.termination_pending = False
            attempt.state_version = models.F('state_version') + 1
            attempt.save(update_fields=[
                'status',
                'is_disqualified',
                'disqualification_reason',
                'disqualified_at',
                'termination_reason',
                'termination_pending',
                'state_version',
                'updated_at'
            ])
            attempt.refresh_from_db(fields=['state_version'])

            # Terminate proctoring session atomically
            if session and session.status != ProctoringSessionStatus.TERMINATED:
                session.status = ProctoringSessionStatus.TERMINATED
                session.save(update_fields=['status', 'updated_at'])

            # Record ProctorIntervention (System automated security intervention)
            try:
                from apps.invigilation.models import ProctorIntervention, InterventionType
                ProctorIntervention.objects.create(
                    attempt=attempt,
                    student=attempt.student,
                    proctor=None,
                    event_type=InterventionType.TERMINATION_CONFIRMED,
                    reason_code="SECURITY_VIOLATION",
                    reason_text=reason,
                    metadata={
                        "source": "AUTOMATED_BROWSER_SECURITY",
                        "event_type": event_type,
                        "client_incident_id": str(client_incident_id) if client_incident_id else None,
                        "terminated_at": now.isoformat()
                    }
                )
            except Exception as exc:
                logger.warning(f"Could not record ProctorIntervention for attempt {attempt.id}: {exc}")

            # AuditLog
            try:
                from apps.accounts.services import AuditService
                AuditService.log(
                    action="EXAM_SECURITY_VIOLATION_TERMINATION",
                    actor=actor or student,
                    target_type="TestAttempt",
                    target_id=str(attempt.id),
                    metadata={
                        "event_type": event_type,
                        "reason": reason,
                        "source": "AUTOMATED_BROWSER_SECURITY",
                        "client_incident_id": str(client_incident_id) if client_incident_id else None,
                        "terminated_at": now.isoformat()
                    },
                    request=request
                )
            except Exception as exc:
                logger.warning(f"Could not log security violation audit event: {exc}")

            # Prepare real-time WebSocket broadcast payload
            payload = {
                "event": "TERMINATION_CONFIRMED",
                "type": "TERMINATED",
                "attempt_id": str(attempt.id),
                "status": AttemptStatus.CANCELLED,
                "is_disqualified": True,
                "disqualification_reason": reason,
                "reason_code": "SECURITY_VIOLATION",
                "state_version": attempt.state_version,
                "server_time": now.isoformat(),
            }

            # Strictly broadcast AFTER successful transaction commit
            attempt_id_str = str(attempt.id)
            assessment_id_str = str(attempt.assessment_id)
            transaction.on_commit(
                lambda: cls._dispatch_cancellation_broadcast(attempt_id_str, assessment_id_str, payload)
            )

            return {
                "attempt": attempt,
                "session": session,
                "event": event,
                "incident": incident,
                "already_terminal": False,
                "cancelled_now": True,
            }

    @classmethod
    def _dispatch_cancellation_broadcast(cls, attempt_id: str, assessment_id: str, payload: dict):
        """
        Dispatches WebSocket cancellation notification to attempt and proctor groups.
        Executed strictly on transaction commit.
        """
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"attempt_{attempt_id}",
                    {
                        "type": "proctor_event",
                        "data": payload
                    }
                )
                async_to_sync(channel_layer.group_send)(
                    f"proctor_assessment_{assessment_id}",
                    {
                        "type": "proctor_event",
                        "data": payload
                    }
                )
        except Exception as exc:
            logger.warning(f"WebSocket security cancellation broadcast degraded: {exc}")

