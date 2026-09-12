"""
Self-Hosted Piston Sandbox Execution Adapter.
"""
import logging
import time
import requests
from typing import Dict, Any, List, Optional
from django.conf import settings

from .base import BaseExecutionAdapter
from .contract import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    CanonicalLanguage,
)
from .exceptions import (
    LanguageConfigurationError,
    SandboxUnavailableError,
)

logger = logging.getLogger('codeguard.evaluator')


DEFAULT_PISTON_LANGUAGE_CONFIG = {
    'PYTHON': {
        'language': 'python',
        'aliases': ['python3', 'py'],
        'version': '3.10.0',
        'file_name': 'solution.py',
    },
    'CPP': {
        'language': 'c++',
        'aliases': ['cpp', 'g++', 'cxx'],
        'version': '10.2.0',
        'file_name': 'solution',
    },
    'JAVA': {
        'language': 'java',
        'aliases': ['openjdk'],
        'version': '15.0.2',
        'file_name': 'Main',
    },
    'C': {
        'language': 'c',
        'aliases': ['gcc', 'clang'],
        'version': '10.2.0',
        'file_name': 'solution',
    },
}


class PistonAdapter(BaseExecutionAdapter):
    """
    Adapter interfacing with self-hosted Piston isolated code execution broker.
    Executes Python, C++, Java, and C code inside isolated unprivileged container sandboxes.
    Fail-closed: NEVER executes candidate code on host.
    """

    @property
    def name(self) -> str:
        return "PISTON"

    @classmethod
    def get_piston_url(cls) -> str:
        url = getattr(settings, 'PISTON_URL', None) or 'http://127.0.0.1:2000'
        return url.rstrip('/')

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        return [
            CanonicalLanguage.PYTHON.value,
            CanonicalLanguage.CPP.value,
            CanonicalLanguage.JAVA.value,
            CanonicalLanguage.C.value,
        ]

    @classmethod
    def resolve_language_config(cls, canonical_lang: str) -> Dict[str, Any]:
        lang_upper = CanonicalLanguage.normalize(canonical_lang)
        custom_config = getattr(settings, 'PISTON_LANGUAGE_MAP', None)
        if custom_config and lang_upper in custom_config:
            return custom_config[lang_upper]
        if lang_upper in DEFAULT_PISTON_LANGUAGE_CONFIG:
            return DEFAULT_PISTON_LANGUAGE_CONFIG[lang_upper]
        raise LanguageConfigurationError(
            f"Unsupported execution language for Piston: '{canonical_lang}'. Supported: {cls.get_supported_languages()}"
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Executes code inside the isolated Piston sandbox via HTTP API.
        Enforces server-side limits and provides deterministic normalized results.
        """
        piston_url = self.get_piston_url()
        timeout = float(getattr(settings, 'PISTON_TIMEOUT_SECONDS', 10))

        try:
            lang_cfg = self.resolve_language_config(request.language)
        except LanguageConfigurationError as e:
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.SYSTEM_ERROR.value,
                stderr=str(e),
                infrastructure_error=True,
                normalized_verdict=ExecutionStatus.SYSTEM_ERROR.value,
            )

        payload = {
            "language": lang_cfg['language'],
            "version": lang_cfg.get('version', '*'),
            "files": [
                {
                    "name": lang_cfg.get('file_name', 'solution.txt'),
                    "content": request.source_code,
                }
            ],
            "stdin": request.stdin or "",
            "args": [],
            "compile_timeout": min(10000, max(2000, request.cpu_time_limit_ms * 2)),
            "run_timeout": request.cpu_time_limit_ms,
            "compile_memory_limit": request.memory_limit_mb * 1024 * 1024,
            "run_memory_limit": request.memory_limit_mb * 1024 * 1024,
        }

        endpoint = f"{piston_url}/api/v2/execute"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_key = getattr(settings, 'PISTON_API_KEY', '')
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start_time = time.time()
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            exec_duration_ms = int(round((time.time() - start_time) * 1000))

            if response.status_code != 200:
                logger.error(f"Piston external sandbox returned HTTP {response.status_code}: {response.text}")
                return ExecutionResult(
                    provider=self.name,
                    language=request.language,
                    status=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                    stderr=f"FAIL_CLOSED: Piston HTTP {response.status_code}",
                    execution_time_ms=exec_duration_ms,
                    infrastructure_error=True,
                    normalized_verdict=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                )

            data = response.json()
            return self._normalize_piston_response(data, request, exec_duration_ms)

        except requests.exceptions.RequestException as e:
            logger.error(f"Piston external sandbox connection error: {e}")
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                stderr=f"FAIL_CLOSED: Sandbox unavailable ({e})",
                infrastructure_error=True,
                normalized_verdict=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
            )
        except Exception as e:
            logger.error(f"Unexpected error executing via Piston: {e}", exc_info=True)
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.SYSTEM_ERROR.value,
                stderr=f"FAIL_CLOSED: Execution interface error ({e})",
                infrastructure_error=True,
                normalized_verdict=ExecutionStatus.SYSTEM_ERROR.value,
            )

    def _normalize_piston_response(
        self,
        data: Dict[str, Any],
        request: ExecutionRequest,
        wall_time_ms: int
    ) -> ExecutionResult:
        """
        Translates Piston execution payload to canonical ExecutionResult.
        """
        compile_stage = data.get('compile') or {}
        run_stage = data.get('run') or {}

        compile_code = compile_stage.get('code')
        compile_output = compile_stage.get('output') or compile_stage.get('stderr') or ""
        compile_signal = compile_stage.get('signal')
        compile_status = compile_stage.get('status')
        compile_message = compile_stage.get('message') or ''

        # 1. Check Compilation Stage Failure (e.g. GCC/G++)
        if compile_code is not None and compile_code != 0:
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.COMPILATION_ERROR.value,
                stdout="",
                stderr="",
                compile_output=compile_output.strip() or "Compilation failed.",
                execution_time_ms=wall_time_ms,
                exit_code=compile_code,
                raw_provider_status=f"compile_exit_{compile_code}",
                normalized_verdict=ExecutionStatus.COMPILATION_ERROR.value,
            )

        run_code = run_stage.get('code', 0)
        run_signal = run_stage.get('signal')
        run_status = run_stage.get('status')
        run_message = run_stage.get('message') or ''
        stdout = run_stage.get('stdout', '') or ''
        stderr = run_stage.get('stderr', '') or ''
        output = run_stage.get('output', '') or ''

        # 2. Check Timeout
        if (
            run_signal == 'SIGKILL'
            or compile_signal == 'SIGKILL'
            or run_code == 137
            or run_status == 'TO'
            or compile_status == 'TO'
            or 'Timed out' in output
            or 'time limit exceeded' in run_message.lower()
            or 'time limit exceeded' in compile_message.lower()
            or 'timed out' in stderr.lower()
        ):
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.TIME_LIMIT.value,
                stdout=stdout,
                stderr=stderr or "Time Limit Exceeded",
                execution_time_ms=request.cpu_time_limit_ms,
                exit_code=run_code,
                raw_provider_status="SIGKILL_TIMEOUT",
                normalized_verdict=ExecutionStatus.TIME_LIMIT.value,
            )

        # 3. Check Output Limit
        if len(stdout) > request.max_stdout_bytes or len(output) > request.max_stdout_bytes:
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.OUTPUT_LIMIT.value,
                stdout=stdout[:request.max_stdout_bytes],
                stderr="Output Limit Exceeded",
                execution_time_ms=wall_time_ms,
                exit_code=run_code,
                raw_provider_status="OUTPUT_LIMIT",
                normalized_verdict=ExecutionStatus.OUTPUT_LIMIT.value,
            )

        # 4. Check Memory Limit
        if (
            'Memory Limit Exceeded' in stderr
            or 'Out of memory' in stderr
            or run_signal == 'SIGSEGV'
            or run_status == 'MLE'
            or compile_status == 'MLE'
            or 'memory limit exceeded' in run_message.lower()
            or 'memory limit exceeded' in compile_message.lower()
        ):
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.MEMORY_LIMIT.value,
                stdout=stdout,
                stderr=stderr or "Memory Limit Exceeded",
                execution_time_ms=wall_time_ms,
                exit_code=run_code,
                raw_provider_status="MEMORY_LIMIT",
                normalized_verdict=ExecutionStatus.MEMORY_LIMIT.value,
            )

        # 5. Check Java Compilation Failure & Python Syntax/Indentation Errors in Run Stage
        norm_lang = CanonicalLanguage.normalize(request.language)
        if norm_lang == 'JAVA' and run_code != 0 and ('compilation failed' in stderr.lower() or 'compilation failed' in output.lower()):
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.COMPILATION_ERROR.value,
                stdout="",
                stderr="",
                compile_output=(stderr.strip() or output.strip() or "Compilation failed."),
                execution_time_ms=wall_time_ms,
                exit_code=run_code,
                raw_provider_status="java_compilation_error",
                normalized_verdict=ExecutionStatus.COMPILATION_ERROR.value,
            )

        if norm_lang == 'PYTHON' and run_code != 0 and any(err_type in stderr for err_type in ('SyntaxError:', 'IndentationError:', 'TabError:')):
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.COMPILATION_ERROR.value,
                stdout="",
                stderr="",
                compile_output=stderr.strip(),
                execution_time_ms=wall_time_ms,
                exit_code=run_code,
                raw_provider_status="python_syntax_error",
                normalized_verdict=ExecutionStatus.COMPILATION_ERROR.value,
            )

        # 6. Check Runtime Error (Non-zero exit code)
        if run_code != 0:
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.RUNTIME_ERROR.value,
                stdout=stdout,
                stderr=stderr or output,
                execution_time_ms=wall_time_ms,
                exit_code=run_code,
                raw_provider_status=f"run_exit_{run_code}",
                normalized_verdict=ExecutionStatus.RUNTIME_ERROR.value,
            )

        # 7. Clean Execution Completion (Exit Code 0 — output comparator evaluates pass vs wrong answer)
        return ExecutionResult(
            provider=self.name,
            language=request.language,
            status=ExecutionStatus.ACCEPTED.value,
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_output or None,
            execution_time_ms=wall_time_ms,
            exit_code=0,
            raw_provider_status="SUCCESS",
            normalized_verdict=ExecutionStatus.ACCEPTED.value,
        )

    @classmethod
    def check_health(cls, timeout: float = 1.0) -> bool:
        """
        Fast liveness probe checking Piston HTTP reachability.
        """
        piston_url = cls.get_piston_url()
        try:
            resp = requests.get(f"{piston_url}/api/v2/runtimes", timeout=timeout)
            return resp.status_code == 200 and isinstance(resp.json(), list)
        except Exception:
            return False

    @classmethod
    def check_health_detailed(cls, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Comprehensive 3-point health verification:
        1. API Reachable
        2. Runtimes Installed (Python, GCC, Java)
        3. Real Sandbox Execution Probe
        """
        piston_url = cls.get_piston_url()
        api_reachable = False
        worker_operational = False
        execution_operational = False
        runtimes = []

        # 1. Query Runtimes
        try:
            resp = requests.get(f"{piston_url}/api/v2/runtimes", timeout=timeout)
            if resp.status_code == 200:
                api_reachable = True
                data = resp.json()
                if isinstance(data, list):
                    runtimes = data
                    worker_operational = len(runtimes) > 0
        except Exception as e:
            logger.debug(f"Piston API unreachable: {e}")

        # 2. Execute Real Sandbox Probe
        if api_reachable:
            try:
                adapter = cls()
                probe_req = ExecutionRequest(
                    source_code="print('CODEGUARD_HEALTH')",
                    language="PYTHON",
                    cpu_time_limit_ms=2000,
                )
                res = adapter.execute(probe_req)
                if res.status == ExecutionStatus.ACCEPTED.value and "CODEGUARD_HEALTH" in res.stdout:
                    execution_operational = True
            except Exception as e:
                logger.debug(f"Piston execution probe failed: {e}")

        healthy = api_reachable and worker_operational and execution_operational
        return {
            "provider": "PISTON",
            "healthy": healthy,
            "api_reachable": api_reachable,
            "worker_operational": worker_operational,
            "execution_operational": execution_operational,
            "runtimes_count": len(runtimes),
            "runtimes": [f"{r.get('language')}@{r.get('version')}" for r in runtimes[:10]],
        }
