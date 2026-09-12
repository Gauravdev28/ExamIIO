"""
Authoritative centralized policy for browser security events in ExamIIO / CODEGUARD.

Enforces strict distinction between:
1. Immediate Cancellation Violations (9 canonical Phase 2 security events)
2. Telemetry-Only Events (viewport resize, screenshot, peripheral status)
3. Legacy Termination-Pending Events (120-second grace period for backward compatibility)
"""
from typing import Set, Optional, Dict, Any


class BrowserSecurityPolicy:
    """
    Centralized authoritative policy defining browser security event categories,
    validation allowlists, and cancellation rationale.
    """

    # 1. Authoritative Phase 2 Browser Security Violations -> IMMEDIATE CANCELLATION (Zero grace period)
    IMMEDIATE_CANCELLATION_EVENTS: Set[str] = {
        'TAB_SWITCH',
        'WINDOW_FOCUS_LOST',
        'FULLSCREEN_EXIT',
        'COPY_ATTEMPT',
        'PASTE_ATTEMPT',
        'CUT_ATTEMPT',
        'CONTEXT_MENU_ATTEMPT',
        'PROTECTED_KEYBOARD_ATTEMPT',
        'NAVIGATION_VIOLATION',
    }

    # 2. Telemetry-Only Events -> Recorded, NEVER automatically cancel or trigger pending termination
    TELEMETRY_ONLY_EVENTS: Set[str] = {
        'WINDOW_RESIZE',
        'SCREENSHOT_ATTEMPT',
        'FULLSCREEN_ENTER',
        'CAMERA_UNAVAILABLE',
        'MICROPHONE_UNAVAILABLE',
    }

    # 3. Legacy Termination-Pending Events -> Retained for existing 120-second pending countdown workflows
    TERMINATION_PENDING_EVENTS: Set[str] = {
        'WINDOW_BLUR',
        'PAGE_VISIBILITY_CHANGE',
    }

    # Authoritative Allowlist: All valid client-ingestible event types
    ALL_ALLOWED_EVENTS: Set[str] = (
        IMMEDIATE_CANCELLATION_EVENTS | TELEMETRY_ONLY_EVENTS | TERMINATION_PENDING_EVENTS
    )

    # Standard audit and candidate-safe reason mappings (Never reveal or infer external app identities)
    CANCELLATION_REASONS: Dict[str, str] = {
        'TAB_SWITCH': 'EXAMINATION TERMINATED — TAB SWITCH DETECTED',
        'WINDOW_FOCUS_LOST': 'EXAMINATION TERMINATED — WINDOW FOCUS LOST',
        'FULLSCREEN_EXIT': 'EXAMINATION TERMINATED — FULLSCREEN EXITED',
        'COPY_ATTEMPT': 'EXAMINATION TERMINATED — CLIPBOARD COPY DETECTED',
        'PASTE_ATTEMPT': 'EXAMINATION TERMINATED — CLIPBOARD PASTE DETECTED',
        'CUT_ATTEMPT': 'EXAMINATION TERMINATED — CLIPBOARD CUT DETECTED',
        'CONTEXT_MENU_ATTEMPT': 'EXAMINATION TERMINATED — CONTEXT MENU / RIGHT-CLICK DETECTED',
        'PROTECTED_KEYBOARD_ATTEMPT': 'EXAMINATION TERMINATED — RESTRICTED KEYBOARD SHORTCUT DETECTED',
        'NAVIGATION_VIOLATION': 'EXAMINATION TERMINATED — UNAUTHORIZED NAVIGATION / ROOM EXIT',
    }

    @classmethod
    def is_immediate_cancellation_event(cls, event_type: str) -> bool:
        """
        Returns True if event_type is an authoritative browser security violation
        requiring immediate transition of an IN_PROGRESS attempt to CANCELLED.
        """
        return event_type in cls.IMMEDIATE_CANCELLATION_EVENTS

    @classmethod
    def is_telemetry_only(cls, event_type: str) -> bool:
        """
        Returns True if event_type is purely telemetry and must not alter attempt status.
        """
        return event_type in cls.TELEMETRY_ONLY_EVENTS

    @classmethod
    def is_termination_pending_event(cls, event_type: str) -> bool:
        """
        Returns True if event_type routes to the legacy 120-second termination pending workflow.
        """
        return event_type in cls.TERMINATION_PENDING_EVENTS

    @classmethod
    def is_valid_event_type(cls, event_type: str) -> bool:
        """
        Validates event_type against the authoritative allowlist.
        """
        return event_type in cls.ALL_ALLOWED_EVENTS

    @classmethod
    def get_cancellation_reason(cls, event_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Returns an authoritative, auditable, candidate-visible disqualification reason.
        Does NOT infer or record external application names.
        """
        return cls.CANCELLATION_REASONS.get(
            event_type,
            f"EXAMINATION TERMINATED — SECURITY VIOLATION: {event_type}"
        )

    @classmethod
    def get_termination_reason_code(cls, event_type: str) -> str:
        """
        Returns machine-readable termination reason code for audit and attempt models.
        """
        return f"SECURITY_VIOLATION_{event_type}"
