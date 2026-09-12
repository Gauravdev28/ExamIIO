# Proctor Reattempt / Second-Chance Architecture & Implementation Plan

## 1. Objective
The Proctor Reattempt (Second-Chance) subsystem provides an authoritative, auditable, and secure mechanism to authorize a single second chance (Attempt #2) for candidates whose initial examination attempt (Attempt #1) was terminated or disqualified due to environmental, technical, or false-positive security violations.

The system ensures:
- Strict authorization gating by authorized invigilators and administrators.
- Immutable isolation between original and reattempt attempts.
- Absolute technical prevention of any 3rd attempt.
- Synchronization and real-time candidate guidance via a 60-second preparation window.

---

## 2. Architecture
The architecture spans both backend services and frontend interfaces, built around a unified state machine and atomic database transactions:
- **Backend Model Layer**: `ProctorReattemptAuthorization` tracks authorization records, state transitions, audit metadata, and one-to-one constraints per assignment.
- **Service Layer**:
  - `ProctorReattemptService`: Handles authorization validation, assignment locking, and state updates.
  - `AttemptService`: Manages attempt creation, preparation window enforcement, attempt number sequencing, and isolation.
- **Channels / WebSocket Layer**: Broadcasts real-time authorization events to the student examination room and proctoring consoles.
- **Frontend Layer**:
  - Proctor Live Console & Timeline Evidence Review for granting second chances.
  - Student Examination Room with real-time banners and a 60-second synchronized countdown timer.
  - Django Admin changelist and detail actions for administrative reauthorization.

---

## 3. Proctor Authorization
Invigilators monitoring live examination sessions can authorize a reattempt directly from the Proctor Live Console:
- The proctor reviews candidate telemetry and violation status.
- If disqualification was due to a benign issue (e.g. system update popup or peripheral disconnection), the proctor invokes the authorization API.
- The authorization endpoint requires proctor authentication, verifies the student's attempt is terminal (`CANCELLED` or `SUBMITTED`), and ensures no prior authorization exists for the assignment.
- Upon creation, the authorization record enters the `AUTHORIZED` state, and a WebSocket event (`REATTEMPT_AUTHORIZED`) is pushed immediately to the student room.

---

## 4. Admin Authorization
Administrators have access to a dedicated Django Admin action ("Give Student Another Chance"):
- Available on both the `TestAttempt` changelist (as an intermediate action page) and the change view.
- Provides reason selection (`HARDWARE_FAILURE`, `NETWORK_DISRUPTION`, `ENVIRONMENTAL_DISTURBANCE`, `FALSE_POSITIVE_SECURITY`, `ADMINISTRATIVE_DISCRETION`, `OTHER`).
- When `OTHER` is selected, an explanatory note is strictly required.
- Calls `ProctorReattemptService.authorize_reattempt()` under the hood, guaranteeing consistent business rules, locking, and audit identity.

---

## 5. Timeline Authorization
In the Proctoring Timeline & Evidence Review modal:
- A distinct "Second-Chance Action" card is integrated without altering the four authoritative Human Review Verdicts (`CLEAN`, `CONFIRMED_VIOLATION`, `FURTHER_REVIEW`, `FALSE_POSITIVE`).
- Displays candidate details, prior attempt status, and reattempt eligibility (`can_grant_reattempt`).
- Includes a confirmation dialog with reason selection and note input.
- Automatically refreshes timeline state upon granting and displays authorized/consumed status.

---

## 6. Reattempt Reasons
Standardized reasons categorized in `ReattemptReason`:
- `HARDWARE_FAILURE`: Camera, microphone, keyboard, or display malfunction.
- `NETWORK_DISRUPTION`: Transient connectivity drop or network failure.
- `ENVIRONMENTAL_DISTURBANCE`: External noise, proctor room disruption, or proctor instructions.
- `FALSE_POSITIVE_SECURITY`: Security policy triggered by benign background processes.
- `ADMINISTRATIVE_DISCRETION`: Institutional or administrative second chance.
- `OTHER`: Exceptional circumstances requiring mandatory documentation notes.

---

## 7. Authorization State Machine
The lifecycle of a `ProctorReattemptAuthorization` record follows a strict three-state machine:
1. `AUTHORIZED`: Granted by proctor or admin; valid for student consumption within 15 minutes.
2. `CONSUMED`: Successfully transitioned when the candidate launches Attempt #2 via `AttemptService.start_attempt()`.
3. `EXPIRED`: Revoked or timed out if not consumed within the validity window.

Transitions are enforced through atomic database operations and row-level locks, preventing replay or concurrent use.

---

## 8. 60-Second Preparation Window
When reattempt authorization is granted:
- `authorized_at` timestamps the event, and `preparation_window_ends_at = authorized_at + 60s`.
- If the student attempts to launch Attempt #2 before the window elapses, the backend responds with HTTP 400 `REATTEMPT_PREPARING` and the remaining seconds.
- The student room displays a prominent banner with a synchronized 60-second countdown (`Ready in Xs`).
- The launch button is enabled only once the preparation delay has elapsed.

---

## 9. Attempt #2 Creation
When the candidate initiates Attempt #2:
- `AttemptService.start_attempt()` acquires a `select_for_update()` lock on the candidate's `AssessmentAssignment`.
- Confirms the authorization is in `AUTHORIZED` status and preparation window has completed.
- Atomically creates a fresh `TestAttempt` with `attempt_number=2`.
- Snapshots fresh question sets and initializes new proctoring and telemetry sessions.
- Transitions the authorization status from `AUTHORIZED` to `CONSUMED`.

---

## 10. Attempt #3 Prevention
Absolute technical guardrails guarantee that no student can ever receive a third attempt:
- `AssessmentAssignment` checks `attempts.count() < assignment.max_attempts` (max_attempts = 2).
- Unique database constraints enforce `unique_together = ('assignment', 'attempt_number')`.
- `ProctorReattemptAuthorization` enforces `OneToOneField(AssessmentAssignment)` or unique assignment constraint, preventing duplicate reattempt authorizations.
- If `attempt_number >= 2`, any further attempt creation is rejected unconditionally with HTTP 403 / 400.

---

## 11. Locking and Concurrency
To eliminate race conditions:
- All mutations run within `transaction.atomic()`.
- `AssessmentAssignment.objects.select_for_update()` is acquired before inspecting prior attempts or authorizations.
- Concurrent proctor requests or simultaneous student clicks are serialized safely: the first transaction consumes the authorization, and subsequent calls see status `CONSUMED` or existing Attempt #2.

---

## 12. Result Isolation
Candidate answers, telemetry, and evaluation results are completely isolated between attempts:
- `AttemptAnswer`, `ProctoringSession`, and `ProctoringEvent` foreign keys point directly to specific `TestAttempt` IDs.
- Disqualification or cancellation of Attempt #1 has zero negative scoring impact on Attempt #2.
- `AssessmentResult` records are scoped to `attempt_id`, ensuring non-interference.

---

## 13. Certificate Behavior
Certificates are generated exclusively for successfully submitted attempts:
- Disqualified or cancelled attempts (`Attempt #1`) produce no certificate.
- When `Attempt #2` is completed and evaluated, certification criteria are evaluated solely against Attempt #2 score and integrity verdict.
- Verification links resolve to the authoritative passing attempt record.

---

## 14. Audit Trail
Comprehensive audit logging tracks all administrative and proctor actions:
- Every reattempt authorization records:
  - `authorized_by_id`: Proscribed user ID of the proctor or admin.
  - `authorized_at`: Exact UTC timestamp.
  - `reason` and `notes`: Auditable justification.
  - `ip_address`: Network origin of the authorization request.
- `AuditLog` records entry and state transitions for regulatory and institutional auditing.

---

## 15. WebSocket Notification
Real-time state changes are broadcast via Django Channels:
- Broadcast topic: `assessment_{assessment_id}_student_{student_id}` and `proctor_live_{assessment_id}`.
- Event payload:
  ```json
  {
    "type": "REATTEMPT_AUTHORIZED",
    "attempt_id": "<attempt-1-uuid>",
    "authorized_at": "2026-09-13T02:00:00Z",
    "preparation_window_ends_at": "2026-09-13T02:01:00Z",
    "remaining_seconds": 60,
    "reason": "FALSE_POSITIVE_SECURITY"
  }
  ```
- Student UI updates reactively without requiring full page reload.

---

## 16. Frontend Architecture
Built with React, TypeScript, and Tailwind CSS:
- Components subscribe to authorization state and countdown timers.
- Clean separation between standard proctoring event telemetry and reattempt action controls.
- Defensive error handling with modal alerts, countdown tickers, and state synchronizers.

---

## 17. Backend Architecture
Built with Django and Django REST Framework:
- Modular app structure: `apps.invigilation`, `apps.assessments`, `apps.proctoring`.
- Robust permission policies (`IsProctorOrAdmin`, `IsAssessmentActive`).
- Reusable service APIs avoiding duplication across Django Admin and DRF views.

---

## 18. Testing
A comprehensive automated test suite validates the entire workflow:
- `test_proctor_reattempt.py`: Validates authorization, 60s delay, Attempt #2 creation, and Attempt #3 prevention.
- `test_admin_reattempt.py`: Validates Django Admin action, confirmation flow, permissions, and audit trails.
- `test_proctoring_timeline_reattempt.py`: Validates timeline serialization, UI payload, and second-chance granting.
- `test_manual_verification_scenario.py`: End-to-end multi-step scenario tests replicating production exam conditions.

---

## 19. Verification
Full end-to-end verification confirms:
- Backend test suite: All reattempt, proctoring, assessment, and coding tests pass.
- Frontend build: TypeScript typecheck and production build pass with zero warnings/errors.
- Security isolation: Zero leakage of Safe Browser artifacts into the clean repository.
