import re
import mimetypes
from pathlib import Path
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import IsAdmin, IsActiveUser
from apps.core.views import APIResponse
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Question, QuestionVersion, QuestionType, Tag, QuestionStatus, VersionStatus
from .services import QuestionService
from .services_ingestion import SpreadsheetQuestionImporter, TEMP_IMAGE_DIR
from .serializers import (
    TagSerializer,
    QuestionListSerializer,
    QuestionDetailSerializer,
    QuestionVersionAdminDetailSerializer,
    QuestionVersionPublicDetailSerializer,
    QuestionVersionSummarySerializer,
    CreateQuestionSerializer,
    UpdateDraftVersionSerializer,
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


class AdminQuestionListView(APIView):
    """
    List & Create Questions.
    GET /api/v1/admin/questions/
    POST /api/v1/admin/questions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Question.objects.prefetch_related('versions__tags', 'created_by').all()

        # Filter by Question Status (ACTIVE vs ARCHIVED)
        q_status = request.query_params.get('status')
        if q_status:
            queryset = queryset.filter(status=q_status.upper())

        # Filter by Question Type
        q_type = request.query_params.get('question_type') or request.query_params.get('type')
        if q_type:
            queryset = queryset.filter(question_type=q_type.upper())

        # Filter by Difficulty (on latest version)
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(versions__difficulty=difficulty.upper()).distinct()

        # Filter by Version Status (e.g. DRAFT, PUBLISHED)
        v_status = request.query_params.get('version_status')
        if v_status:
            queryset = queryset.filter(versions__status=v_status.upper()).distinct()

        # Filter by Tag
        tag = request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(versions__tags__name__iexact=tag.strip()).distinct()

        # Search across title, description, tags
        search = request.query_params.get('search')
        if search:
            search_clean = search.strip()
            queryset = queryset.filter(
                Q(versions__title__icontains=search_clean) |
                Q(versions__description__icontains=search_clean) |
                Q(versions__tags__name__icontains=search_clean)
            ).distinct()

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'updated_at', '-updated_at', 'question_type', '-question_type']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = QuestionListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        question, version = QuestionService.create_question(
            question_type=data['question_type'],
            title=data['title'],
            description=data['description'],
            instructions=data.get('instructions', ''),
            points=data.get('points', 10),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            negative_points=data.get('negative_points', 0),
            difficulty=data.get('difficulty', 'MEDIUM'),
            tags=data.get('tags', []),
            type_config=data.get('type_config', {}),
            coding_config_data=data.get('coding_config', {}),
            test_cases_data=data.get('test_cases', []),
            sql_config_data=data.get('sql_config', {}),
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(version).data,
            message="Question created successfully in DRAFT status.",
            status_code=status.HTTP_201_CREATED
        )


class AdminQuestionDetailView(APIView):
    """
    Retrieve or Hard-delete logical Question.
    GET /api/v1/admin/questions/<id>/
    DELETE /api/v1/admin/questions/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(
            Question.objects.prefetch_related('versions__tags', 'versions__coding_config__test_cases', 'versions__sql_config'),
            id=pk
        )
        return APIResponse(
            data=QuestionDetailSerializer(question).data,
            message="Question details retrieved."
        )

    def delete(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        QuestionService.delete_draft_question(question=question, actor=request.user, request=request)
        return APIResponse(
            message="Question deleted successfully."
        )


class AdminQuestionDuplicateView(APIView):
    """
    Duplicates an existing question into a completely NEW Question identity in DRAFT status.
    POST /api/v1/admin/questions/<uuid:pk>/duplicate/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        new_question, new_version = QuestionService.duplicate_question(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(new_version).data,
            message="Question duplicated successfully as a new draft question.",
            status_code=status.HTTP_201_CREATED
        )


class AdminQuestionArchiveView(APIView):
    """
    Logically archive a Question.
    POST /api/v1/admin/questions/<id>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        archived_question = QuestionService.archive_question(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionDetailSerializer(archived_question).data,
            message="Question archived successfully."
        )


class AdminQuestionUsageView(APIView):
    """
    Dependency-aware question usage check.
    GET /api/v1/admin/questions/<uuid:pk>/usage/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        usage = QuestionService.get_question_usage(question)
        return APIResponse(
            data=usage,
            message="Question usage details retrieved successfully."
        )


class AdminQuestionRunSandboxView(APIView):
    """
    Safely executes admin test code against authoritative sandbox execution provider.
    POST /api/v1/admin/questions/run-sandbox/

    Strict fail-closed architecture:
    - Never uses exec(), eval(), compile(), or host subprocesses.
    - Uses CodeExecutionService with bounded limits.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from apps.evaluator.services import (
            CodeExecutionService,
            OutputComparisonService,
            ExecutionRequest,
            ExecutionStatus,
        )

        source_code = request.data.get('source_code', '')
        raw_lang = request.data.get('language', 'PYTHON')
        language = (raw_lang or 'PYTHON').strip().upper()
        stdin_data = request.data.get('stdin', '')
        expected_output = request.data.get('expected_output', '')
        
        # Bounded execution limits owned by backend policy
        raw_time_limit = request.data.get('time_limit_ms') or request.data.get('cpu_time_limit_ms') or 2000
        try:
            time_limit_ms = min(max(int(raw_time_limit), 100), 5000)
        except (ValueError, TypeError):
            time_limit_ms = 2000

        raw_mem_limit = request.data.get('memory_limit_mb') or 256
        try:
            memory_limit_mb = min(max(int(raw_mem_limit), 16), 256)
        except (ValueError, TypeError):
            memory_limit_mb = 256

        if not source_code.strip():
            return APIResponse(
                error={"message": "Source code cannot be blank."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['PYTHON', 'CPP', 'JAVA', 'C', 'SQL', 'MYSQL']:
            return APIResponse(
                error={"message": f"Unsupported execution language: {raw_lang}. Supported languages are PYTHON, CPP, JAVA, C."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if language in ['SQL', 'MYSQL']:
            from apps.evaluator.sql_sandbox import SQLExecutionService
            schema_setup = request.data.get('schema_setup_sql', '')
            expected_def = request.data.get('expected_result_definition') or expected_output or ''
            sql_res = SQLExecutionService.evaluate_query(
                candidate_sql=source_code,
                schema_setup_sql=schema_setup,
                expected_result_definition=expected_def,
                time_limit_ms=time_limit_ms
            )
            return APIResponse(
                data={
                    "status": "SUCCESS" if sql_res.get("is_correct") else "RUNTIME_ERROR",
                    "status_id": 3 if sql_res.get("is_correct") else 4,
                    "status_description": sql_res.get("verdict"),
                    "stdout": str(sql_res.get("candidate_rows")),
                    "stderr": sql_res.get("error_message") or None,
                    "compile_output": None,
                    "execution_time_ms": sql_res.get("execution_time_ms", 0),
                    "memory_kb": 0,
                    "time": round(sql_res.get("execution_time_ms", 0) / 1000.0, 3),
                    "memory": 0,
                    "passed": sql_res.get("is_correct"),
                    "expected_output": expected_def,
                    "columns": sql_res.get("candidate_columns"),
                    "rows": sql_res.get("candidate_rows")
                },
                message="SQL sandbox execution completed."
            )

        # Execute strictly via authoritative CodeExecutionService
        exec_req = ExecutionRequest(
            source_code=source_code,
            language=language,
            stdin=stdin_data,
            expected_output=expected_output,
            cpu_time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
        )
        result = CodeExecutionService.execute(exec_req)

        # Map canonical execution status to frontend representation
        status_map = {
            ExecutionStatus.ACCEPTED.value: ("SUCCESS", 3, "Accepted"),
            ExecutionStatus.COMPILATION_ERROR.value: ("COMPILATION_ERROR", 6, "Compilation Error"),
            ExecutionStatus.RUNTIME_ERROR.value: ("RUNTIME_ERROR", 11, "Runtime Error"),
            ExecutionStatus.TIME_LIMIT.value: ("TIME_LIMIT_EXCEEDED", 5, "Time Limit Exceeded"),
            ExecutionStatus.MEMORY_LIMIT.value: ("MEMORY_LIMIT_EXCEEDED", 12, "Memory Limit Exceeded"),
            ExecutionStatus.OUTPUT_LIMIT.value: ("OUTPUT_LIMIT_EXCEEDED", 15, "Output Limit Exceeded"),
            ExecutionStatus.SANDBOX_UNAVAILABLE.value: ("SANDBOX_UNAVAILABLE", 13, "Sandbox Unavailable"),
            ExecutionStatus.WORKER_UNAVAILABLE.value: ("SANDBOX_UNAVAILABLE", 13, "Sandbox Unavailable"),
            ExecutionStatus.SYSTEM_ERROR.value: ("SYSTEM_ERROR", 14, "System Error"),
            ExecutionStatus.JUDGE_INTERNAL_ERROR.value: ("SYSTEM_ERROR", 14, "Internal Error"),
        }
        frontend_status, status_id, default_desc = status_map.get(result.status, (result.status, 14, result.status))
        status_desc = default_desc or result.raw_provider_status or result.status

        passed = None
        if expected_output.strip() and result.stdout is not None:
            passed = OutputComparisonService.compare(
                result.stdout or '',
                expected_output,
                policy={'mode': 'EXACT_STRIPPED', 'ignore_trailing_whitespace': True, 'ignore_trailing_empty_lines': True}
            )

        normalized_data = {
            "status": frontend_status,
            "status_id": status_id,
            "status_description": status_desc,
            "stdout": result.stdout if result.stdout != "" or result.status == ExecutionStatus.ACCEPTED.value else (result.stdout or None),
            "stderr": result.stderr or None,
            "compile_output": result.compile_output or None,
            "execution_time_ms": result.execution_time_ms,
            "memory_kb": result.memory_kb,
            "time": round(result.execution_time_ms / 1000.0, 3),
            "memory": result.memory_kb,
            "passed": passed,
            "expected_output": expected_output,
            "provider": result.provider,
        }

        return APIResponse(
            data=normalized_data,
            message="Sandbox execution completed."
        )


class AdminQuestionVersionListView(APIView):
    """
    List all versions or create/reuse a draft Version (N+1) for a Question.
    GET /api/v1/admin/questions/<id>/versions/
    POST /api/v1/admin/questions/<id>/versions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        versions = question.versions.order_by('version_number')
        return APIResponse(
            data=QuestionVersionSummarySerializer(versions, many=True).data,
            message="Version history retrieved."
        )

    def post(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        if question.versions.filter(status__in=[VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]).exists():
            raise DRFValidationError("Published questions are permanently immutable and cannot have new draft versions created.")
        new_version, _ = QuestionService.get_or_create_draft_version(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(new_version).data,
            message=f"Version {new_version.version_number} draft ready.",
            status_code=status.HTTP_200_OK if new_version.status == VersionStatus.DRAFT else status.HTTP_201_CREATED
        )


class AdminQuestionVersionDetailView(APIView):
    """
    Retrieve or Update a specific QuestionVersion.
    GET /api/v1/admin/questions/<id>/versions/<version_number>/
    PATCH /api/v1/admin/questions/<id>/versions/<version_number>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('tags', 'coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(version).data,
            message=f"Version {version_number} details retrieved."
        )

    def patch(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config'),
            question_id=pk,
            version_number=version_number
        )
        serializer = UpdateDraftVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated_version = QuestionService.update_draft_version(
            version=version,
            title=data.get('title'),
            description=data.get('description'),
            instructions=data.get('instructions'),
            points=data.get('points'),
            negative_marking_enabled=data.get('negative_marking_enabled'),
            negative_points=data.get('negative_points'),
            difficulty=data.get('difficulty'),
            tags=data.get('tags'),
            type_config=data.get('type_config'),
            coding_config_data=data.get('coding_config'),
            test_cases_data=data.get('test_cases'),
            sql_config_data=data.get('sql_config'),
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(updated_version).data,
            message=f"Draft version {version_number} successfully saved."
        )

    put = patch


class AdminQuestionVersionPublishView(APIView):
    """
    Validate and Publish a QuestionVersion.
    POST /api/v1/admin/questions/<id>/versions/<version_number>/publish/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        published_version = QuestionService.publish_version(version=version, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(published_version).data,
            message=f"Version {version_number} published successfully and locked permanently."
        )


class AdminQuestionVersionArchiveView(APIView):
    """
    Archive a published QuestionVersion.
    POST /api/v1/admin/questions/<id>/versions/<version_number>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question'),
            question_id=pk,
            version_number=version_number
        )
        archived_version = QuestionService.archive_version(version=version, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(archived_version).data,
            message=f"Version {version_number} archived."
        )


class AdminQuestionVersionPreviewView(APIView):
    """
    Student-perspective Preview of a QuestionVersion (hiding hidden test cases).
    GET /api/v1/admin/questions/<id>/versions/<version_number>/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('tags', 'coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        return APIResponse(
            data=QuestionVersionPublicDetailSerializer(version).data,
            message=f"Version {version_number} preview retrieved."
        )


class AdminTagListView(APIView):
    """
    List & Create Tags.
    GET /api/v1/admin/tags/
    POST /api/v1/admin/tags/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        tags = Tag.objects.all()
        return APIResponse(data=TagSerializer(tags, many=True).data)

    def post(self, request):
        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = serializer.save()
        return APIResponse(data=TagSerializer(tag).data, status_code=status.HTTP_201_CREATED)


class AdminQuestionTemplateDownloadView(APIView):
    """
    Download official Question Bank canonical ingestion template (XLSX).
    GET /api/v1/admin/questions/import/template/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def perform_content_negotiation(self, request, force=False):
        # Prevent DRF format-suffix negotiation from intercepting ?format=xlsx
        return (None, None)

    def get(self, request):
        fmt = request.query_params.get('format', 'xlsx').lower()
        if fmt == 'csv':
            content = SpreadsheetQuestionImporter.generate_template_csv()
            filename = "codeguard_question_import_template.csv"
            content_type = "text/csv"
        else:
            from apps.questions.canonical import CanonicalExcelTemplateGenerator
            content = CanonicalExcelTemplateGenerator.generate_template_bytes()
            filename = "CODEGUARD_Question_Import_Template_v1.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminQuestionSpreadsheetPreviewView(APIView):
    """
    Upload and parse Excel question file, producing canonical validation preview.
    POST /api/v1/admin/questions/import/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from apps.questions.canonical import CanonicalExcelParser, CanonicalQuestionDTO

        upload = request.FILES.get('file')
        if not upload:
            return APIResponse(
                error={"message": "No file uploaded. Please upload a valid .xlsx spreadsheet based on CODEGUARD_Question_Import_Template_v1.xlsx."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        file_name = getattr(upload, 'name', '')
        if file_name.lower().endswith('.csv'):
            # Backward compatibility fallback for legacy CSVs
            preview_data = SpreadsheetQuestionImporter.parse_and_validate_spreadsheet(
                upload,
                file_name
            )
            return APIResponse(
                data=preview_data,
                message="Spreadsheet validated and preview generated."
            )

        dtos, errors, warnings = CanonicalExcelParser.parse_workbook(upload)
        if len(dtos) == 0 and len(errors) == 0:
            errors.append({
                "question_id": "GLOBAL",
                "type": "QUESTIONS_SHEET",
                "message": "No question rows found in the Questions sheet."
            })

        is_valid = (len(errors) == 0 and len(dtos) > 0)

        preview_questions = []
        for d in dtos:
            preview_questions.append({
                "question_id": d.question_id,
                "title": d.title,
                "type": d.type,
                "difficulty": d.difficulty,
                "points": d.points,
                "negative_points": d.negative_points,
                "status": "DRAFT",
                "statement": d.statement,
                "instructions": d.instructions,
                "options": [
                    {"key": opt.option_key, "text": opt.option_text, "is_correct": opt.is_correct}
                    for opt in d.options
                ],
                "coding": {
                    "languages": d.coding.languages,
                    "starter_codes": d.coding.starter_codes,
                    "constraints": d.coding.constraints,
                    "execution_time_ms": d.coding.execution_time_ms,
                    "memory_mb": d.coding.memory_mb,
                    "examples": d.coding.examples
                } if d.coding else None,
                "test_cases": [
                    {
                        "case_id": tc.case_id,
                        "visibility": tc.visibility,
                        "input": tc.input,
                        "expected_output": tc.expected_output,
                        "points": tc.points,
                        "is_example": tc.is_example,
                        "is_verified": tc.is_verified
                    }
                    for tc in d.test_cases
                ]
            })

        preview_data = {
            "is_valid": is_valid,
            "detected": len(dtos),
            "questions_detected": len(dtos),
            "detected_count": len(dtos),
            "mcq": sum(1 for d in dtos if d.type == "MCQ"),
            "mcq_count": sum(1 for d in dtos if d.type == "MCQ"),
            "coding": sum(1 for d in dtos if d.type == "CODING"),
            "coding_count": sum(1 for d in dtos if d.type == "CODING"),
            "errors": errors,
            "validation_errors": errors,
            "warnings": warnings,
            "questions": preview_questions,
            "rows": preview_questions,
            "total_rows": len(dtos),
            "valid_rows": len(dtos) if is_valid else 0,
            "error_rows": len(errors),
        }

        return APIResponse(
            data=preview_data,
            message="Workbook parsed and validation preview generated successfully."
        )


class AdminQuestionSpreadsheetConfirmView(APIView):
    """
    Commit validated questions into DRAFT questions transactionally.
    POST /api/v1/admin/questions/import/confirm/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from apps.questions.canonical import (
            CanonicalExcelParser,
            CanonicalQuestionImporter,
            CanonicalQuestionDTO,
            CanonicalOptionDTO,
            CanonicalCodingConfigDTO,
            CanonicalTestCaseDTO,
            validate_and_normalize_canonical_question
        )

        upload = request.FILES.get('file')
        raw_questions = request.data.get('questions') or request.data.get('rows')

        if upload:
            dtos, errors, warnings = CanonicalExcelParser.parse_workbook(upload)
            if errors:
                return APIResponse(
                    error={
                        "message": "Import rejected due to validation errors. Zero questions were created.",
                        "errors": errors
                    },
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        elif raw_questions and isinstance(raw_questions, list):
            dtos = []
            for idx, q_item in enumerate(raw_questions, start=1):
                if not isinstance(q_item, dict):
                    continue
                q_payload = q_item.get('normalized_payload') or q_item.get('data') or q_item
                if not isinstance(q_payload, dict):
                    q_payload = q_item
                q_type = str(q_payload.get('type') or q_payload.get('question_type') or 'MCQ').strip().upper()
                opts = []
                for opt in (q_payload.get('options') or []):
                    o_key = str(opt.get('key') or opt.get('id') or '')
                    o_text = str(opt.get('text') or '')
                    o_corr = bool(opt.get('is_correct', False))
                    opts.append(CanonicalOptionDTO(option_key=o_key, option_text=o_text, is_correct=o_corr))

                coding_dto = None
                if q_type == "CODING":
                    c_conf = q_payload.get('coding') or q_payload.get('coding_config') or {}
                    langs = c_conf.get('languages') or c_conf.get('allowed_languages') or ['PYTHON']
                    starters = c_conf.get('starter_codes') or {}
                    if not starters and c_conf.get('starter_code'):
                        starters = {lang: c_conf['starter_code'] for lang in langs}
                    coding_dto = CanonicalCodingConfigDTO(
                        languages=langs,
                        starter_codes=starters,
                        constraints=c_conf.get('constraints') or '',
                        execution_time_ms=c_conf.get('execution_time_ms') or c_conf.get('time_limit_ms') or 2000,
                        memory_mb=c_conf.get('memory_mb') or c_conf.get('memory_limit_mb') or 256,
                        examples=c_conf.get('examples') or []
                    )

                tcs = []
                for tc_idx, tc in enumerate(q_payload.get('test_cases') or [], start=1):
                    tcs.append(CanonicalTestCaseDTO(
                        case_id=str(tc.get('case_id') or tc.get('name') or f"TC{tc_idx:02d}"),
                        visibility=str(tc.get('visibility') or ('HIDDEN' if tc.get('is_hidden') else 'SAMPLE')),
                        input=str(tc.get('input') if tc.get('input') is not None else tc.get('input_data', '')),
                        expected_output=str(tc.get('expected_output') if tc.get('expected_output') is not None else tc.get('output', '')),
                        points=int(tc.get('points') or 1),
                        is_example=bool(tc.get('is_example', False)),
                        is_verified=bool(tc.get('is_verified', True))
                    ))

                dtos.append(CanonicalQuestionDTO(
                    question_id=str(q_payload.get('question_id') or q_payload.get('id') or f"Q{idx:03d}"),
                    title=str(q_payload.get('title') or f"Question {idx}"),
                    type=q_type,
                    statement=str(q_payload.get('statement') or q_payload.get('description') or q_payload.get('problem_statement') or ''),
                    instructions=str(q_payload.get('instructions') or ''),
                    difficulty=str(q_payload.get('difficulty') or 'MEDIUM'),
                    points=int(q_payload.get('points') or 10),
                    negative_points=int(q_payload.get('negative_points') or 0),
                    options=opts,
                    coding=coding_dto,
                    test_cases=tcs
                ))
        else:
            return APIResponse(
                error={"message": "Expected an uploaded workbook file or questions payload to import."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = CanonicalQuestionImporter.import_canonical_questions(
                dtos,
                actor=request.user,
                request=request
            )
            return APIResponse(
                data=result,
                message=f"Successfully imported {result['created_count']} question(s) as Draft.",
                status_code=status.HTTP_201_CREATED if result['created_count'] > 0 else status.HTTP_200_OK
            )
        except (DRFValidationError, DjangoValidationError) as e:
            err_data = getattr(e, 'detail', str(e))
            return APIResponse(
                error={
                    "message": "Import rejected due to validation errors. Zero questions were created.",
                    "details": err_data
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )



class AdminQuestionTempImageView(APIView):
    """
    Authenticated retrieval of temporary uploaded question screenshot for the review interface.
    GET /api/v1/admin/questions/temp-image/<str:image_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, image_id: str):
        # Strict filename sanitization to prevent path traversal
        clean_id = Path(image_id).name
        if not re.match(r'^[a-f0-9]{32}\.(png|jpe?g|webp)$', clean_id, re.IGNORECASE):
            return APIResponse(
                error={"message": "Image not found."},
                status_code=status.HTTP_404_NOT_FOUND
            )

        file_path = TEMP_IMAGE_DIR / clean_id
        if not file_path.exists() or not file_path.is_file():
            return APIResponse(
                error={"message": "Image not found or has expired."},
                status_code=status.HTTP_404_NOT_FOUND
            )

        mime, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(open(file_path, 'rb'), content_type=mime or 'application/octet-stream')


class AdminQuestionVersionHealthView(APIView):
    """
    Returns the authoritative 12-check Question Health assessment for a QuestionVersion.
    GET /api/v1/admin/questions/<pk>/versions/<version_number>/health/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk, version_number):
        from .services import CodingQuestionValidationService
        version = get_object_or_404(
            QuestionVersion.objects.select_related('coding_config', 'question').prefetch_related('coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        if version.question_type != QuestionType.CODING:
            return APIResponse(
                error={"message": "Question health assessment is only available for coding questions."},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        health_data = CodingQuestionValidationService.get_health_status(version)
        return APIResponse(data=health_data, message="Question health status retrieved.")


class AdminSupportedLanguagesView(APIView):
    """
    Returns the dynamic registry of execution languages supported by CODEGUARD.
    GET /api/v1/admin/questions/languages/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        from .models import CodingLanguage
        from apps.evaluator.services import Judge0Adapter

        starter_templates = {
            'PYTHON': "def solve():\n    pass\n",
            'CPP': "#include <bits/stdc++.h>\n",
            'JAVA': "import java.io.*;\n",
            'C': "#include <stdio.h>\n",
        }

        languages = []
        for choice_key, choice_label in CodingLanguage.choices:
            languages.append({
                "key": choice_key,
                "label": choice_label,
                "monaco_lang": choice_key.lower() if choice_key != 'CPP' else 'cpp',
                "judge0_id": Judge0Adapter.LANGUAGE_IDS.get(choice_key),
                "default_starter_code": starter_templates.get(choice_key, "")
            })

        return APIResponse(data={"languages": languages}, message="Supported languages retrieved.")


class AdminPlatformImportStatusView(APIView):
    """
    Returns the configuration status of authorized platform integrations.
    GET /api/v1/admin/questions/platform-import/status/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        from .services_platform_import import PlatformImportService
        return APIResponse(
            data=PlatformImportService.get_platforms_status(),
            message="Platform import integration statuses retrieved."
        )


class AdminPlatformImportPreviewView(APIView):
    """
    Parses and returns a normalized preview of a platform question import before creation.
    POST /api/v1/admin/questions/platform-import/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from .services_platform_import import PlatformImportService
        source = request.data.get('source', '')
        file_obj = request.FILES.get('file')
        file_bytes = file_obj.read() if file_obj else None

        raw_data = request.data.get('data')
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                raw_data = {}
        elif not isinstance(raw_data, dict):
            raw_data = dict(request.data)

        preview = PlatformImportService.parse_preview(
            source=source,
            payload_data=raw_data,
            file_bytes=file_bytes
        )
        return APIResponse(data=preview, message="Platform import preview generated.")


class AdminPlatformImportConfirmView(APIView):
    """
    Creates an imported question strictly in DRAFT status with unverified test cases.
    POST /api/v1/admin/questions/platform-import/confirm/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from .services_platform_import import PlatformImportService
        normalized_payload = request.data.get('normalized_payload')
        if not normalized_payload:
            return APIResponse(
                error={"message": "Normalized payload is required to finalize import."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        version = PlatformImportService.confirm_and_create_draft(
            normalized_payload=normalized_payload,
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(version).data,
            message=f"Question '{version.title}' successfully imported as Draft.",
            status_code=status.HTTP_201_CREATED
        )
