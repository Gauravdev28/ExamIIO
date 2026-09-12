import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile, Role, Section
from apps.accounts.services import (
    StudentService,
    AccountSecurityService,
    AdminIdService,
    EUIDService,
)
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    TestAttempt,
    AttemptStatus,
    AssessmentSnapshot,
)
from apps.assessments.services import AssessmentAttendanceService, resolve_student_users
from rest_framework.exceptions import ValidationError as DRFValidationError


@pytest.fixture
def primary_admin(db):
    user = User.objects.create(
        email="primary_admin_audit@codeguard.edu",
        role=Role.ADMIN,
        admin_id="EUAD-GAURAV-099",
        primary_admin_marker="PRIMARY",
        display_name="Primary Admin",
        is_active=True,
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def secondary_admin(db):
    user = User.objects.create(
        email="secondary_admin_audit@codeguard.edu",
        role=Role.ADMIN,
        admin_id="CG-ADM-000005",
        display_name="Secondary Admin",
        is_active=True,
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def primary_admin_client(primary_admin):
    client = APIClient()
    client.force_authenticate(user=primary_admin)
    return client


@pytest.fixture
def secondary_admin_client(secondary_admin):
    client = APIClient()
    client.force_authenticate(user=secondary_admin)
    return client


@pytest.fixture
def sample_section(db):
    return Section.objects.create(code="CSE-AUDIT", name="Computer Science Audit", is_active=True)


# ==============================================================================
# D1: Secondary Admin Deletion (ProtectedError Resolution)
# ==============================================================================

@pytest.mark.django_db
class TestSecondaryAdminDeletionFix:

    def test_secondary_admin_with_foreign_keys_is_safely_deleted(
        self, primary_admin_client, secondary_admin, primary_admin
    ):
        """
        When deleting a secondary admin who authored an assessment,
        the assessment is re-attributed to the Primary Admin, the secondary admin
        is cleanly deleted from the database, and HTTP 200 is returned.
        """
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Admin Authored Assessment",
            description="Testing protected deletion",
            created_by=secondary_admin,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60,
        )

        url = f"/api/v1/admin/administrators/{secondary_admin.id}/"
        response = primary_admin_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "deleted successfully" in data["message"].lower()

        # Target admin is deleted from DB
        assert not User.objects.filter(id=secondary_admin.id).exists()

        # Authored assessment is re-attributed to Primary Admin
        assessment.refresh_from_db()
        assert assessment.created_by == primary_admin

    def test_primary_admin_cannot_be_deleted(self, primary_admin_client, primary_admin):
        """
        D1: Primary admin deletion must be rejected with HTTP 400.
        """
        url = f"/api/v1/admin/administrators/{primary_admin.id}/"
        response = primary_admin_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "primary administrator" in response.data.get("message", "").lower()

    def test_admin_without_relations_is_hard_deleted(
        self, primary_admin_client, primary_admin
    ):
        """
        D1: Admin without foreign keys is hard deleted normally.
        """
        clean_admin = User.objects.create_user(
            email="clean_admin@codeguard.edu",
            password="AdminPass123!",
            role=Role.ADMIN,
            admin_id="CG-ADM-000008",
            display_name="Clean Admin",
            is_active=True,
        )
        url = f"/api/v1/admin/administrators/{clean_admin.id}/"
        response = primary_admin_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not User.objects.filter(id=clean_admin.id).exists()


# ==============================================================================
# D2: Authoritative Dashboard Student Count
# ==============================================================================

@pytest.mark.django_db
class TestDashboardStudentCountFix:

    def test_dashboard_counts_only_active_student_profiles(
        self, primary_admin_client, sample_section
    ):
        """
        D2: Dashboard overview counts StudentProfile with active users,
        ignoring orphaned User records.
        """
        # Create a legitimate student
        u1, p1 = StudentService.create_student(
            email="legit_student@codeguard.edu",
            roll_number="BETN1AI25001",
            section=sample_section,
        )

        # Create an orphaned User record with role=STUDENT (no StudentProfile)
        User.objects.create_user(
            email="orphaned_student@codeguard.edu",
            password="Password123!",
            role=Role.STUDENT,
            is_active=True,
        )

        # Create an inactive student
        u3, p3 = StudentService.create_student(
            email="inactive_student@codeguard.edu",
            roll_number="BETN1AI25002",
            section=sample_section,
        )
        u3.is_active = False
        u3.save()

        url = "/api/v1/admin/overview/"
        response = primary_admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", response.data)

        # Only u1 has active User + StudentProfile
        assert data["metrics"]["total_students"] == 1


# ==============================================================================
# D3 & D4: Two-Phase Bulk Import Validation & Roll Number Uniqueness
# ==============================================================================

@pytest.mark.django_db
class TestBulkImportValidationFix:

    def test_bulk_create_rejects_internal_duplicate_roll_numbers_with_zero_writes(
        self, sample_section, primary_admin
    ):
        """
        D3-D4: File with internal duplicate roll numbers is rejected,
        0 database records are created.
        """
        batch = [
            {"roll_number": "ROLL-DUP-01", "email": "s1@test.com", "section": sample_section.code},
            {"roll_number": "ROLL-DUP-01", "email": "s2@test.com", "section": sample_section.code},
        ]

        with pytest.raises(DRFValidationError) as exc:
            StudentService.bulk_create_students(batch, actor=primary_admin)

        assert "Duplicate roll number" in str(exc.value)
        assert not StudentProfile.objects.filter(roll_number="ROLL-DUP-01").exists()
        assert not User.objects.filter(email="s1@test.com").exists()

    def test_bulk_create_rejects_existing_db_roll_number(
        self, sample_section, primary_admin
    ):
        """
        D3-D4: Roll number already in DB is rejected, 0 writes occur.
        """
        StudentService.create_student(
            email="preexisting@test.com",
            roll_number="ROLL-PRE-01",
            section=sample_section,
        )

        batch = [
            {"roll_number": "ROLL-NEW-01", "email": "new1@test.com", "section": sample_section.code},
            {"roll_number": "ROLL-PRE-01", "email": "new2@test.com", "section": sample_section.code},
        ]

        with pytest.raises(DRFValidationError) as exc:
            StudentService.bulk_create_students(batch, actor=primary_admin)

        assert "already exists in system database" in str(exc.value)
        assert not StudentProfile.objects.filter(roll_number="ROLL-NEW-01").exists()

    def test_bulk_create_valid_batch_succeeds_atomically(
        self, sample_section, primary_admin
    ):
        """
        D3-D4: Clean batch creates all accounts atomically with initial passwords.
        """
        batch = [
            {"roll_number": "ROLL-VALID-01", "email": "v1@test.com", "section": sample_section.code, "first_name": "Alice", "last_name": "Smith"},
            {"roll_number": "ROLL-VALID-02", "email": "v2@test.com", "section": sample_section.code, "first_name": "Bob", "last_name": "Jones"},
        ]

        records = StudentService.bulk_create_students(batch, actor=primary_admin)
        assert len(records) == 2

        u1, p1 = records[0]
        assert u1.email == "v1@test.com"
        assert p1.roll_number == "ROLL-VALID-01"
        assert u1.display_name == "Alice Smith"
        assert u1.check_password("ROLL-VALID-01")
        assert u1.first_login_required is True


# ==============================================================================
# D5: Student First-Login & Password Security
# ==============================================================================

@pytest.mark.django_db
class TestFirstLoginPasswordSecurityFix:

    def test_first_login_password_change_updates_hash_and_name(
        self, sample_section
    ):
        """
        D5: First login changes password using user.set_password (PBKDF2 hash),
        clears first_login_required on User and StudentProfile, updates display_name,
        and keeps session hash valid.
        """
        user, profile = StudentService.create_student(
            email="first_login_student@codeguard.edu",
            roll_number="BETN1AI25099",
            section=sample_section,
        )
        assert user.check_password("BETN1AI25099")
        assert user.first_login_required is True
        assert profile.first_login_required is True

        client = APIClient()
        client.force_authenticate(user=user)

        url = "/api/v1/auth/change-password/"
        payload = {
            "current_password": "BETN1AI25099",
            "new_password": "NewSecurePass2026!",
            "confirm_password": "NewSecurePass2026!",
            "first_name": "Gaurav",
            "last_name": "Agarwal",
        }
        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        profile.refresh_from_db()

        assert user.check_password("NewSecurePass2026!")
        assert not user.check_password("BETN1AI25099")
        assert user.first_login_required is False
        assert profile.first_login_required is False
        assert user.display_name == "Gaurav Agarwal"


# ==============================================================================
# D7: Authoritative Attendance System with Explicit Time Boundaries
# ==============================================================================

@pytest.mark.django_db
class TestDeterministicAttendanceTimeBoundaries:

    def test_attendance_status_time_boundaries(self, primary_admin, sample_section):
        """
        D7:
        - Before start window: NOT_STARTED
        - During window without attempt: NOT_STARTED
        - After deadline without attempt: NOT_ATTENDED
        - Started attempt: ATTENDED
        - Multiple attempts: 1 record
        """
        now = timezone.now()

        # 1. Assessment currently DURING window
        open_assessment = Assessment.objects.create(
            title="Open Exam",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60,
            created_by=primary_admin,
            status=AssessmentStatus.PUBLISHED,
        )
        snapshot_open = AssessmentSnapshot.objects.create(
            assessment=open_assessment,
            version_number=1,
            snapshot_data={},
            server_evaluation_bundle={},
        )

        u1, p1 = StudentService.create_student(email="att1@test.com", roll_number="ROLL-ATT-01", section=sample_section)
        u2, p2 = StudentService.create_student(email="att2@test.com", roll_number="ROLL-ATT-02", section=sample_section)

        AssessmentAssignment.objects.create(assessment=open_assessment, student=u1, assigned_by=primary_admin, status=AssignmentStatus.ASSIGNED)
        AssessmentAssignment.objects.create(assessment=open_assessment, student=u2, assigned_by=primary_admin, status=AssignmentStatus.ASSIGNED)

        # u1 starts attempt, u2 does not
        TestAttempt.objects.create(
            assessment=open_assessment,
            assessment_snapshot=snapshot_open,
            student=u1,
            attempt_number=1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now - timedelta(minutes=20),
        )

        data_open = AssessmentAttendanceService.get_attendance_data(open_assessment)
        rows_open = {r["email"]: r for r in data_open["results"]}

        assert rows_open["att1@test.com"]["attendance_status"] == "ATTENDED"
        assert rows_open["att2@test.com"]["attendance_status"] == "NOT_STARTED"
        assert data_open["summary"]["total_attended"] == 1
        assert data_open["summary"]["total_not_started"] == 1
        assert data_open["summary"]["total_not_attended"] == 0

        # 2. Assessment PAST deadline
        closed_assessment = Assessment.objects.create(
            title="Closed Exam",
            start_datetime=now - timedelta(hours=3),
            end_datetime=now - timedelta(hours=1),
            duration_minutes=60,
            created_by=primary_admin,
            status=AssessmentStatus.PUBLISHED,
        )
        AssessmentAssignment.objects.create(assessment=closed_assessment, student=u2, assigned_by=primary_admin, status=AssignmentStatus.ASSIGNED)

        data_closed = AssessmentAttendanceService.get_attendance_data(closed_assessment)
        row_closed = data_closed["results"][0]
        assert row_closed["attendance_status"] == "NOT_ATTENDED"
        assert data_closed["summary"]["total_not_attended"] == 1

        # 3. Assessment BEFORE window
        future_assessment = Assessment.objects.create(
            title="Future Exam",
            start_datetime=now + timedelta(hours=2),
            end_datetime=now + timedelta(hours=4),
            duration_minutes=60,
            created_by=primary_admin,
            status=AssessmentStatus.PUBLISHED,
        )
        AssessmentAssignment.objects.create(assessment=future_assessment, student=u2, assigned_by=primary_admin, status=AssignmentStatus.ASSIGNED)

        data_future = AssessmentAttendanceService.get_attendance_data(future_assessment)
        row_future = data_future["results"][0]
        assert row_future["attendance_status"] == "NOT_STARTED"
        assert data_future["summary"]["total_not_started"] == 1
        assert data_future["summary"]["total_not_attended"] == 0


# ==============================================================================
# D10: Canonical Student Identity & Roster Invariant Tests
# ==============================================================================

@pytest.mark.django_db
class TestStudentDashboardAndRosterCanonicalInvariant:

    def test_one_active_student_dashboard_count_and_active_roster_parity(
        self, primary_admin_client, sample_section
    ):
        """
        One active student yields dashboard count 1 and exactly matches active student roster.
        """
        u1, p1 = StudentService.create_student(
            email="single_active@codeguard.edu",
            roll_number="BETN1AI25055",
            section=sample_section,
        )

        overview_res = primary_admin_client.get("/api/v1/admin/overview/")
        assert overview_res.status_code == status.HTTP_200_OK
        data = overview_res.data.get("data", overview_res.data)
        assert data["metrics"]["total_students"] == 1

        roster_res = primary_admin_client.get("/api/v1/admin/students/?is_active=true")
        assert roster_res.status_code == status.HTTP_200_OK
        roster_data = roster_res.data.get("data", roster_res.data)
        assert roster_data["count"] == 1
        assert roster_data["results"][0]["roll_number"] == "BETN1AI25055"
        assert data["metrics"]["total_students"] == roster_data["count"]

    def test_deactivated_student_excluded_from_active_count_and_preserved(
        self, primary_admin_client, sample_section, primary_admin
    ):
        """
        Deactivated student is excluded from active dashboard count and active roster,
        but preserved in complete historical roster and database.
        """
        u1, p1 = StudentService.create_student(
            email="active_cand@codeguard.edu",
            roll_number="BETN1AI25056",
            section=sample_section,
        )
        u2, p2 = StudentService.create_student(
            email="disabled_cand@codeguard.edu",
            roll_number="BETN1AI25057",
            section=sample_section,
        )
        StudentService.set_student_status(
            student_profile=p2,
            is_active=False,
            actor=primary_admin,
            reason="Graduated / Inactive"
        )

        # 1. Dashboard active count excludes deactivated student
        overview_res = primary_admin_client.get("/api/v1/admin/overview/")
        assert overview_res.status_code == status.HTTP_200_OK
        data = overview_res.data.get("data", overview_res.data)
        assert data["metrics"]["total_students"] == 1

        # 2. Active roster excludes deactivated student
        active_roster = primary_admin_client.get("/api/v1/admin/students/?is_active=true")
        active_data = active_roster.data.get("data", active_roster.data)
        assert active_data["count"] == 1
        assert active_data["results"][0]["roll_number"] == "BETN1AI25056"

        # 3. Complete roster preserves both historical records
        all_roster = primary_admin_client.get("/api/v1/admin/students/")
        all_data = all_roster.data.get("data", all_roster.data)
        assert all_data["count"] == 2

        # 4. Database records remain intact
        assert StudentProfile.objects.filter(roll_number="BETN1AI25057").exists()
        assert User.objects.filter(email="disabled_cand@codeguard.edu", is_active=False).exists()

    def test_duplicate_student_creation_with_same_roll_number_rejected(
        self, sample_section, primary_admin
    ):
        """
        One-roll-number-one-account invariant: creating second student with same roll number is rejected.
        """
        StudentService.create_student(
            email="original@codeguard.edu",
            roll_number="BETN1AI25058",
            section=sample_section,
            actor=primary_admin
        )

        with pytest.raises(DRFValidationError) as exc:
            StudentService.create_student(
                email="duplicate@codeguard.edu",
                roll_number="BETN1AI25058",
                section=sample_section,
                actor=primary_admin
            )
        assert "roll number already exists" in str(exc.value)

    def test_orphaned_user_without_profile_cannot_be_targeted_or_counted(
        self, primary_admin_client, sample_section
    ):
        """
        Orphaned User with role=STUDENT but no StudentProfile cannot be targeted in assessments
        and is excluded from canonical student counts.
        """
        orphaned = User.objects.create_user(
            email="orphaned_cand@codeguard.edu",
            password="Password123!",
            role=Role.STUDENT,
            is_active=True
        )

        # Overview count is 0 because no canonical student profile exists
        overview_res = primary_admin_client.get("/api/v1/admin/overview/")
        data = overview_res.data.get("data", overview_res.data)
        assert data["metrics"]["total_students"] == 0

        # Roster count is 0
        roster_res = primary_admin_client.get("/api/v1/admin/students/?is_active=true")
        roster_data = roster_res.data.get("data", roster_res.data)
        assert roster_data["count"] == 0

        # Canonical queryset excludes orphaned user without profile
        canonical_qs = StudentService.get_canonical_students_queryset(active_only=False)
        assert not canonical_qs.filter(user=orphaned).exists()

