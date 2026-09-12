"""
Code Execution Domain Service and Provider Factory.
"""
import logging
from typing import Dict, Any, Optional
from django.conf import settings

from .base import BaseExecutionAdapter
from .contract import ExecutionRequest, ExecutionResult, ExecutionStatus
from .piston import PistonAdapter
from .judge0 import Judge0Adapter
from .exceptions import ExecutionError, LanguageConfigurationError

logger = logging.getLogger('codeguard.evaluator')


class ExecutionProviderFactory:
    """
    Centralized factory for resolving and instantiating sandbox execution providers.
    """
    _instances: Dict[str, BaseExecutionAdapter] = {}

    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> BaseExecutionAdapter:
        name = (provider_name or getattr(settings, 'CODE_EXECUTION_PROVIDER', 'PISTON')).strip().upper()
        if name not in cls._instances:
            if name == 'PISTON':
                cls._instances[name] = PistonAdapter()
            elif name == 'JUDGE0':
                cls._instances[name] = Judge0Adapter()
            else:
                logger.warning(f"Unknown code execution provider '{name}', falling back to PISTON.")
                cls._instances[name] = PistonAdapter()
        return cls._instances[name]


class CodeExecutionService:
    """
    Authoritative service orchestrating isolated code execution through active provider.
    Evaluator subsystem interacts exclusively with this service.
    """

    @classmethod
    def execute(
        cls,
        request: ExecutionRequest,
        provider_name: Optional[str] = None
    ) -> ExecutionResult:
        provider = ExecutionProviderFactory.get_provider(provider_name)

        logger.info(
            f"code_execution_started | provider={provider.name} | language={request.language} | "
            f"submission={request.submission_id or 'adhoc'} | question={request.question_id or 'none'} | "
            f"tc_index={request.test_case_index if request.test_case_index is not None else 'all'} | "
            f"hidden={request.is_hidden}"
        )

        result = provider.execute(request)

        # Structured audit logging based on status
        log_ctx = (
            f"provider={result.provider} | status={result.status} | "
            f"language={result.language} | time_ms={result.execution_time_ms} | "
            f"submission={request.submission_id or 'adhoc'} | question={request.question_id or 'none'}"
        )

        if result.status == ExecutionStatus.ACCEPTED.value:
            logger.info(f"code_execution_completed | {log_ctx}")
        elif result.status == ExecutionStatus.COMPILATION_ERROR.value:
            logger.info(f"code_compilation_error | {log_ctx}")
        elif result.status == ExecutionStatus.RUNTIME_ERROR.value:
            logger.info(f"code_runtime_error | {log_ctx}")
        elif result.status == ExecutionStatus.TIME_LIMIT.value:
            logger.warning(f"code_time_limit_exceeded | {log_ctx}")
        elif result.status == ExecutionStatus.MEMORY_LIMIT.value:
            logger.warning(f"code_memory_limit_exceeded | {log_ctx}")
        elif result.status == ExecutionStatus.OUTPUT_LIMIT.value:
            logger.warning(f"code_output_limit_exceeded | {log_ctx}")
        elif result.status == ExecutionStatus.SANDBOX_UNAVAILABLE.value:
            logger.error(f"code_sandbox_unavailable | {log_ctx} | error={result.stderr}")
        elif result.status in (ExecutionStatus.JUDGE_INTERNAL_ERROR.value, ExecutionStatus.SYSTEM_ERROR.value):
            logger.error(f"code_provider_internal_error | {log_ctx} | error={result.stderr}")

        return result

    @classmethod
    def check_health(cls, provider_name: Optional[str] = None, timeout: float = 1.0) -> bool:
        provider = ExecutionProviderFactory.get_provider(provider_name)
        return provider.check_health(timeout=timeout)

    @classmethod
    def check_health_detailed(cls, provider_name: Optional[str] = None, timeout: float = 2.0) -> Dict[str, Any]:
        provider = ExecutionProviderFactory.get_provider(provider_name)
        return provider.check_health_detailed(timeout=timeout)
