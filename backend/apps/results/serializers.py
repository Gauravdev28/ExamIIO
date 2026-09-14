from typing import Optional
from decimal import Decimal
from rest_framework import serializers
from apps.accounts.models import User
from .models import (
    AssessmentResult,
    QuestionResult,
    ResultStatus,
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


class AdminCandidateReviewStudentSerializer(serializers.ModelSerializer):
    official_name = serializers.SerializerMethodField()
    roll_number = serializers.SerializerMethodField()
    euid = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'official_name', 'roll_number', 'euid']

    def get_official_name(self, obj):
        profile = getattr(obj, 'student_profile', None)
        if profile and profile.certificate_name:
            return profile.certificate_name
        return obj.display_name or obj.email

    def get_roll_number(self, obj):
        profile = getattr(obj, 'student_profile', None)
        return profile.roll_number if profile else ''

    def get_euid(self, obj):
        profile = getattr(obj, 'student_profile', None)
        return profile.euid if profile else ''


class AdminAssessmentResultAnswerReviewSerializer(serializers.ModelSerializer):
    student = AdminCandidateReviewStudentSerializer(read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    status = serializers.SerializerMethodField()
    proctoring_summary = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

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
            'total_questions',
            'answered_questions',
            'correct_questions',
            'partially_correct_questions',
            'incorrect_questions',
            'skipped_questions',
            'time_spent_seconds',
            'finalized_at',
            'proctoring_summary',
            'questions',
        ]
        read_only_fields = fields

    def get_status(self, obj: AssessmentResult):
        from apps.assessments.models import AttemptStatus
        att = obj.attempt
        proc = getattr(att, 'proctoring_session', None) if att else None
        if att and att.status == AttemptStatus.CANCELLED and proc and proc.status == 'TERMINATED':
            return 'DISQUALIFIED'
        elif obj.is_released:
            return 'RELEASED'
        elif obj.status in [ResultStatus.PENDING, ResultStatus.PROCESSING]:
            return 'EVALUATING'
        else:
            return 'EVALUATED'

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

    def get_questions(self, obj: AssessmentResult):
        snapshot = obj.assessment_snapshot
        server_bundle = (snapshot.server_evaluation_bundle or {}) if snapshot else {}
        server_questions = server_bundle.get('questions_eval', server_bundle.get('questions', {}))

        answers_by_qid = self.context.get('answers_by_qid', {})
        submissions_by_qid = self.context.get('submissions_by_qid', {})

        question_results = list(obj.question_results.all())
        question_results.sort(key=lambda qr: qr.snapshot_question.order if qr.snapshot_question else 0)

        serialized_questions = []

        for qr in question_results:
            sq = qr.snapshot_question
            if not sq:
                continue
            q_id = sq.snapshot_question_id
            eval_info = server_questions.get(q_id) or server_questions.get(str(q_id)) or {}
            correct_cfg = eval_info.get('correct_type_config', {})

            ans = answers_by_qid.get(q_id) or answers_by_qid.get(str(sq.id))
            code_sub = submissions_by_qid.get(q_id) or submissions_by_qid.get(str(sq.id))

            # 1. Student answer object
            student_answer = {
                'selected_options': (ans.selected_options or []) if (ans and ans.selected_options) else [],
                'text_response': ans.text_response if (ans and ans.text_response) else '',
                'code_response': ans.code_response if (ans and ans.code_response) else '',
                'code_language': ans.code_language if (ans and ans.code_language) else '',
                'sql_response': ans.sql_response if (ans and ans.sql_response) else '',
                'is_answered': ans.is_answered if ans else False,
            }

            if not student_answer['selected_options'] and qr.evaluation_details and 'user_selected' in qr.evaluation_details:
                student_answer['selected_options'] = qr.evaluation_details['user_selected']
            if not student_answer['text_response'] and qr.evaluation_details and 'user_text' in qr.evaluation_details:
                student_answer['text_response'] = qr.evaluation_details['user_text']
            if not student_answer['sql_response'] and qr.evaluation_details and 'sql_query' in qr.evaluation_details:
                student_answer['sql_response'] = qr.evaluation_details['sql_query']

            if not student_answer['is_answered'] and not qr.is_skipped:
                student_answer['is_answered'] = bool(
                    student_answer['selected_options']
                    or student_answer['text_response']
                    or student_answer['code_response']
                    or student_answer['sql_response']
                )

            # 2. Correct answer object
            correct_answer = {}
            q_type = sq.question_type

            if q_type in ['MCQ', 'MULTI_SELECT', 'TRUE_FALSE']:
                raw_options = sq.type_config.get('options', [])
                correct_opts = correct_cfg.get('correct_options', [])
                if not correct_opts and 'options' in correct_cfg:
                    correct_opts = [opt['id'] for opt in correct_cfg['options'] if opt.get('is_correct')]
                correct_opt_set = set(map(str, correct_opts))
                user_selected_set = set(map(str, student_answer['selected_options']))

                options_list = []
                for opt in raw_options:
                    opt_id_str = str(opt.get('id', ''))
                    options_list.append({
                        'id': opt.get('id'),
                        'text': opt.get('text', ''),
                        'is_correct': opt_id_str in correct_opt_set,
                        'is_selected': opt_id_str in user_selected_set,
                    })

                correct_answer = {
                    'options': options_list,
                    'correct_options': list(correct_opt_set),
                }

            elif q_type == 'SHORT_ANSWER':
                correct_answer = {
                    'exact_matches': correct_cfg.get('exact_matches', []),
                    'case_sensitive': correct_cfg.get('case_sensitive', False),
                }

            elif q_type == 'CODING':
                server_coding_eval = eval_info.get('server_coding_eval', {})
                all_tcs = server_coding_eval.get('all_test_cases', [])
                tc_summary = []
                for tc in all_tcs:
                    item = {
                        'index': tc.get('execution_order', 1),
                        'is_hidden': tc.get('is_hidden', False),
                        'points': tc.get('points', 0),
                    }
                    if not tc.get('is_hidden'):
                        item['input_data'] = tc.get('input_data')
                        item['expected_output'] = tc.get('expected_output')
                    tc_summary.append(item)
                correct_answer = {
                    'test_cases': tc_summary,
                }

            elif q_type == 'SQL':
                server_sql_eval = eval_info.get('server_sql_eval', {})
                correct_answer = {
                    'schema_setup_sql': server_sql_eval.get('schema_setup_sql') or (sq.sql_config or {}).get('schema_setup_sql', ''),
                    'expected_result_definition': server_sql_eval.get('expected_result_definition', ''),
                    'allowed_dialect': server_sql_eval.get('allowed_dialect', (sq.sql_config or {}).get('allowed_dialect', 'MYSQL')),
                }

            # 3. Code submission details if CODING or SQL
            code_submission_data = None
            if code_sub:
                tc_results = []
                for tcr in code_sub.test_case_results.all():
                    tc_item = {
                        'index': tcr.test_case_index,
                        'is_hidden': tcr.is_hidden,
                        'verdict': tcr.verdict,
                        'points_awarded': str(tcr.points_awarded),
                        'max_points': str(tcr.max_points),
                        'execution_time_ms': tcr.execution_time_ms,
                        'memory_used_kb': tcr.memory_used_kb,
                    }
                    if not tcr.is_hidden:
                        tc_item['public_input'] = tcr.public_input
                        tc_item['expected_output'] = tcr.expected_output
                        tc_item['actual_output'] = tcr.actual_output
                        tc_item['error_message'] = tcr.error_message
                    tc_results.append(tc_item)

                code_submission_data = {
                    'source_code': code_sub.source_code,
                    'language': code_sub.language,
                    'verdict': code_sub.verdict,
                    'passed_test_cases': code_sub.passed_test_cases,
                    'total_test_cases': code_sub.total_test_cases,
                    'execution_time_ms': code_sub.execution_time_ms,
                    'memory_used_kb': code_sub.memory_used_kb,
                    'compilation_error': code_sub.compilation_error or '',
                    'test_cases': tc_results,
                }
            elif q_type == 'CODING' and student_answer['code_response']:
                code_submission_data = {
                    'source_code': student_answer['code_response'],
                    'language': student_answer['code_language'] or 'PYTHON',
                    'verdict': qr.evaluation_details.get('verdict') if qr.evaluation_details else None,
                    'passed_test_cases': qr.evaluation_details.get('passed_test_cases', 0) if qr.evaluation_details else 0,
                    'total_test_cases': qr.evaluation_details.get('total_test_cases', 0) if qr.evaluation_details else 0,
                    'execution_time_ms': qr.evaluation_details.get('execution_time_ms', 0) if qr.evaluation_details else 0,
                    'memory_used_kb': qr.evaluation_details.get('memory_used_kb', 0) if qr.evaluation_details else 0,
                    'compilation_error': '',
                    'test_cases': [],
                }
            elif q_type == 'SQL' and (student_answer['sql_response'] or (qr.evaluation_details and qr.evaluation_details.get('sql_query'))):
                code_submission_data = {
                    'source_code': student_answer['sql_response'] or (qr.evaluation_details.get('sql_query', '') if qr.evaluation_details else ''),
                    'language': 'SQL',
                    'verdict': qr.evaluation_details.get('verdict') if qr.evaluation_details else None,
                    'passed_test_cases': 1 if qr.is_correct else 0,
                    'total_test_cases': 1,
                    'execution_time_ms': qr.evaluation_details.get('execution_time_ms', 0) if qr.evaluation_details else 0,
                    'memory_used_kb': 0,
                    'compilation_error': qr.evaluation_details.get('error_message') or '' if (qr.evaluation_details and not qr.is_correct) else '',
                    'test_cases': [],
                }

            q_obj = {
                'snapshot_question_id': sq.snapshot_question_id,
                'question_id': sq.snapshot_question_id,
                'order': sq.order,
                'title': sq.title,
                'description': sq.description,
                'instructions': sq.instructions,
                'question_type': sq.question_type,
                'difficulty': sq.difficulty,
                'points': sq.points,
                'earned_points': str(qr.earned_points),
                'max_points': str(qr.max_points),
                'is_correct': qr.is_correct,
                'is_partially_correct': qr.is_partially_correct,
                'is_skipped': qr.is_skipped,
                'negative_marking_enabled': sq.negative_marking_enabled,
                'negative_points': sq.negative_points,
                'tags': sq.tags or [],
                'student_answer': student_answer,
                'correct_answer': correct_answer,
                'evaluation_details': qr.evaluation_details or {},
                'time_spent_seconds': qr.time_spent_seconds,
                'code_submission': code_submission_data,
            }
            serialized_questions.append(q_obj)

        return serialized_questions


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

