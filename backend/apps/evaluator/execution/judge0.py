"""
Judge0 Community Edition Sandbox Execution Adapter.
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


DEFAULT_JUDGE0_LANGUAGE_MAP = {
    'PYTHON': 71,   # Python (3.8.1 / 3.11)
    'CPP': 54,      # C++ (GCC 9.2.0 / GCC 13)
    'JAVA': 62,     # Java (OpenJDK 13.0.1 / OpenJDK 17)
    'C': 50,        # C (GCC 9.2.0 / GCC 13)
}


class Judge0Adapter(BaseExecutionAdapter):
    """
    Adapter interfacing with self-hosted Judge0 CE broker via HTTP API.
    Maintains compatibility with existing Judge0 settings and deployments.
    """

    DEFAULT_LANGUAGE_MAP = DEFAULT_JUDGE0_LANGUAGE_MAP
    LANGUAGE_IDS = DEFAULT_JUDGE0_LANGUAGE_MAP

    @property
    def name(self) -> str:
        return "JUDGE0"

    @classmethod
    def get_judge0_url(cls) -> str:
        url = getattr(settings, 'JUDGE0_URL', None) or 'http://127.0.0.1:2358'
        return url.rstrip('/')

    @classmethod
    def get_language_map(cls) -> Dict[str, int]:
        custom_map = getattr(settings, 'JUDGE0_LANGUAGE_MAP', None)
        if custom_map is not None:
            return custom_map
        return cls.DEFAULT_LANGUAGE_MAP

    @classmethod
    def get_language_id(cls, language: str) -> int:
        lang_upper = CanonicalLanguage.normalize(language)
        lang_map = cls.get_language_map()
        if lang_upper in lang_map:
            val = lang_map[lang_upper]
            if val is None or not isinstance(val, int):
                raise LanguageConfigurationError(f"Missing configured Judge0 runtime ID for language '{language}'.")
            return val
        raise LanguageConfigurationError(
            f"Unsupported execution language for Judge0: '{language}'. Supported: {list(lang_map.keys())}"
        )

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        return list(cls.get_language_map().keys())

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Executes code inside the isolated Judge0 CE sandbox via HTTP API.
        NEVER executes code on host.
        """
        judge0_url = self.get_judge0_url()
        api_key = getattr(settings, 'JUDGE0_API_KEY', '')
        timeout = float(getattr(settings, 'JUDGE0_TIMEOUT_SECONDS', 10))

        try:
            lang_id = self.get_language_id(request.language)
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
            "source_code": request.source_code,
            "language_id": lang_id,
            "stdin": request.stdin or "",
            "expected_output": request.expected_output or "",
            "cpu_time_limit": max(0.1, request.cpu_time_limit_ms / 1000.0),
            "memory_limit": request.memory_limit_mb * 1024,
            "max_file_size": max(1, min(4096, int(request.max_stdout_bytes / 1024))),
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["X-Auth-Token"] = api_key
            headers["X-RapidAPI-Key"] = api_key

        endpoint = f"{judge0_url}/submissions/?base64_encoded=false&wait=true"

        start_time = time.time()
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            exec_duration_ms = int(round((time.time() - start_time) * 1000))

            if response.status_code not in (200, 201):
                logger.error(f"Judge0 external sandbox HTTP error {response.status_code}: {response.text}")
                return ExecutionResult(
                    provider=self.name,
                    language=request.language,
                    status=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                    stderr=f"FAIL_CLOSED: Judge0 HTTP {response.status_code}",
                    execution_time_ms=exec_duration_ms,
                    infrastructure_error=True,
                    normalized_verdict=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                )

            data = response.json()
            status_obj = data.get('status') or {}
            status_id = status_obj.get('id', 13) if isinstance(status_obj, dict) else (data.get('status_id') or 13)
            status_desc = status_obj.get('description', 'Internal Error') if isinstance(status_obj, dict) else str(data.get('status_description') or 'Internal Error')
            token = data.get('token')

            # Token-based asynchronous polling if Judge0 queued or is processing the submission
            if status_id in (1, 2) and token:
                poll_interval = float(getattr(settings, 'JUDGE0_POLL_INTERVAL_SEC', 0.5))
                max_poll_timeout = float(getattr(settings, 'JUDGE0_MAX_POLL_TIMEOUT_SEC', 15))
                poll_start = time.time()
                while status_id in (1, 2) and (time.time() - poll_start) < max_poll_timeout:
                    time.sleep(poll_interval)
                    try:
                        poll_resp = requests.get(
                            f"{judge0_url}/submissions/{token}?base64_encoded=false",
                            headers=headers,
                            timeout=timeout
                        )
                        if poll_resp.status_code == 200:
                            data = poll_resp.json()
                            status_obj = data.get('status') or {}
                            status_id = status_obj.get('id', 13) if isinstance(status_obj, dict) else (data.get('status_id') or 13)
                            status_desc = status_obj.get('description', 'Internal Error') if isinstance(status_obj, dict) else str(data.get('status_description') or 'Internal Error')
                        else:
                            break
                    except Exception as poll_err:
                        logger.warning(f"Judge0 token poll error for token {token}: {poll_err}")
                        break

            return self._normalize_judge0_response(data, request, status_id, status_desc, token)

        except requests.exceptions.RequestException as e:
            logger.error(f"Judge0 external sandbox connection error: {e}")
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
                stderr=f"FAIL_CLOSED: Sandbox unavailable ({e})",
                infrastructure_error=True,
                normalized_verdict=ExecutionStatus.SANDBOX_UNAVAILABLE.value,
            )
        except Exception as e:
            logger.error(f"Unexpected error interfacing with Judge0 sandbox: {e}", exc_info=True)
            return ExecutionResult(
                provider=self.name,
                language=request.language,
                status=ExecutionStatus.SYSTEM_ERROR.value,
                stderr=f"FAIL_CLOSED: Execution interface error ({e})",
                infrastructure_error=True,
                normalized_verdict=ExecutionStatus.SYSTEM_ERROR.value,
            )

    def _normalize_judge0_response(
        self,
        data: Dict[str, Any],
        request: ExecutionRequest,
        status_id: int,
        status_desc: str,
        token: Optional[str]
    ) -> ExecutionResult:
        raw_time = data.get('time')
        try:
            exec_time_sec = float(raw_time) if raw_time is not None else 0.0
        except (ValueError, TypeError):
            exec_time_sec = 0.0
        exec_time_ms = int(round(exec_time_sec * 1000))

        raw_mem = data.get('memory')
        try:
            mem_kb = int(raw_mem) if raw_mem is not None else 0
        except (ValueError, TypeError):
            mem_kb = 0

        stdout = data.get('stdout') or ""
        stderr = data.get('stderr') or ""
        compile_out = data.get('compile_output') or ""

        if status_id == 6:
            norm_status = ExecutionStatus.COMPILATION_ERROR.value
        elif status_id == 5:
            norm_status = ExecutionStatus.TIME_LIMIT.value
        elif status_id == 12:
            norm_status = ExecutionStatus.MEMORY_LIMIT.value
        elif status_id in (7, 8, 9, 10, 11):
            norm_status = ExecutionStatus.RUNTIME_ERROR.value
        elif status_id in (13, 14):
            # Judge0 Internal / Cgroups Failure
            norm_status = ExecutionStatus.JUDGE_INTERNAL_ERROR.value
        elif status_id in (3, 4):
            norm_status = ExecutionStatus.ACCEPTED.value
        else:
            norm_status = ExecutionStatus.SYSTEM_ERROR.value

        is_infra = norm_status in (
            ExecutionStatus.SANDBOX_UNAVAILABLE.value,
            ExecutionStatus.JUDGE_INTERNAL_ERROR.value,
            ExecutionStatus.SYSTEM_ERROR.value,
        )

        return ExecutionResult(
            provider=self.name,
            language=request.language,
            status=norm_status,
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_out or None,
            execution_time_ms=exec_time_ms,
            memory_kb=mem_kb,
            token=token,
            raw_provider_status=f"status_{status_id}_{status_desc}",
            infrastructure_error=is_infra,
            normalized_verdict=norm_status,
        )

    @classmethod
    def execute_in_sandbox(
        cls,
        source_code: str,
        language: str,
        stdin_data: str,
        expected_output: str,
        cpu_time_limit_ms: int = 2000,
        memory_limit_mb: int = 256,
        max_stdout_bytes: int = 65536
    ) -> Dict[str, Any]:
        """
        Legacy classmethod wrapper interfacing with Judge0 CE sandbox via HTTP API.
        """
        adapter = cls()
        req = ExecutionRequest(
            source_code=source_code,
            language=language,
            stdin=stdin_data,
            expected_output=expected_output,
            cpu_time_limit_ms=cpu_time_limit_ms,
            memory_limit_mb=memory_limit_mb,
            max_stdout_bytes=max_stdout_bytes,
        )
        res = adapter.execute(req)
        status_id = 3
        if res.status == ExecutionStatus.COMPILATION_ERROR.value:
            status_id = 6
        elif res.status == ExecutionStatus.TIME_LIMIT.value:
            status_id = 5
        elif res.status == ExecutionStatus.MEMORY_LIMIT.value:
            status_id = 12
        elif res.status == ExecutionStatus.RUNTIME_ERROR.value:
            status_id = 11
        elif res.status in (ExecutionStatus.SANDBOX_UNAVAILABLE.value, ExecutionStatus.JUDGE_INTERNAL_ERROR.value, ExecutionStatus.SYSTEM_ERROR.value):
            status_id = 13

        return {
            "status_id": status_id,
            "status_description": "Sandbox Unavailable" if res.status == ExecutionStatus.SANDBOX_UNAVAILABLE.value else res.status,
            "compile_output": res.compile_output,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "time": max(0.01, round(res.execution_time_ms / 1000.0, 3)),
            "memory": res.memory_kb
        }

    @classmethod
    def normalize_execution_result(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Backward-compatible 9-state normalizer.
        """
        raw_status = raw.get("status")
        status_id = raw.get("status_id")
        status_desc = str(raw.get("status_description") or "").strip()

        if isinstance(raw_status, dict):
            if status_id is None:
                status_id = raw_status.get("id")
            if not status_desc:
                status_desc = str(raw_status.get("description") or "").strip()

        stderr = raw.get("stderr") or ""
        compile_out = raw.get("compile_output") or ""
        stdout = raw.get("stdout") or ""

        normalized_states = {
            "QUEUED", "PROCESSING", "SUCCESS", "COMPILATION_ERROR",
            "RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED",
            "SYSTEM_ERROR", "SANDBOX_UNAVAILABLE"
        }

        if isinstance(raw_status, str) and raw_status in normalized_states:
            norm_status = raw_status
        elif status_desc == "Sandbox Unavailable" or "FAIL_CLOSED" in stderr or "Connection refused" in stderr:
            norm_status = "SANDBOX_UNAVAILABLE"
            if not stderr:
                stderr = "Coding Sandbox Unavailable"
        elif status_id in (1, 2) or status_desc in ("In Queue", "Processing"):
            norm_status = "PROCESSING" if status_id == 2 else "QUEUED"
        elif status_id == 3 or status_desc.upper() in ("ACCEPTED", "SUCCESS"):
            norm_status = "SUCCESS"
        elif status_id == 4:
            norm_status = "SUCCESS"
        elif status_id == 5 or "Time Limit Exceeded" in status_desc:
            norm_status = "TIME_LIMIT_EXCEEDED"
        elif status_id == 6 or "Compilation Error" in status_desc:
            norm_status = "COMPILATION_ERROR"
        elif status_id == 12 or "Memory Limit Exceeded" in status_desc:
            norm_status = "MEMORY_LIMIT_EXCEEDED"
        elif status_id in (7, 8, 9, 10, 11) or "Runtime Error" in status_desc:
            norm_status = "RUNTIME_ERROR"
        elif status_id in (13, 14) or "Internal Error" in status_desc:
            norm_status = "SYSTEM_ERROR"
        elif compile_out:
            norm_status = "COMPILATION_ERROR"
        elif stderr and "Error" in stderr:
            norm_status = "RUNTIME_ERROR"
        elif status_id is not None:
            norm_status = "SYSTEM_ERROR"
        elif status_desc:
            norm_status = "SYSTEM_ERROR"
        else:
            norm_status = "SUCCESS"

        raw_time = raw.get("time")
        try:
            exec_time_sec = float(raw_time) if raw_time is not None else 0.0
        except (ValueError, TypeError):
            exec_time_sec = 0.0

        exec_time_ms = raw.get("execution_time_ms")
        if exec_time_ms is None:
            exec_time_ms = int(round(exec_time_sec * 1000))

        raw_mem = raw.get("memory")
        try:
            mem_kb = int(raw_mem) if raw_mem is not None else 0
        except (ValueError, TypeError):
            mem_kb = 0
        if raw.get("memory_kb") is not None:
            mem_kb = int(raw["memory_kb"])

        return {
            "status": norm_status,
            "stdout": stdout,
            "stderr": stderr,
            "compile_output": compile_out,
            "execution_time_ms": exec_time_ms,
            "memory_kb": mem_kb,
            "status_id": status_id,
            "status_description": status_desc or ("Sandbox Unavailable" if norm_status == "SANDBOX_UNAVAILABLE" else norm_status),
            "time": raw_time,
            "memory": mem_kb,
            "passed": raw.get("passed"),
            "expected_output": raw.get("expected_output")
        }

    @classmethod
    def check_health(cls, timeout: float = 1.0) -> bool:
        """
        Fast infrastructure health probe verifying Judge0 reachability.
        """
        judge0_url = cls.get_judge0_url()
        api_key = getattr(settings, 'JUDGE0_API_KEY', '')
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-Auth-Token"] = api_key
            headers["X-RapidAPI-Key"] = api_key
        try:
            resp = requests.get(f"{judge0_url}/system_info", headers=headers, timeout=timeout)
            return resp.status_code == 200 and isinstance(resp.json(), dict)
        except Exception:
            return False

    @classmethod
    def check_health_detailed(cls, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Detailed health check probe distinguishing API reachability, worker health, and actual execution.
        """
        judge0_url = cls.get_judge0_url()
        api_key = getattr(settings, 'JUDGE0_API_KEY', '')
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-Auth-Token"] = api_key
            headers["X-RapidAPI-Key"] = api_key

        api_reachable = False
        worker_operational = False
        execution_operational = False
        info_data = {}

        try:
            resp = requests.get(f"{judge0_url}/system_info", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                api_reachable = True
                try:
                    info_data = resp.json()
                except Exception:
                    info_data = {}
        except Exception as e:
            logger.debug(f"Judge0 API unreachable: {e}")

        if api_reachable:
            try:
                w_resp = requests.get(f"{judge0_url}/workers", headers=headers, timeout=timeout)
                if w_resp.status_code == 200:
                    w_data = w_resp.json()
                    if isinstance(w_data, list) and len(w_data) > 0:
                        worker_operational = any(
                            isinstance(w, dict) and (w.get("available") is True or w.get("available", 0) > 0 or w.get("idle", 0) > 0 or w.get("working", 0) > 0)
                            for w in w_data
                        )
                    elif isinstance(w_data, dict):
                        worker_operational = bool(w_data.get("available") or w_data.get("workers"))
                elif isinstance(info_data.get('workers'), int) and info_data.get('workers', 0) > 0:
                    worker_operational = True
            except Exception as e:
                logger.debug(f"Judge0 worker probe failed: {e}")

        if api_reachable and worker_operational:
            try:
                t_resp = requests.post(
                    f"{judge0_url}/submissions?wait=true",
                    json={
                        "source_code": "print(1)",
                        "language_id": 71,
                        "cpu_time_limit": 2,
                    },
                    headers=headers,
                    timeout=timeout + 2.0
                )
                if t_resp.status_code in (200, 201):
                    t_data = t_resp.json()
                    if t_data.get("status", {}).get("id") == 3:
                        execution_operational = True
            except Exception as e:
                logger.debug(f"Judge0 execution probe failed: {e}")

        healthy = api_reachable and worker_operational and execution_operational
        return {
            "provider": "JUDGE0",
            "healthy": healthy,
            "api_reachable": api_reachable,
            "worker_operational": worker_operational,
            "worker_available": worker_operational,
            "execution_operational": execution_operational,
            "system_info": info_data
        }
