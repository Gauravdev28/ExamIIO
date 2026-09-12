"""
Canonical Contract and Data Models for CODEGUARD Code Execution.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class CanonicalLanguage(str, Enum):
    PYTHON = 'PYTHON'
    CPP = 'CPP'
    JAVA = 'JAVA'
    C = 'C'

    @classmethod
    def normalize(cls, lang: str) -> str:
        if not lang:
            return cls.PYTHON.value
        val = lang.strip().upper()
        if val in ('PY', 'PYTHON', 'PYTHON3', 'PYTHON3.10', 'PYTHON3.11'):
            return cls.PYTHON.value
        if val in ('CPP', 'C++', 'G++', 'GCC_CPP', 'CLANG_CPP', 'CXX'):
            return cls.CPP.value
        if val in ('JAVA', 'OPENJDK', 'JAVA15', 'JAVA17', 'JAVA21'):
            return cls.JAVA.value
        if val in ('C', 'GCC', 'CLANG', 'C10', 'C11', 'C99', 'C89'):
            return cls.C.value
        return val


class ExecutionStatus(str, Enum):
    ACCEPTED = 'ACCEPTED'
    WRONG_ANSWER = 'WRONG_ANSWER'
    COMPILATION_ERROR = 'COMPILATION_ERROR'
    RUNTIME_ERROR = 'RUNTIME_ERROR'
    TIME_LIMIT = 'TIME_LIMIT'
    MEMORY_LIMIT = 'MEMORY_LIMIT'
    OUTPUT_LIMIT = 'OUTPUT_LIMIT'
    SANDBOX_UNAVAILABLE = 'SANDBOX_UNAVAILABLE'
    WORKER_UNAVAILABLE = 'WORKER_UNAVAILABLE'
    JUDGE_INTERNAL_ERROR = 'JUDGE_INTERNAL_ERROR'
    SYSTEM_ERROR = 'SYSTEM_ERROR'

    @property
    def is_terminal_failure(self) -> bool:
        return self in (
            ExecutionStatus.COMPILATION_ERROR,
            ExecutionStatus.RUNTIME_ERROR,
            ExecutionStatus.TIME_LIMIT,
            ExecutionStatus.MEMORY_LIMIT,
            ExecutionStatus.OUTPUT_LIMIT,
        )

    @property
    def is_infrastructure_failure(self) -> bool:
        return self in (
            ExecutionStatus.SANDBOX_UNAVAILABLE,
            ExecutionStatus.WORKER_UNAVAILABLE,
            ExecutionStatus.JUDGE_INTERNAL_ERROR,
            ExecutionStatus.SYSTEM_ERROR,
        )


@dataclass
class ExecutionRequest:
    """
    Immutable execution request dispatched to a sandbox provider.
    """
    source_code: str
    language: str
    stdin: str = ""
    expected_output: str = ""
    cpu_time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    max_stdout_bytes: int = 65536
    attempt_id: Optional[str] = None
    question_id: Optional[str] = None
    submission_id: Optional[str] = None
    test_case_index: Optional[int] = None
    is_hidden: bool = False

    def __post_init__(self):
        # Server-side safety clamp limits
        self.cpu_time_limit_ms = max(100, min(10000, int(self.cpu_time_limit_ms or 2000)))
        self.memory_limit_mb = max(16, min(1024, int(self.memory_limit_mb or 256)))
        self.max_stdout_bytes = max(1024, min(1048576, int(self.max_stdout_bytes or 65536)))
        self.language = CanonicalLanguage.normalize(self.language)


@dataclass
class ExecutionResult:
    """
    Standardized, provider-neutral execution result returned from any execution adapter.
    """
    provider: str
    language: str
    status: str
    stdout: str = ""
    stderr: str = ""
    compile_output: Optional[str] = None
    execution_time_ms: int = 0
    memory_kb: int = 0
    exit_code: Optional[int] = None
    token: Optional[str] = None
    raw_provider_status: Optional[str] = None
    infrastructure_error: bool = False
    normalized_verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "language": self.language,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "compile_output": self.compile_output,
            "execution_time_ms": self.execution_time_ms,
            "memory_kb": self.memory_kb,
            "exit_code": self.exit_code,
            "token": self.token,
            "raw_provider_status": self.raw_provider_status,
            "infrastructure_error": self.infrastructure_error,
            "normalized_verdict": self.normalized_verdict or self.status,
        }
