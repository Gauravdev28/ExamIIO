"""
Exceptions for CODEGUARD Sandbox and Code Execution Subsystem.
"""
from rest_framework.exceptions import ValidationError as DRFValidationError


class ExecutionError(Exception):
    """Base exception for all code execution and sandbox errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SandboxUnavailableError(ExecutionError):
    """Raised when the execution sandbox/broker is completely unreachable or offline."""
    pass


class LanguageConfigurationError(DRFValidationError, ValueError, ExecutionError):
    """
    Raised when a requested execution language is not configured or unsupported.
    Inherits from DRFValidationError and ValueError for clean API boundary handling.
    """
    pass


class ProviderInternalError(ExecutionError):
    """Raised when the sandbox provider encounters an internal infrastructure error (e.g. cgroups failure)."""
    pass


class CompilationError(ExecutionError):
    """Raised when source code compilation fails."""
    pass


class ExecutionTimeoutError(ExecutionError):
    """Raised when code execution exceeds the allocated CPU or wall time limit."""
    pass


class MemoryLimitExceededError(ExecutionError):
    """Raised when code execution exceeds the allocated memory limit."""
    pass


class OutputLimitExceededError(ExecutionError):
    """Raised when code execution stdout/stderr exceeds the maximum byte limit."""
    pass
