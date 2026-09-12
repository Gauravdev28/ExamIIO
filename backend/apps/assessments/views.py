import math
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.models import User, Role
from apps.accounts.services import StudentService
from apps.accounts.permissions import IsAdmin, IsActiveUser, IsStudent, IsFirstLoginSatisfied
from apps.core.views import APIResponse
from apps.questions.models import Question, QuestionVersion, VersionStatus
from .models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from .services import (
    AssessmentService,
    AttemptService,
    AttemptTimerService,
    AssessmentAudienceService,
    AssessmentAttendanceService,
)
from .serializers import (
    AssessmentAdminListSerializer,
    AssessmentAdminDetailSerializer,
    CreateAssessmentSerializer,
    UpdateAssessmentSerializer,
    AddQuestionToAssessmentSerializer,
    AssessmentAssignmentSerializer,
    AssignStudentsPayloadSerializer,
    StudentAssessmentListSerializer,
    StudentAttemptAnswerSerializer,
    SaveAnswerPayloadSerializer,
    ConfigureAudienceSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return APIResponse(
            data={
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        )


# ==============================================================================
# Admin Assessment Management Views
# ==============================================================================

class AdminAssessmentListView(APIView):
    """
    List & Create Assessments.
    GET /api/v1/admin/assessments/
    POST /api/v1/admin/assessments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Assessment.objects.prefetch_related('assessment_questions', 'assignments').select_related('created_by').all()

        # Status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search.strip()) |
                Q(description__icontains=search.strip())
            )

        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'start_datetime', '-start_datetime', 'title', '-title']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AssessmentAdminListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assessment = AssessmentService.create_assessment(
            title=data['title'],
            description=data['description'],
            instructions=data.get('instructions', ''),
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            duration_minutes=data['duration_minutes'],
            total_points=data.get('total_points', 0),
            passing_percentage=data.get('passing_percentage', 0.00),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            attempt_limit=data.get('attempt_limit', 1),
            randomize_questions=data.get('randomize_questions', False),
            randomize_options=data.get('randomize_options', False),
            result_visibility=data.get('result_visibility', 'AFTER_DEADLINE'),
            created_by=request.user,
            request=request
        )

        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Assessment created successfully in DRAFT status.",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentDetailView(APIView):
    """
    Retrieve, Update, or Delete an Assessment.
    GET /api/v1/admin/assessments/<id>/
    PATCH /api/v1/admin/assessments/<id>/
    DELETE /api/v1/admin/assessments/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.prefetch_related(
                'assessment_questions__question_version__tags',
                'assignments__student__student_profile'
            ).select_related('created_by'),
            id=pk
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Assessment details retrieved."
        )

    def patch(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = UpdateAssessmentSerializer(instance=assessment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated = AssessmentService.update_draft_assessment(
            assessment=assessment,
            actor=request.user,
            title=data.get('title'),
            description=data.get('description'),
            instructions=data.get('instructions'),
            start_datetime=data.get('start_datetime'),
            end_datetime=data.get('end_datetime'),
            duration_minutes=data.get('duration_minutes'),
            total_points=data.get('total_points'),
            passing_percentage=data.get('passing_percentage'),
            negative_marking_enabled=data.get('negative_marking_enabled'),
            attempt_limit=data.get('attempt_limit'),
            randomize_questions=data.get('randomize_questions'),
            randomize_options=data.get('randomize_options'),
            target_section_ids=data.get('target_section_ids'),
            target_student_ids=data.get('target_student_ids'),
            target_all_students=data.get('target_all_students'),
            proctoring_enabled=data.get('proctoring_enabled'),
            camera_required=data.get('camera_required'),
            phone_detection_enabled=data.get('phone_detection_enabled'),
            face_detection_enabled=data.get('face_detection_enabled'),
            multiple_face_detection_enabled=data.get('multiple_face_detection_enabled'),
            gaze_detection_enabled=data.get('gaze_detection_enabled'),
            head_movement_detection_enabled=data.get('head_movement_detection_enabled'),
            max_confirmed_violations=data.get('max_confirmed_violations'),
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(updated).data,
            message="Assessment updated successfully."
        )

    def delete(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        if assessment.status in [AssessmentStatus.PUBLISHED, AssessmentStatus.ARCHIVED]:
            return APIResponse(
                error={"message": "Cannot delete a published or archived assessment."},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        assessment.delete()
        return APIResponse(message="Assessment deleted successfully.")


class AdminAssessmentPublishView(APIView):
    """
    Validate points invariant, resolve audience, create assignments, freeze AssessmentSnapshot, and publish assessment.
    POST /api/v1/admin/assessments/<id>/publish/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        published = AssessmentService.publish_assessment(
            assessment=assessment,
            actor=request.user,
            request=request,
            enforce_audience=True
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(published).data,
            message="Assessment published successfully and snapshot permanently locked."
        )


class AdminAssessmentAudienceView(APIView):
    """
    Retrieve or configure audience targeting for a DRAFT assessment.
    GET /api/v1/admin/assessments/<id>/audience/
    POST /api/v1/admin/assessments/<id>/audience/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        resolved = AssessmentAudienceService.resolve_audience(assessment)
        return APIResponse(data=resolved)

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = ConfigureAudienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_all = serializer.validated_data.get('target_all_students', False)
        section_ids = [str(sid) for sid in serializer.validated_data.get('section_ids', [])]
        student_ids = [str(uid) for uid in serializer.validated_data.get('student_ids', [])]

        resolved = AssessmentAudienceService.configure_audience(
            assessment=assessment,
            section_ids=section_ids,
            student_ids=student_ids,
            target_all_students=target_all,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=resolved,
            message="Assessment target audience updated successfully."
        )


class AdminAssessmentAudiencePreviewView(APIView):
    """
    Pure preview of resolved audience without mutating draft state or creating assignments.
    POST /api/v1/admin/assessments/<id>/audience/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = ConfigureAudienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_all = serializer.validated_data.get('target_all_students', False)
        section_ids = [str(sid) for sid in serializer.validated_data.get('section_ids', [])]
        student_ids = [str(uid) for uid in serializer.validated_data.get('student_ids', [])]

        if target_all or any(s.upper() in ['ALL', 'ALL_STUDENTS', 'ALL_ACTIVE'] for s in student_ids):
            student_ids = [str(uid) for uid in StudentService.get_canonical_student_users_queryset(active_only=False).values_list('id', flat=True)]
            section_ids = []

        resolved = AssessmentAudienceService.resolve_audience(
            assessment=assessment,
            section_ids=section_ids,
            student_ids=student_ids
        )
        return APIResponse(data=resolved)


class AdminAssessmentArchiveView(APIView):
    """
    Archive an assessment.
    POST /api/v1/admin/assessments/<id>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        archived = AssessmentService.archive_assessment(assessment=assessment, actor=request.user, request=request)
        return APIResponse(
            data=AssessmentAdminDetailSerializer(archived).data,
            message="Assessment archived."
        )


class AdminAssessmentQuestionAddView(APIView):
    """
    Add a published QuestionVersion to a DRAFT assessment.
    POST /api/v1/admin/assessments/<id>/questions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = AddQuestionToAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qv_id = data.get('question_version_id')
        if not qv_id and data.get('question_id'):
            question = get_object_or_404(Question, id=data['question_id'])
            qv = question.versions.filter(status=VersionStatus.PUBLISHED).order_by('-version_number').first()
            if not qv:
                qv = question.versions.order_by('-version_number').first()
            if not qv:
                return APIResponse(
                    message="No version found for the specified question.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        elif qv_id:
            qv = get_object_or_404(QuestionVersion, id=qv_id)
        else:
            return APIResponse(
                message="Either question_version_id or question_id is required.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        aq = AssessmentService.add_question(
            assessment=assessment,
            question_version=qv,
            actor=request.user,
            order=data.get('order'),
            points=data.get('points'),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            negative_points=data.get('negative_points', 0),
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Question added to assessment.",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentQuestionRemoveView(APIView):
    """
    Remove a question from a DRAFT assessment.
    DELETE /api/v1/admin/assessments/<id>/questions/<question_version_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def delete(self, request, pk, question_version_id):
        assessment = get_object_or_404(Assessment, id=pk)
        AssessmentService.remove_question(
            assessment=assessment,
            question_version_id=str(question_version_id),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Question removed from assessment."
        )


class AdminAssessmentAssignmentListView(APIView):
    """
    List & Assign students to an assessment.
    GET /api/v1/admin/assessments/<id>/assignments/
    POST /api/v1/admin/assessments/<id>/assignments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        assignments = assessment.assignments.select_related('student__student_profile', 'assigned_by').all()
        serializer = AssessmentAssignmentSerializer(assignments, many=True)
        return APIResponse(data=serializer.data)

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = AssignStudentsPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_ids = [str(sid) for sid in serializer.validated_data['student_ids']]

        assignments = AssessmentService.assign_students(
            assessment=assessment,
            student_ids=student_ids,
            actor=request.user,
            request=request,
            sync_draft_target=True
        )
        return APIResponse(
            data=AssessmentAssignmentSerializer(assignments, many=True).data,
            message=f"Successfully assigned {len(assignments)} student(s).",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentAssignmentRevokeView(APIView):
    """
    Revoke a student's assignment to an assessment.
    DELETE /api/v1/admin/assessments/<id>/assignments/<student_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def delete(self, request, pk, student_id):
        assessment = get_object_or_404(Assessment, id=pk)
        assignment = AssessmentService.revoke_assignment(
            assessment=assessment,
            student_id=str(student_id),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=AssessmentAssignmentSerializer(assignment).data,
            message="Student assignment revoked."
        )


# ==============================================================================
# Student Assessment & Test Room Views
# ==============================================================================

class StudentAssessmentListView(APIView):
    """
    List all assessments assigned to the authenticated student.
    GET /api/v1/student/assessments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request):
        # Query only assigned assessments in PUBLISHED status
        assessments = Assessment.objects.filter(
            assignments__student=request.user,
            assignments__status=AssignmentStatus.ASSIGNED,
            status=AssessmentStatus.PUBLISHED
        ).order_by('start_datetime')

        serializer = StudentAssessmentListSerializer(assessments, many=True, context={'request': request})
        return APIResponse(data=serializer.data)


class StudentAssessmentDetailView(APIView):
    """
    Get instructions and eligibility for a specific assigned assessment.
    GET /api/v1/student/assessments/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.filter(
                assignments__student=request.user,
                assignments__status=AssignmentStatus.ASSIGNED,
                status=AssessmentStatus.PUBLISHED
            ),
            id=pk
        )
        serializer = StudentAssessmentListSerializer(assessment, context={'request': request})
        return APIResponse(data=serializer.data)


class StudentAssessmentStartView(APIView):
    """
    Start or Resume a Test Attempt.
    POST /api/v1/student/assessments/<id>/start/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk):
        attempt, created = AttemptService.start_attempt(
            student=request.user,
            assessment_id=str(pk),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data={"attempt_id": str(attempt.id), "status": str(attempt.status), "is_new": created},
            message="Test attempt started." if created else "Resuming active test attempt.",
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class StudentAttemptDetailView(APIView):
    """
    Retrieve authoritative test attempt state, sanitized snapshot questions, and current answers.
    GET /api/v1/student/attempts/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request, pk):
        attempt = get_object_or_404(
            TestAttempt.objects.select_related('assessment', 'assessment_snapshot').prefetch_related('answers'),
            id=pk
        )

        # IDOR Protection
        if attempt.student != request.user:
            return APIResponse(
                message="You do not have permission to access this test attempt.",
                status_code=status.HTTP_403_FORBIDDEN
            )

        # Check and handle timer expiry
        AttemptTimerService.check_and_expire_attempt_if_needed(attempt)

        # Check and handle window termination expiry
        now = timezone.now()
        if attempt.termination_pending and attempt.termination_deadline and now >= attempt.termination_deadline:
            from apps.proctoring.services import AttemptTerminationPolicyService
            AttemptTerminationPolicyService.check_and_expire_termination(str(attempt.id))
            attempt.refresh_from_db()

        snapshot = attempt.assessment_snapshot
        snapshot_data = snapshot.snapshot_data or {}
        raw_questions = snapshot_data.get('questions', [])

        # Index snapshot questions by ID
        questions_by_id = {q['snapshot_question_id']: dict(q) for q in raw_questions}

        # Format questions according to attempt's deterministic question_order and option_orders
        ordered_questions = []
        for q_id in attempt.question_order:
            if q_id in questions_by_id:
                q_item = dict(questions_by_id[q_id])
                # Shuffle options if randomized
                if q_id in attempt.option_orders and 'type_config' in q_item and 'options' in q_item['type_config']:
                    ordered_opt_ids = attempt.option_orders[q_id]
                    raw_opts = {opt['id']: opt for opt in q_item['type_config']['options']}
                    q_item['type_config']['options'] = [
                        raw_opts[opt_id] for opt_id in ordered_opt_ids if opt_id in raw_opts
                    ]
                # Defensive enrichment for coding questions if snapshot was missing starter_codes or examples
                if q_item.get('question_type') == 'CODING':
                    c_cfg = dict(q_item.get('coding_config') or {})
                    if not c_cfg.get('starter_codes') or not c_cfg.get('examples'):
                        from apps.assessments.models import AssessmentSnapshotQuestion
                        snap_rec = AssessmentSnapshotQuestion.objects.filter(
                            snapshot=snapshot, snapshot_question_id=q_id
                        ).select_related('question_version', 'question_version__coding_config').first()
                        if snap_rec and snap_rec.question_version and hasattr(snap_rec.question_version, 'coding_config'):
                            c_model = snap_rec.question_version.coding_config
                            if c_model:
                                if not c_cfg.get('starter_codes') and c_model.starter_codes:
                                    c_cfg['starter_codes'] = c_model.starter_codes
                                if not c_cfg.get('examples') and c_model.examples:
                                    c_cfg['examples'] = c_model.examples
                                if not c_cfg.get('problem_statement') and c_model.problem_statement:
                                    c_cfg['problem_statement'] = c_model.problem_statement
                                if not c_cfg.get('constraints') and c_model.constraints:
                                    c_cfg['constraints'] = c_model.constraints
                    q_item['coding_config'] = c_cfg

                # Runtime student sanitization guard (strip answer keys, is_correct, reference solutions)
                if 'type_config' in q_item and isinstance(q_item['type_config'], dict):
                    for sec_k in ['correct_option', 'correct_options', 'correct_answer', 'accepted_answers', 'explanation', 'reference_solution', 'rubric', 'admin_notes']:
                        q_item['type_config'].pop(sec_k, None)
                    if 'options' in q_item['type_config'] and isinstance(q_item['type_config']['options'], list):
                        for o in q_item['type_config']['options']:
                            if isinstance(o, dict):
                                o.pop('is_correct', None)
                if q_item.get('question_type') == 'CODING':
                    c_clean = dict(q_item.get('coding_config') or {})
                    c_clean.pop('reference_solutions', None)
                    c_clean.pop('reference_solution', None)
                    c_clean.pop('hidden_test_cases', None)
                    c_clean.pop('all_test_cases', None)
                    q_item['coding_config'] = c_clean

                ordered_questions.append(q_item)

        # Compile answers map
        answers_map = {}
        for ans in attempt.answers.all():
            answers_map[ans.question_id] = StudentAttemptAnswerSerializer(ans).data

        remaining_secs = AttemptTimerService.get_remaining_seconds(attempt)

        # Authoritative proctoring violation and active warning recovery
        confirmed_violations_count = 0
        active_warning_data = None
        try:
            from apps.proctoring.models import ProctoringSession, ProctoringEvent, ProctoringWarning
            proct_session = ProctoringSession.objects.filter(attempt=attempt).first()
            if proct_session:
                confirmed_violations_count = ProctoringEvent.objects.filter(
                    session=proct_session,
                    is_confirmed=True
                ).count()
                latest_warn = ProctoringWarning.objects.filter(
                    session=proct_session,
                    is_acknowledged=False
                ).order_by('-issued_at').first()
                if latest_warn:
                    active_warning_data = {
                        "id": str(latest_warn.id),
                        "warning_type": latest_warn.warning_type,
                        "message": latest_warn.message,
                        "issued_at": latest_warn.issued_at.isoformat(),
                    }
        except Exception:
            pass

        try:
            from apps.invigilation.models import ProctorIntervention, InterventionType
            latest_intervention = ProctorIntervention.objects.filter(
                attempt=attempt,
                event_type=InterventionType.WARNING_ISSUED
            ).exclude(
                child_events__event_type=InterventionType.WARNING_ACKNOWLEDGED
            ).order_by('-issued_at').first()
            if latest_intervention and not active_warning_data:
                active_warning_data = {
                    "id": str(latest_intervention.id),
                    "warning_type": latest_intervention.reason_code,
                    "reason_code": latest_intervention.reason_code,
                    "message": latest_intervention.reason_text,
                    "issued_at": latest_intervention.issued_at.isoformat(),
                }
        except Exception:
            pass

        reattempt_data = None
        try:
            from apps.invigilation.models import ProctorReattemptAuthorization
            reatt_auth = ProctorReattemptAuthorization.objects.filter(
                original_attempt=attempt
            ).first()
            if not reatt_auth:
                reatt_auth = ProctorReattemptAuthorization.objects.filter(
                    assessment=attempt.assessment,
                    student=attempt.student
                ).first()
            if reatt_auth:
                rem_sec = max(0, math.ceil((reatt_auth.available_at - now).total_seconds())) if reatt_auth.available_at else 0
                reattempt_data = {
                    "id": str(reatt_auth.id),
                    "status": reatt_auth.status,
                    "authorized_at": reatt_auth.authorized_at.isoformat() if reatt_auth.authorized_at else None,
                    "available_at": reatt_auth.available_at.isoformat() if reatt_auth.available_at else None,
                    "remaining_seconds": rem_sec,
                    "reason": reatt_auth.reason,
                    "note": reatt_auth.note,
                    "new_attempt_id": str(reatt_auth.new_attempt_id) if reatt_auth.new_attempt_id else None,
                }
        except Exception:
            pass

        return APIResponse(
            data={
                "attempt_id": str(attempt.id),
                "assessment_id": str(attempt.assessment_id),
                "title": attempt.assessment.title,
                "instructions": attempt.assessment.instructions,
                "status": attempt.status,
                "attempt_number": attempt.attempt_number,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                "remaining_seconds": remaining_secs,
                "camera_required": getattr(attempt.assessment, 'camera_required', True),
                "proctoring_enabled": getattr(attempt.assessment, 'proctoring_enabled', True),
                "phone_detection_enabled": getattr(attempt.assessment, 'phone_detection_enabled', True),
                "face_detection_enabled": getattr(attempt.assessment, 'face_detection_enabled', True),
                "multiple_face_detection_enabled": getattr(attempt.assessment, 'multiple_face_detection_enabled', True),
                "gaze_detection_enabled": getattr(attempt.assessment, 'gaze_detection_enabled', True),
                "head_movement_detection_enabled": getattr(attempt.assessment, 'head_movement_detection_enabled', True),
                "max_confirmed_violations": getattr(attempt.assessment, 'max_confirmed_violations', 3),
                "confirmed_violations_count": confirmed_violations_count,
                "active_warning": active_warning_data,
                "is_disqualified": getattr(attempt, 'is_disqualified', False),
                "disqualification_reason": getattr(attempt, 'disqualification_reason', ''),
                "state_version": getattr(attempt, 'state_version', 0),
                "termination_pending": attempt.termination_pending,
                "termination_deadline": attempt.termination_deadline.isoformat() if attempt.termination_deadline else None,
                "termination_remaining_seconds": max(0, int((attempt.termination_deadline - now).total_seconds())) if (attempt.termination_pending and attempt.termination_deadline) else None,
                "termination_reason": attempt.termination_reason,
                "reattempt": reattempt_data,
                "server_time": now.isoformat(),
                "questions": ordered_questions,
                "answers": answers_map,
            },
            message="Attempt state retrieved."
        )


class StudentAttemptSaveAnswerView(APIView):
    """
    Save or Autosave an answer for a specific question within an attempt.
    POST /api/v1/student/attempts/<id>/answers/<question_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk, question_id):
        serializer = SaveAnswerPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_revision = data.get('revision', 1)
        answer_payload = {
            k: v for k, v in data.items() if k != 'revision'
        }

        result = AttemptService.save_answer(
            student=request.user,
            attempt_id=str(pk),
            snapshot_question_id=str(question_id),
            answer_data=answer_payload,
            client_revision=client_revision,
            actor=request.user,
            request=request
        )

        return APIResponse(data=result, message="Answer saved successfully.")


class StudentAttemptSubmitView(APIView):
    """
    Final submission of a test attempt.
    POST /api/v1/student/attempts/<id>/submit/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk):
        attempt = AttemptService.submit_attempt(
            student=request.user,
            attempt_id=str(pk),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data={
                "attempt_id": str(attempt.id),
                "status": attempt.status,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None
            },
            message="Test attempt submitted successfully."
        )


class StudentAttemptTerminateView(APIView):
    """
    Explicit examination exit / termination (e.g. browser back, navigation away, voluntary exit).
    Authoritatively cancels and disqualifies the attempt, preventing re-entry and award of coins.
    POST /api/v1/student/attempts/<id>/terminate/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk):
        reason = request.data.get('reason', 'EXAMINATION ABANDONED — BROWSER NAVIGATION / ROOM EXIT')
        attempt = AttemptService.terminate_attempt_explicitly(
            student=request.user,
            attempt_id=str(pk),
            reason=reason,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data={
                "attempt_id": str(attempt.id),
                "attempt_status": attempt.status,
                "status": attempt.status,
                "is_disqualified": attempt.is_disqualified,
                "disqualification_reason": attempt.disqualification_reason,
            },
            message="Examination attempt terminated and disqualified."
        )


class AdminAssessmentAttendanceView(APIView):
    """
    Get authoritative derived attendance data, section breakdown, and student roster.
    GET /api/v1/admin/assessments/<id>/attendance/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        filters = {
            'section_id': request.query_params.get('section_id'),
            'attendance_status': request.query_params.get('attendance_status'),
            'attempt_status': request.query_params.get('attempt_status'),
            'search': request.query_params.get('search'),
        }
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)

        data = AssessmentAttendanceService.get_attendance_data(
            assessment=assessment,
            filters=filters,
            page=page,
            page_size=page_size
        )
        return APIResponse(data=data)


class AdminAssessmentAttendanceExportView(APIView):
    """
    Export attendance roster and section breakdown in XLSX or PDF format.
    GET /api/v1/admin/assessments/<id>/attendance/export/?format=xlsx|pdf
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def perform_content_negotiation(self, request, force=False):
        """
        Graceful content negotiation: client specifies ?format=xlsx or ?format=pdf
        for file downloads, but error responses (401, 403, 404) must still render as JSON.
        """
        renderers = self.get_renderers()
        try:
            return super().perform_content_negotiation(request, force)
        except Exception:
            return (renderers[0], renderers[0].media_type)

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        export_format = request.query_params.get('format', 'xlsx').lower()
        filters = {
            'section_id': request.query_params.get('section_id'),
            'attendance_status': request.query_params.get('attendance_status'),
            'attempt_status': request.query_params.get('attempt_status'),
            'search': request.query_params.get('search'),
        }

        if export_format == 'csv':
            csv_buf = AssessmentAttendanceService.export_attendance_csv(assessment, filters=filters)
            response = HttpResponse(csv_buf.getvalue(), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="attendance_{assessment.id}.csv"'
            return response
        elif export_format == 'pdf':
            pdf_buf = AssessmentAttendanceService.export_attendance_pdf(assessment, filters=filters)
            response = HttpResponse(pdf_buf.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="attendance_{assessment.id}.pdf"'
            return response
        else:
            xlsx_buf = AssessmentAttendanceService.export_attendance_xlsx(assessment, filters=filters)
            response = HttpResponse(
                xlsx_buf.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="attendance_{assessment.id}.xlsx"'
            return response

