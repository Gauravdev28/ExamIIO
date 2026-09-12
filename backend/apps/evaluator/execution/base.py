"""
Base Execution Adapter Abstract Interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .contract import ExecutionRequest, ExecutionResult


class BaseExecutionAdapter(ABC):
    """
    Abstract interface for all sandboxed code execution adapters.
    Guarantees strict isolation and provider independence.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'PISTON', 'JUDGE0')."""
        pass

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Executes code inside an isolated sandbox environment.
        NEVER executes code on the host server or in-process.
        """
        pass

    @classmethod
    @abstractmethod
    def check_health(cls, timeout: float = 1.0) -> bool:
        """
        Fast liveness probe checking if the execution broker API is reachable.
        """
        pass

    @classmethod
    @abstractmethod
    def check_health_detailed(cls, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Comprehensive probe distinguishing:
        1. API reachable
        2. Worker operational
        3. Real sandbox execution operational
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Returns list of canonical supported language names."""
        pass
