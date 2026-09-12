from django.utils import timezone
from rest_framework import serializers
from apps.assessments.models import AttemptStatus
from apps.invigilation.models import ProctorReattemptAuthorization
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    ProctoringReview,
)


class StudentProctoringSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    frame_sampling_interval_seconds = serializers.SerializerMethodField()
    heartbeat_interval_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'status',
            'frame_sampling_interval_seconds',
            'heartbeat_interval_seconds',
            'created_at',
        ]
        read_only_fields = ['session_id', 'status', 'created_at']

    def get_frame_sampling_interval_seconds(self, obj):
        return 2.0

    def get_heartbeat_interval_seconds(self, obj):
        return 15.0


class StudentProctoringEventIngestSerializer(serializers.Serializer):
    client_incident_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    client_event_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    event_type = serializers.CharField(max_length=64)
    client_detected_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        # Normalize client_event_id to client_incident_id for single internal identity
        if not attrs.get('client_incident_id') and attrs.get('client_event_id'):
            attrs['client_incident_id'] = attrs['client_event_id']
        return attrs

    def validate_event_type(self, value):
        from apps.proctoring.security_policy import BrowserSecurityPolicy
        if not BrowserSecurityPolicy.is_valid_event_type(value):
            raise serializers.ValidationError(f"Invalid client event type: '{value}'.")
        return value


class StudentProctoringFrameUploadSerializer(serializers.Serializer):
    frame = serializers.FileField(required=True)
    sequence_number = serializers.IntegerField(required=False, default=0)

    def validate_frame(self, value):
        # 300 KB max frame size
        if value.size > 300 * 1024:
            raise serializers.ValidationError("Frame image size exceeds 300 KB limit.")
        return value


class StudentProctoringAudioUploadSerializer(serializers.Serializer):
    audio = serializers.FileField(required=True)
    rms_db = serializers.FloatField(required=False, default=0.0)

    def validate_audio(self, value):
        # 100 KB max audio snippet size
        if value.size > 100 * 1024:
            raise serializers.ValidationError("Audio snippet size exceeds 100 KB limit.")
        return value


class ProctoringWarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctoringWarning
        fields = [
            'id',
            'warning_type',
            'message',
            'issued_at',
            'acknowledged_at',
        ]
        read_only_fields = ['id', 'warning_type', 'message', 'issued_at']


class ReattemptSerializerMixin:
    def get_is_already_reattempt(self, obj):
        att = getattr(obj, 'attempt', None)
        if not att:
            return False
        return bool(hasattr(att, 'reattempt_origin') and att.reattempt_origin is not None)

    def _get_reattempt_auth(self, obj):
        if not hasattr(obj, '_cached_reattempt_auth'):
            att = getattr(obj, 'attempt', None)
            if not att or not getattr(att, 'assessment', None) or not getattr(att, 'student', None):
                obj._cached_reattempt_auth = None
            else:
                obj._cached_reattempt_auth = ProctorReattemptAuthorization.objects.filter(
                    assessment=att.assessment,
                    student=att.student
                ).select_related('new_attempt').first()
        return obj._cached_reattempt_auth

    def get_can_grant_reattempt(self, obj):
        att = getattr(obj, 'attempt', None)
        if not att:
            return False
        auth = self._get_reattempt_auth(obj)
        is_cancelled = (att.status == AttemptStatus.CANCELLED)
        is_already_reattempt = bool(hasattr(att, 'reattempt_origin') and att.reattempt_origin is not None)
        return is_cancelled and not is_already_reattempt and auth is None

    def get_reattempt(self, obj):
        auth = self._get_reattempt_auth(obj)
        if not auth:
            return None
        now = timezone.now()
        rem_sec = max(0, int((auth.available_at - now).total_seconds())) if auth.available_at else 0
        return {
            "id": str(auth.id),
            "status": auth.status,
            "authorized_at": auth.authorized_at.isoformat() if auth.authorized_at else None,
            "available_at": auth.available_at.isoformat() if auth.available_at else None,
            "remaining_seconds": rem_sec,
            "reason": auth.reason,
            "note": auth.note,
            "new_attempt_id": str(auth.new_attempt_id) if auth.new_attempt_id else None,
            "new_attempt_number": auth.new_attempt.attempt_number if auth.new_attempt else 2,
        }


class AdminProctoringSessionListSerializer(ReattemptSerializerMixin, serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    attempt_number = serializers.IntegerField(source='attempt.attempt_number', read_only=True)
    assessment_title = serializers.CharField(source='attempt.assessment.title', read_only=True)
    attempt_status = serializers.SerializerMethodField()
    latest_violation = serializers.SerializerMethodField()
    latest_violation_at = serializers.SerializerMethodField()
    violation_count = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    termination_pending = serializers.BooleanField(source='attempt.termination_pending', read_only=True)
    termination_deadline = serializers.DateTimeField(source='attempt.termination_deadline', read_only=True)
    termination_reason = serializers.CharField(source='attempt.termination_reason', read_only=True)
    termination_remaining_seconds = serializers.SerializerMethodField()
    is_disqualified = serializers.BooleanField(source='attempt.is_disqualified', read_only=True)
    disqualification_reason = serializers.CharField(source='attempt.disqualification_reason', read_only=True)
    is_already_reattempt = serializers.SerializerMethodField()
    can_grant_reattempt = serializers.SerializerMethodField()
    reattempt = serializers.SerializerMethodField()

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'attempt_id',
            'attempt_number',
            'assessment_title',
            'student',
            'status',
            'attempt_status',
            'latest_violation',
            'latest_violation_at',
            'violation_count',
            'risk_score',
            'risk_band',
            'total_events_count',
            'total_warnings_count',
            'review_status',
            'termination_pending',
            'termination_deadline',
            'termination_reason',
            'termination_remaining_seconds',
            'is_disqualified',
            'disqualification_reason',
            'is_already_reattempt',
            'can_grant_reattempt',
            'reattempt',
            'created_at',
            'updated_at',
        ]

    def get_attempt_status(self, obj):
        att = obj.attempt
        if att.is_disqualified:
            return 'DISQUALIFIED'
        if att.status == AttemptStatus.CANCELLED:
            return 'DISQUALIFIED' if (att.is_disqualified or 'DISQUALIFIED' in (att.disqualification_reason or '').upper()) else 'CANCELLED'
        return att.status

    def get_termination_remaining_seconds(self, obj):
        att = obj.attempt
        if att.termination_pending and att.termination_deadline:
            now = timezone.now()
            return max(0, int((att.termination_deadline - now).total_seconds()))
        return None

    def get_violation_count(self, obj):
        events = list(obj.events.all())
        if events:
            confirmed = [e for e in events if getattr(e, 'is_confirmed', True) and e.source in ['BROWSER', 'AI']]
            if confirmed:
                return len(confirmed)
        return obj.total_warnings_count

    def get_latest_violation(self, obj):
        events = sorted(list(obj.events.all()), key=lambda e: e.server_received_at or e.started_at, reverse=True)
        for ev in events:
            if ev.event_type in ['TAB_SWITCH', 'FULLSCREEN_EXIT', 'WINDOW_BLUR', 'PHONE_DETECTED', 'MULTIPLE_FACES', 'FACE_MISSING', 'HEAD_TURN_PROLONGED']:
                return ev.event_type.replace('_', ' ').title()
        warnings = sorted(list(obj.warnings.all()), key=lambda w: w.issued_at, reverse=True)
        if warnings:
            return warnings[0].warning_type.replace('_', ' ').title()
        return None

    def get_latest_violation_at(self, obj):
        events = sorted(list(obj.events.all()), key=lambda e: e.server_received_at or e.started_at, reverse=True)
        for ev in events:
            if ev.event_type in ['TAB_SWITCH', 'FULLSCREEN_EXIT', 'WINDOW_BLUR', 'PHONE_DETECTED', 'MULTIPLE_FACES', 'FACE_MISSING', 'HEAD_TURN_PROLONGED']:
                dt = ev.server_received_at or ev.started_at
                return dt.isoformat() if dt else None
        warnings = sorted(list(obj.warnings.all()), key=lambda w: w.issued_at, reverse=True)
        if warnings and warnings[0].issued_at:
            return warnings[0].issued_at.isoformat()
        return None

    def get_student(self, obj):
        student_user = obj.attempt.student
        profile = getattr(student_user, 'student_profile', None)
        return {
            'id': str(student_user.id),
            'email': student_user.email,
            'euid': getattr(profile, 'euid', ''),
            'roll_number': getattr(profile, 'roll_number', ''),
            'full_name': getattr(profile, 'full_name', '') or student_user.email,
        }


class AdminProctoringEventSerializer(serializers.ModelSerializer):
    evidence_id = serializers.UUIDField(source='evidence.id', read_only=True, allow_null=True)

    class Meta:
        model = ProctoringEvent
        fields = [
            'id',
            'event_type',
            'source',
            'severity',
            'confidence',
            'started_at',
            'ended_at',
            'duration_ms',
            'client_detected_at',
            'server_received_at',
            'model_name',
            'model_version',
            'threshold_version',
            'inference_policy_version',
            'risk_delta',
            'is_confirmed',
            'metadata',
            'evidence_id',
        ]


class AdminProctoringReviewSerializer(serializers.ModelSerializer):
    reviewed_by = serializers.CharField(source='reviewer.email', read_only=True)

    class Meta:
        model = ProctoringReview
        fields = [
            'id',
            'decision',
            'notes',
            'reviewed_by',
            'reviewed_at',
        ]
        read_only_fields = ['id', 'reviewed_by', 'reviewed_at']


class AdminProctoringSessionDetailSerializer(ReattemptSerializerMixin, serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    attempt_number = serializers.IntegerField(source='attempt.attempt_number', read_only=True)
    assessment_title = serializers.CharField(source='attempt.assessment.title', read_only=True)
    attempt_status = serializers.SerializerMethodField()
    latest_violation = serializers.SerializerMethodField()
    latest_violation_at = serializers.SerializerMethodField()
    violation_count = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    events = AdminProctoringEventSerializer(many=True, read_only=True)
    warnings = ProctoringWarningSerializer(many=True, read_only=True)
    review = AdminProctoringReviewSerializer(read_only=True)
    termination_pending = serializers.BooleanField(source='attempt.termination_pending', read_only=True)
    termination_deadline = serializers.DateTimeField(source='attempt.termination_deadline', read_only=True)
    termination_reason = serializers.CharField(source='attempt.termination_reason', read_only=True)
    termination_remaining_seconds = serializers.SerializerMethodField()
    is_disqualified = serializers.BooleanField(source='attempt.is_disqualified', read_only=True)
    disqualification_reason = serializers.CharField(source='attempt.disqualification_reason', read_only=True)
    is_already_reattempt = serializers.SerializerMethodField()
    can_grant_reattempt = serializers.SerializerMethodField()
    reattempt = serializers.SerializerMethodField()

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'attempt_id',
            'attempt_number',
            'assessment_title',
            'student',
            'status',
            'attempt_status',
            'latest_violation',
            'latest_violation_at',
            'violation_count',
            'risk_score',
            'risk_band',
            'total_events_count',
            'total_warnings_count',
            'review_status',
            'termination_pending',
            'termination_deadline',
            'termination_reason',
            'termination_remaining_seconds',
            'is_disqualified',
            'disqualification_reason',
            'is_already_reattempt',
            'can_grant_reattempt',
            'reattempt',
            'events',
            'warnings',
            'review',
            'created_at',
            'updated_at',
        ]

    def get_attempt_status(self, obj):
        att = obj.attempt
        if att.is_disqualified:
            return 'DISQUALIFIED'
        if att.status == AttemptStatus.CANCELLED:
            return 'DISQUALIFIED' if (att.is_disqualified or 'DISQUALIFIED' in (att.disqualification_reason or '').upper()) else 'CANCELLED'
        return att.status

    def get_termination_remaining_seconds(self, obj):
        att = obj.attempt
        if att.termination_pending and att.termination_deadline:
            now = timezone.now()
            return max(0, int((att.termination_deadline - now).total_seconds()))
        return None

    def get_violation_count(self, obj):
        events = list(obj.events.all())
        if events:
            confirmed = [e for e in events if getattr(e, 'is_confirmed', True) and e.source in ['BROWSER', 'AI']]
            if confirmed:
                return len(confirmed)
        return obj.total_warnings_count

    def get_latest_violation(self, obj):
        events = sorted(list(obj.events.all()), key=lambda e: e.server_received_at or e.started_at, reverse=True)
        for ev in events:
            if ev.event_type in ['TAB_SWITCH', 'FULLSCREEN_EXIT', 'WINDOW_BLUR', 'PHONE_DETECTED', 'MULTIPLE_FACES', 'FACE_MISSING', 'HEAD_TURN_PROLONGED']:
                return ev.event_type.replace('_', ' ').title()
        warnings = sorted(list(obj.warnings.all()), key=lambda w: w.issued_at, reverse=True)
        if warnings:
            return warnings[0].warning_type.replace('_', ' ').title()
        return None

    def get_latest_violation_at(self, obj):
        events = sorted(list(obj.events.all()), key=lambda e: e.server_received_at or e.started_at, reverse=True)
        for ev in events:
            if ev.event_type in ['TAB_SWITCH', 'FULLSCREEN_EXIT', 'WINDOW_BLUR', 'PHONE_DETECTED', 'MULTIPLE_FACES', 'FACE_MISSING', 'HEAD_TURN_PROLONGED']:
                dt = ev.server_received_at or ev.started_at
                return dt.isoformat() if dt else None
        warnings = sorted(list(obj.warnings.all()), key=lambda w: w.issued_at, reverse=True)
        if warnings and warnings[0].issued_at:
            return warnings[0].issued_at.isoformat()
        return None

    def get_student(self, obj):
        student_user = obj.attempt.student
        profile = getattr(student_user, 'student_profile', None)
        return {
            'id': str(student_user.id),
            'email': student_user.email,
            'euid': getattr(profile, 'euid', ''),
            'roll_number': getattr(profile, 'roll_number', ''),
            'full_name': getattr(profile, 'full_name', '') or student_user.email,
        }
