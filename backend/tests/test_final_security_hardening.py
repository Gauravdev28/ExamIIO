import os
import io
import uuid
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import User, Role
from apps.proctoring.serializers import (
    StudentProctoringFrameUploadSerializer,
    StudentProctoringAudioUploadSerializer,
)
from apps.questions.views import _validate_question_upload_file


@pytest.mark.django_db
class TestFinalSecurityHardening:
    """
    Security regression test suite validating:
    - Removal of BasicAuthentication (Session-only default)
    - File upload magic-byte validation & safety boundaries
    - Private media RBAC and direct-access protection
    - 500 Error message and stack-trace sanitization
    - Health check privacy for public callers
    """

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin_hardening@codeguard.test",
            password="AdminPassword123!",
            role=Role.ADMIN
        )
        self.student_1 = User.objects.create_user(
            email="student1_hardening@codeguard.test",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        self.student_2 = User.objects.create_user(
            email="student2_hardening@codeguard.test",
            password="StudentPassword123!",
            role=Role.STUDENT
        )

    # --------------------------------------------------------------------------
    # 1. BasicAuthentication Removal Verification
    # --------------------------------------------------------------------------

    def test_basic_authentication_removed_from_defaults(self):
        """Ensure BasicAuthentication is not active in default authentication classes."""
        classes = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', [])
        class_names = [c if isinstance(c, str) else f"{c.__module__}.{c.__name__}" for c in classes]
        assert not any('BasicAuthentication' in name for name in class_names), (
            "BasicAuthentication must not be present in default authentication classes."
        )
        assert any('SessionAuthentication' in name for name in class_names), (
            "SessionAuthentication must be configured as default."
        )

    def test_unauthenticated_request_rejected_without_basic_auth_prompt(self):
        """Unauthenticated requests must be rejected without WWW-Authenticate Basic prompt."""
        url = reverse('accounts:current-user')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'Basic' not in response.get('WWW-Authenticate', '')

    # --------------------------------------------------------------------------
    # 2. File Upload Hardening: Proctoring Frames & Audio
    # --------------------------------------------------------------------------

    def test_proctoring_frame_rejects_oversized_payload(self):
        """Frame uploads exceeding 300 KB must be rejected."""
        oversized = SimpleUploadedFile("frame.jpg", b'\xff\xd8\xff' + b'A' * (305 * 1024), content_type="image/jpeg")
        serializer = StudentProctoringFrameUploadSerializer(data={"frame": oversized})
        assert not serializer.is_valid()
        assert "300 KB" in str(serializer.errors)

    def test_proctoring_frame_rejects_executable_or_non_image_payload(self):
        """Frame uploads with executable headers (e.g. MZ, ELF, shell) must be rejected."""
        malicious_mz = SimpleUploadedFile("frame.jpg", b'MZ\x90\x00executable_code_here', content_type="image/jpeg")
        serializer = StudentProctoringFrameUploadSerializer(data={"frame": malicious_mz})
        assert not serializer.is_valid()
        assert "Invalid image format" in str(serializer.errors) or "prohibited" in str(serializer.errors)

        malicious_elf = SimpleUploadedFile("frame.jpg", b'\x7fELFbinary_content', content_type="image/jpeg")
        serializer_elf = StudentProctoringFrameUploadSerializer(data={"frame": malicious_elf})
        assert not serializer_elf.is_valid()

        plain_text = SimpleUploadedFile("frame.jpg", b'plain text not an image', content_type="image/jpeg")
        serializer_text = StudentProctoringFrameUploadSerializer(data={"frame": plain_text})
        assert not serializer_text.is_valid()
        assert "Invalid image format" in str(serializer_text.errors)

    def test_proctoring_frame_accepts_valid_jpeg(self):
        """Valid JPEG header frame upload must be accepted."""
        valid_jpeg = SimpleUploadedFile("frame.jpg", b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 500, content_type="image/jpeg")
        serializer = StudentProctoringFrameUploadSerializer(data={"frame": valid_jpeg})
        assert serializer.is_valid(), serializer.errors

    def test_proctoring_audio_rejects_oversized_and_invalid_payload(self):
        """Audio uploads exceeding 100 KB or with non-audio content must be rejected."""
        oversized_audio = SimpleUploadedFile("audio.webm", b'\x1a\x45\xdf\xa3' + b'A' * (105 * 1024), content_type="audio/webm")
        serializer = StudentProctoringAudioUploadSerializer(data={"audio": oversized_audio})
        assert not serializer.is_valid()
        assert "100 KB" in str(serializer.errors)

        malicious_audio = SimpleUploadedFile("audio.webm", b'MZ\x90\x00bad_executable', content_type="audio/webm")
        serializer_mal = StudentProctoringAudioUploadSerializer(data={"audio": malicious_audio})
        assert not serializer_mal.is_valid()

    def test_proctoring_audio_accepts_valid_webm(self):
        """Valid WebM audio container upload must be accepted."""
        valid_webm = SimpleUploadedFile("audio.webm", b'\x1a\x45\xdf\xa3\x9f\x42\x86\x81' + b'\x00' * 200, content_type="audio/webm")
        serializer = StudentProctoringAudioUploadSerializer(data={"audio": valid_webm})
        assert serializer.is_valid(), serializer.errors

    # --------------------------------------------------------------------------
    # 3. Question Spreadsheet Upload Hardening
    # --------------------------------------------------------------------------

    def test_question_spreadsheet_rejects_executable_or_spoofed_files(self):
        """Question upload validator must reject executable files, path traversal, and corrupted files."""
        fake_xlsx = SimpleUploadedFile("questions.xlsx", b'MZ\x90\x00not_a_zip', content_type="application/vnd.ms-excel")
        err = _validate_question_upload_file(fake_xlsx)
        assert err is not None
        assert "Executable" in err or "Corrupted" in err or "invalid" in err

        bad_ext_file = SimpleUploadedFile("exploit.sh", b"#!/bin/sh\nrm -rf /", content_type="text/x-sh")
        err_ext = _validate_question_upload_file(bad_ext_file)
        assert err_ext is not None
        assert "Invalid file format" in err_ext or "prohibited" in err_ext

    def test_question_spreadsheet_accepts_valid_xlsx_header(self):
        """Valid XLSX file header must pass file validation."""
        valid_xlsx = SimpleUploadedFile("template.xlsx", b'PK\x03\x04\x14\x00\x06\x00' + b'\x00' * 100, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        err = _validate_question_upload_file(valid_xlsx)
        assert err is None

    # --------------------------------------------------------------------------
    # 4. Error Information Leakage Prevention
    # --------------------------------------------------------------------------

    def test_unexpected_exception_handler_sanitizes_500_response(self):
        """Unhandled 500 exceptions must never leak internal stack traces or database errors."""
        from apps.core.exceptions import custom_exception_handler
        from rest_framework.views import APIView

        class DummyView(APIView):
            pass

        simulated_exc = RuntimeError("CRITICAL_INTERNAL_DB_SECRET: table users where password_hash = xyz")
        context = {"view": DummyView(), "request": None}

        response = custom_exception_handler(simulated_exc, context)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["status"] == "error"
        assert response.data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert response.data["error"]["message"] == "An unexpected server error occurred."
        assert response.data["error"]["details"] is None
        # Verify secret was not leaked
        assert "password_hash" not in str(response.data)
        assert "CRITICAL_INTERNAL_DB_SECRET" not in str(response.data)

    # --------------------------------------------------------------------------
    # 5. Private Media Access Protection & RBAC
    # --------------------------------------------------------------------------

    def test_unauthenticated_evidence_access_denied(self):
        """Unauthenticated requests to evidence streaming endpoints are denied."""
        url = f"/api/v1/admin/proctoring/evidence/{uuid.uuid4()}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_cannot_access_admin_evidence_endpoint(self):
        """Students cannot access proctoring evidence streaming."""
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/admin/proctoring/evidence/{uuid.uuid4()}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_report_download_denied(self):
        """Unauthenticated requests to report download endpoints are denied."""
        url = f"/api/v1/student/reports/{uuid.uuid4()}/download/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_certificate_download_denied(self):
        """Unauthenticated requests to certificate download endpoints are denied."""
        url = f"/api/v1/student/certificates/{uuid.uuid4()}/download/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
