import pytest
import uuid
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone

from apps.accounts.models import User, Role, StudentProfile
from apps.assessments.models import Assessment, AssessmentStatus, TestAttempt, AttemptStatus, AssessmentSnapshot
from apps.results.models import Certificate, CertificateStatus


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def cert_test_data(db):
    admin = User.objects.create_user(
        email="admin_cert@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )
    proctor = User.objects.create_user(
        email="proctor_cert@codeguard.test",
        password="ProctorPassword123!",
        role=Role.PROCTOR
    )
    student1 = User.objects.create_user(
        email="student1_cert@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student1,
        roll_number="CS-CERT-01",
        euid="EUID-CERT-01"
    )

    student2 = User.objects.create_user(
        email="student2_cert@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student2,
        roll_number="CS-CERT-02",
        euid="EUID-CERT-02"
    )

    # Assessment A
    assessment_a = Assessment.objects.create(
        title="Python Fundamentals Exam",
        description="Core Python concepts",
        status=AssessmentStatus.PUBLISHED,
        total_points=100,
        duration_minutes=60,
        start_datetime=timezone.now(),
        end_datetime=timezone.now() + timezone.timedelta(days=7),
        created_by=admin
    )

    # Assessment B
    assessment_b = Assessment.objects.create(
        title="Machine Learning Assessment",
        description="Applied ML",
        status=AssessmentStatus.PUBLISHED,
        total_points=100,
        duration_minutes=90,
        start_datetime=timezone.now(),
        end_datetime=timezone.now() + timezone.timedelta(days=7),
        created_by=admin
    )

    # Assessment C (No certificates)
    assessment_c = Assessment.objects.create(
        title="Empty Exam Without Certs",
        description="Zero certificates issued",
        status=AssessmentStatus.PUBLISHED,
        total_points=50,
        duration_minutes=30,
        start_datetime=timezone.now(),
        end_datetime=timezone.now() + timezone.timedelta(days=7),
        created_by=admin
    )

    # Snapshots
    snap_a = AssessmentSnapshot.objects.create(
        assessment=assessment_a,
        version_number=1,
        snapshot_data={"title": assessment_a.title},
        server_evaluation_bundle={}
    )
    snap_b = AssessmentSnapshot.objects.create(
        assessment=assessment_b,
        version_number=1,
        snapshot_data={"title": assessment_b.title},
        server_evaluation_bundle={}
    )

    # Attempts
    att_a1 = TestAttempt.objects.create(
        assessment=assessment_a,
        assessment_snapshot=snap_a,
        student=student1,
        status=AttemptStatus.SUBMITTED,
        attempt_number=1,
        started_at=timezone.now(),
        submitted_at=timezone.now()
    )
    att_a2 = TestAttempt.objects.create(
        assessment=assessment_a,
        assessment_snapshot=snap_a,
        student=student2,
        status=AttemptStatus.SUBMITTED,
        attempt_number=1,
        started_at=timezone.now(),
        submitted_at=timezone.now()
    )
    att_b1 = TestAttempt.objects.create(
        assessment=assessment_b,
        assessment_snapshot=snap_b,
        student=student1,
        status=AttemptStatus.SUBMITTED,
        attempt_number=1,
        started_at=timezone.now(),
        submitted_at=timezone.now()
    )

    # Certificates: 2 for Assessment A, 1 for Assessment B, 0 for Assessment C
    cert_a1 = Certificate.objects.create(
        certificate_id="CERT-A1-PY101",
        exam=assessment_a,
        student=student1,
        attempt=att_a1,
        printed_name="Alice Candidate",
        status=CertificateStatus.ISSUED,
        issued_at=timezone.now()
    )
    cert_a2 = Certificate.objects.create(
        certificate_id="CERT-A2-PY102",
        exam=assessment_a,
        student=student2,
        attempt=att_a2,
        printed_name="Bob Candidate",
        status=CertificateStatus.PENDING,
        issued_at=None
    )
    cert_b1 = Certificate.objects.create(
        certificate_id="CERT-B1-ML201",
        exam=assessment_b,
        student=student1,
        attempt=att_b1,
        printed_name="Alice ML Specialist",
        status=CertificateStatus.ISSUED,
        issued_at=timezone.now()
    )

    return {
        "admin": admin,
        "proctor": proctor,
        "student1": student1,
        "student2": student2,
        "assessment_a": assessment_a,
        "assessment_b": assessment_b,
        "assessment_c": assessment_c,
        "cert_a1": cert_a1,
        "cert_a2": cert_a2,
        "cert_b1": cert_b1,
    }


def test_admin_can_access_assessment_certificates_summary(api_client, cert_test_data):
    """
    Admin can fetch the assessment-wise certificate summary endpoint.
    Only assessments with certificate_count > 0 are returned.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    url = "/api/v1/admin/certificates/assessments/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.data.get("data", [])
    
    # Must contain Assessment A and B, but NOT Assessment C (0 certs)
    titles = [item["title"] for item in data]
    assert "Python Fundamentals Exam" in titles
    assert "Machine Learning Assessment" in titles
    assert "Empty Exam Without Certs" not in titles

    # Check certificate counts
    item_a = next(i for i in data if i["id"] == str(cert_test_data["assessment_a"].id))
    item_b = next(i for i in data if i["id"] == str(cert_test_data["assessment_b"].id))
    assert item_a["certificate_count"] == 2
    assert item_b["certificate_count"] == 1


def test_admin_can_access_assessment_scoped_certificates(api_client, cert_test_data):
    """
    Admin can fetch certificates belonging strictly to a specific assessment.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    asm_a_id = cert_test_data["assessment_a"].id
    url = f"/api/v1/admin/assessments/{asm_a_id}/certificates/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    results = response.data["results"]
    assert len(results) == 2

    # Verify both returned certs belong exclusively to Assessment A
    cert_ids = [r["certificate_id"] for r in results]
    assert "CERT-A1-PY101" in cert_ids
    assert "CERT-A2-PY102" in cert_ids
    assert "CERT-B1-ML201" not in cert_ids

    # Verify assessment metadata is attached
    assert response.data["assessment"]["id"] == str(asm_a_id)
    assert response.data["assessment"]["title"] == "Python Fundamentals Exam"


def test_cross_assessment_certificate_isolation(api_client, cert_test_data):
    """
    Certificates from Assessment B must NEVER appear when querying Assessment A, and vice-versa.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    asm_b_id = cert_test_data["assessment_b"].id
    url = f"/api/v1/admin/assessments/{asm_b_id}/certificates/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    results = response.data["results"]
    assert len(results) == 1
    assert results[0]["certificate_id"] == "CERT-B1-ML201"

    # None of Assessment A certificates should be present
    for r in results:
        assert str(r["exam_id"]) == str(asm_b_id)


def test_nonexistent_and_invalid_assessment_returns_404(api_client, cert_test_data):
    """
    Requesting certificates for an invalid or non-existent assessment ID returns HTTP 404.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    fake_uuid = uuid.uuid4()
    url = f"/api/v1/admin/assessments/{fake_uuid}/certificates/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_empty_assessment_certificates_returns_clean_response(api_client, cert_test_data):
    """
    An assessment with zero certificates returns a clean empty paginated list with count=0.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    asm_c_id = cert_test_data["assessment_c"].id
    url = f"/api/v1/admin/assessments/{asm_c_id}/certificates/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0
    assert response.data["results"] == []
    assert response.data["assessment"]["id"] == str(asm_c_id)


def test_student_and_proctor_forbidden(api_client, cert_test_data):
    """
    Unauthenticated users get 401.
    Students and proctors get 403.
    """
    asm_a_id = cert_test_data["assessment_a"].id
    summary_url = "/api/v1/admin/certificates/assessments/"
    scoped_url = f"/api/v1/admin/assessments/{asm_a_id}/certificates/"

    # 1. Unauthenticated -> 401
    assert api_client.get(summary_url).status_code == status.HTTP_401_UNAUTHORIZED
    assert api_client.get(scoped_url).status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Student -> 403
    api_client.force_authenticate(user=cert_test_data["student1"])
    assert api_client.get(summary_url).status_code == status.HTTP_403_FORBIDDEN
    assert api_client.get(scoped_url).status_code == status.HTTP_403_FORBIDDEN

    # 3. Proctor -> 403
    api_client.force_authenticate(user=cert_test_data["proctor"])
    assert api_client.get(summary_url).status_code == status.HTTP_403_FORBIDDEN
    assert api_client.get(scoped_url).status_code == status.HTTP_403_FORBIDDEN


def test_assessment_certificates_search_and_status_filter(api_client, cert_test_data):
    """
    Filtering by status and search query works server-side.
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    asm_a_id = cert_test_data["assessment_a"].id
    base_url = f"/api/v1/admin/assessments/{asm_a_id}/certificates/"

    # Filter status=ISSUED (should return only cert_a1)
    res_issued = api_client.get(f"{base_url}?status=ISSUED")
    assert res_issued.status_code == status.HTTP_200_OK
    assert res_issued.data["count"] == 1
    assert res_issued.data["results"][0]["certificate_id"] == "CERT-A1-PY101"

    # Filter status=PENDING (should return only cert_a2)
    res_pending = api_client.get(f"{base_url}?status=PENDING")
    assert res_pending.status_code == status.HTTP_200_OK
    assert res_pending.data["count"] == 1
    assert res_pending.data["results"][0]["certificate_id"] == "CERT-A2-PY102"

    # Search by printed_name
    res_search = api_client.get(f"{base_url}?search=Alice")
    assert res_search.status_code == status.HTTP_200_OK
    assert res_search.data["count"] == 1
    assert res_search.data["results"][0]["printed_name"] == "Alice Candidate"


def test_summary_query_count_is_bounded(api_client, cert_test_data, django_assert_num_queries):
    """
    Assessment certificate summary query count is strictly bounded (single aggregated query, no N+1).
    """
    api_client.force_authenticate(user=cert_test_data["admin"])
    url = "/api/v1/admin/certificates/assessments/"

    with django_assert_num_queries(1):
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

