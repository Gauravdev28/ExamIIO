from typing import Optional
from decimal import Decimal
from rest_framework import serializers
from apps.accounts.models import User
from .models import (
    AssessmentResult,
    QuestionResult,
    HistoricalResultSummary,
    ReportJob,
    ReportType,
    ReportFormat,
    ReportStatus,
    Certificate,
    CertificateStatus,
)


class QuestionResultStudentSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source='snapshot_question.order', read_only=True)
    title = serializers.CharField(source='snapshot_question.title', read_only=True)
    coins_awarded = serializers.SerializerMethodField()

    class Meta:
        model = QuestionResult
        fields = [
            'id',
            'question_id',
            'order',
            'title',
            'question_type',
            'earned_points',
            'max_points',
            'is_correct',
            'is_partially_correct',
            'is_skipped',
            'coins_awarded',
            'evaluation_details',
            'time_spent_seconds',
        ]
        read_only_fields = fields

    def get_coins_awarded(self, obj: QuestionResult) -> int:
        return 3 if obj.is_correct else 0


class QuestionResultAdminSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source='snapshot_question.order', read_only=True)
    title = serializers.CharField(source='snapshot_question.title', read_only=True)
    tags = serializers.JSONField(source='snapshot_question.tags', read_only=True)

    class Meta:
        model = QuestionResult
        fields = [
            'id',
            'question_id',
            'order',
            'title',
            'question_type',
            'earned_points',
            'max_points',
            'is_correct',
            'is_partially_correct',
            'is_skipped',
            'evaluation_details',
            'time_spent_seconds',
            'tags',
        ]
        read_only_fields = fields


class AssessmentResultStudentDetailSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    question_results = QuestionResultStudentSerializer(many=True, read_only=True)
    coins_earned = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentResult
        fields = [
            'id',
            'attempt_id',
            'assessment_id',
            'assessment_title',
            'status',
            'total_score_earned',
            'total_possible_score',
            'percentage',
            'is_passed',
            'total_questions',
            'answered_questions',
            'correct_questions',
            'partially_correct_questions',
            'incorrect_questions',
            'skipped_questions',
            'coins_earned',
            'time_spent_seconds',
            'finalized_at',
            'question_results',
        ]
        read_only_fields = fields

    def get_coins_earned(self, obj: AssessmentResult) -> int:
        from .models import StudentCoinLedger
        from django.db.models import Sum
        val = StudentCoinLedger.objects.filter(attempt_id=obj.attempt_id).aggregate(total=Sum('coins_awarded'))['total']
        return val if val is not None else (obj.correct_questions * 3)


class StudentCoinLedgerSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='attempt.assessment.title', read_only=True)

    class Meta:
        from .models import StudentCoinLedger
        model = StudentCoinLedger
        fields = [
            'id',
            'attempt_id',
            'assessment_title',
            'question_id',
            'coins_awarded',
            'awarded_at',
            'reason',
        ]
        read_only_fields = fields


class StudentBasicSerializer(serializers.ModelSerializer):
    roll_number = serializers.SerializerMethodField()
    euid = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'roll_number', 'euid']

    def get_roll_number(self, obj):
        return getattr(obj.student_profile, 'roll_number', '') if hasattr(obj, 'student_profile') else ''

    def get_euid(self, obj):
        return getattr(obj.student_profile, 'euid', '') if hasattr(obj, 'student_profile') else ''

    def get_full_name(self, obj):
        return obj.email


class AssessmentResultAdminListSerializer(serializers.ModelSerializer):
    student = StudentBasicSerializer(read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    proctoring_summary = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentResult
        fields = [
            'id',
            'attempt_id',
            'student',
            'status',
            'total_score_earned',
            'total_possible_score',
            'percentage',
            'is_passed',
            'is_released',
            'time_spent_seconds',
            'finalized_at',
            'proctoring_summary',
        ]
        read_only_fields = fields

    def get_proctoring_summary(self, obj: AssessmentResult):
        if hasattr(obj.attempt, 'proctoring_session') and obj.attempt.proctoring_session:
            ps = obj.attempt.proctoring_session
            return {
                'risk_score': str(ps.risk_score),
                'risk_band': ps.risk_band,
                'status': ps.status
            }
        return None


class AssessmentResultAdminDetailSerializer(serializers.ModelSerializer):
    student = StudentBasicSerializer(read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    question_results = QuestionResultAdminSerializer(many=True, read_only=True)
    proctoring_summary = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentResult
        fields = [
            'id',
            'attempt_id',
            'assessment_id',
            'assessment_title',
            'student',
            'status',
            'total_score_earned',
            'total_possible_score',
            'percentage',
            'is_passed',
            'is_released',
            'total_questions',
            'answered_questions',
            'correct_questions',
            'partially_correct_questions',
            'incorrect_questions',
            'skipped_questions',
            'time_spent_seconds',
            'finalized_at',
            'question_results',
            'proctoring_summary',
        ]
        read_only_fields = fields

    def get_proctoring_summary(self, obj: AssessmentResult):
        if hasattr(obj.attempt, 'proctoring_session') and obj.attempt.proctoring_session:
            ps = obj.attempt.proctoring_session
            return {
                'risk_score': str(ps.risk_score),
                'risk_band': ps.risk_band,
                'review_status': ps.review_status,
                'status': ps.status
            }
        return None


class HistoricalResultSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalResultSummary
        fields = [
            'id',
            'assessment_id',
            'assessment_title_snapshot',
            'total_score_earned',
            'total_possible_score',
            'percentage',
            'is_passed',
            'completion_status',
            'started_at',
            'completed_at',
            'details_purged',
        ]
        read_only_fields = fields


class CreateReportJobSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    format = serializers.ChoiceField(choices=ReportFormat.choices)
    assessment_id = serializers.UUIDField(required=False, allow_null=True)
    student_id = serializers.UUIDField(required=False, allow_null=True)


class ReportJobDetailSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportJob
        fields = [
            'id',
            'report_type',
            'format',
            'status',
            'file_size_bytes',
            'sha256_hash',
            'error_message',
            'download_url',
            'expires_at',
            'created_at',
            'completed_at',
        ]
        read_only_fields = fields

    def get_download_url(self, obj: ReportJob):
        if obj.status == ReportStatus.COMPLETED:
            return f"/api/v1/admin/reports/{obj.id}/download/"
        return None


class CertificateSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    student_name = serializers.CharField(source='student.display_name', read_only=True)
    student_roll_number = serializers.SerializerMethodField()
    attempt_number = serializers.IntegerField(source='attempt.attempt_number', read_only=True)
    has_pdf = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_id',
            'exam_id',
            'exam_title',
            'student_id',
            'student_email',
            'student_name',
            'student_roll_number',
            'attempt_id',
            'attempt_number',
            'printed_name',
            'status',
            'issued_at',
            'has_pdf',
            'download_url',
            'verification_url',
            'created_at',
        ]
        read_only_fields = fields

    def get_student_roll_number(self, obj: Certificate) -> str:
        profile = getattr(obj.student, 'student_profile', None)
        return getattr(profile, 'roll_number', '') if profile else ''

    def get_has_pdf(self, obj: Certificate) -> bool:
        return bool(obj.pdf_file and obj.status == CertificateStatus.ISSUED)

    def get_download_url(self, obj: Certificate) -> Optional[str]:
        if obj.pdf_file and obj.status == CertificateStatus.ISSUED:
            # Context-aware URL or student/admin endpoint
            request = self.context.get('request')
            if request and getattr(request.user, 'role', None) in ['ADMIN', 'SUPERADMIN']:
                return f"/api/v1/admin/certificates/{obj.id}/download/"
            return f"/api/v1/student/certificates/{obj.id}/download/"
        return None


class PublicCertificateVerificationSerializer(serializers.Serializer):
    certificate_id = serializers.CharField()
    printed_name = serializers.CharField()
    exam_title = serializers.CharField(source='exam.title')
    organization_name = serializers.CharField(default="Craft Society")
    issued_at = serializers.DateTimeField()
    status = serializers.CharField()
    is_valid = serializers.SerializerMethodField()

    def get_is_valid(self, obj: Certificate) -> bool:
        return obj.status == CertificateStatus.ISSUED

