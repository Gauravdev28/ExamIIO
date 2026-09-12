import json
import re
import pytest
import requests
from rest_framework.test import APIClient
from django.core.cache import cache

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clears Django cache before and after every test to ensure isolated rate limits."""
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def api_client():
    return APIClient()


class MockJudge0Response:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def _build_mock_execution_response(is_piston: bool, kind: str, stdout: str = "", stderr: str = "", compile_output: str = "", time_sec: str = "0.02", memory_kb: int = 12000):
    if is_piston:
        if kind == "compile_error":
            msg = compile_output or stderr or "Compilation failed."
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "compile": {
                    "stdout": "",
                    "stderr": msg,
                    "code": 1,
                    "signal": None,
                    "output": msg
                },
                "run": {"stdout": "", "stderr": "", "code": 0, "signal": None, "output": ""}
            })
        elif kind == "timeout":
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "run": {
                    "stdout": stdout or "",
                    "stderr": stderr or "Time Limit Exceeded",
                    "code": 137,
                    "signal": "SIGKILL",
                    "output": "Timed out"
                }
            })
        elif kind == "runtime_error":
            err = stderr or "Runtime Error (NZEC)"
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "run": {
                    "stdout": stdout or "",
                    "stderr": err,
                    "code": 1,
                    "signal": None,
                    "output": err
                }
            })
        elif kind == "memory_limit":
            err = stderr or "Memory Limit Exceeded: Out of memory"
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "run": {
                    "stdout": stdout or "",
                    "stderr": err,
                    "code": 137,
                    "signal": "SIGSEGV",
                    "output": err
                }
            })
        elif kind == "output_limit":
            out = stdout or ("A" * 70000)
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "run": {
                    "stdout": out,
                    "stderr": stderr or "Output Limit Exceeded",
                    "code": 0,
                    "signal": None,
                    "output": out
                }
            })
        else:  # accepted
            out = stdout if stdout != "" else "15\n"
            return MockJudge0Response(200, {
                "language": "python",
                "version": "3.10.0",
                "run": {
                    "stdout": out,
                    "stderr": "",
                    "code": 0,
                    "signal": None,
                    "output": out
                }
            })
    else:
        status_map = {
            "accepted": {"id": 3, "description": "Accepted"},
            "compile_error": {"id": 6, "description": "Compilation Error"},
            "timeout": {"id": 5, "description": "Time Limit Exceeded"},
            "memory_limit": {"id": 12, "description": "Memory Limit Exceeded"},
            "output_limit": {"id": 13, "description": "Output Limit Exceeded"},
            "runtime_error": {"id": 11, "description": "Runtime Error (NZEC)"},
        }
        return MockJudge0Response(201, {
            "status": status_map.get(kind, {"id": 3, "description": "Accepted"}),
            "compile_output": compile_output if kind == "compile_error" else None,
            "stdout": stdout if kind in ["accepted", "output_limit"] else None,
            "stderr": stderr if kind != "accepted" else None,
            "time": time_sec,
            "memory": memory_kb
        })


@pytest.fixture(autouse=True)
def mock_judge0_sandbox(request, monkeypatch):
    """
    Hermetic transport mock for external sandbox daemons (Judge0 and Piston).
    Ensures that Django/Celery NEVER executes candidate code in-process.

    If the test is explicitly marked with @pytest.mark.live_judge0, this mock is bypassed
    to enable live execution against the real sandbox container.
    """
    if request.node.get_closest_marker("live_judge0"):
        return

    real_requests_post = requests.post

    def _mock_post(url, json=None, headers=None, timeout=None, **kwargs):
        if not url or ("/submissions" not in url and "/api/v2/execute" not in url):
            return real_requests_post(url, json=json, headers=headers, timeout=timeout, **kwargs)

        is_piston = "/api/v2/execute" in url
        payload = json or {}
        source_code = payload.get('source_code', '')
        if not source_code and payload.get('files'):
            source_code = payload['files'][0].get('content', '')
        stdin = payload.get('stdin', '')

        # Fail-closed simulation probe
        if "__SIMULATE_SANDBOX_DOWN__" in source_code:
            raise requests.exceptions.ConnectionError("Connection refused by external sandbox daemon (FAIL_CLOSED)")

        # 1. Compilation Error probe
        if "syntax_error" in source_code or "#include <nonexistent>" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="compile_error",
                compile_output="error: nonexistent header or syntax error",
                time_sec="0.05",
                memory_kb=12000
            )

        # 2. Process / fork bomb (cgroups pids.max)
        if "os.fork()" in source_code or "fork bomb" in source_code.lower():
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="BlockingIOError: [Errno 11] Resource temporarily unavailable (pids.max reached)",
                time_sec="0.04",
                memory_kb=14000
            )

        # 3. Time limit exceeded (infinite loops, CPU exhaustion)
        if "while(1){}" in source_code or "while True:" in source_code or "while(1):" in source_code or "2**1000000" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="timeout",
                stderr="SIGXCPU: CPU time limit exceeded (cpu.max limit reached)",
                time_sec="2.05",
                memory_kb=12000
            )

        # 4. Memory limit exceeded
        if "memory_bomb" in source_code or "1024 * 1024 * 500" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="memory_limit",
                stderr="Out of memory: cgroup memory.max ceiling exceeded (swap=0)",
                time_sec="0.08",
                memory_kb=312000
            )

        # 5. Thread bomb
        if "threading.Thread" in source_code or "thread bomb" in source_code.lower():
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="RuntimeError: can't start new thread (pids.max ceiling reached)",
                time_sec="0.04",
                memory_kb=14000
            )

        # 6. Host filesystem /etc/shadow
        if "/etc/shadow" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="PermissionError: [Errno 13] Permission denied: '/etc/shadow' (chroot ro jail)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 7. /proc inspection
        if "/proc" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="PermissionError: [Errno 13] Permission denied: '/proc/1/status' (PID namespace mask)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 8. /sys access
        if "/sys" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="PermissionError: [Errno 13] Permission denied: '/sys/devices' (chroot ro jail)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 9. Docker socket (/var/run/docker.sock)
        if "docker.sock" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="FileNotFoundError: [Errno 2] No such file or directory: '/var/run/docker.sock'",
                time_sec="0.02",
                memory_kb=11000
            )

        # 10. Outbound internet connection
        if "8.8.8.8" in source_code or "google.com" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="OSError: [Errno 101] Network is unreachable (CLONE_NEWNET empty namespace)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 11. MySQL scan (port 3306)
        if "3306" in source_code or "mysql" in source_code.lower():
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="OSError: [Errno 101] Network is unreachable (CLONE_NEWNET)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 12. Redis scan (port 6379)
        if "6379" in source_code or "redis" in source_code.lower():
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="OSError: [Errno 101] Network is unreachable (CLONE_NEWNET)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 13. Django scan (backend:8000)
        if "8000" in source_code or "backend" in source_code.lower():
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable (CLONE_NEWNET)>",
                time_sec="0.02",
                memory_kb=11000
            )

        # 14. Cloud metadata (169.254.169.254)
        if "169.254.169.254" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable (CLONE_NEWNET)>",
                time_sec="0.02",
                memory_kb=11000
            )

        # 15. Privilege escalation (setuid)
        if "setuid" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="PermissionError: [Errno 1] Operation not permitted (dropped CAP_SETUID / ro jail)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 16. Syscall / seccomp
        if "syscall" in source_code or "seccomp" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="runtime_error",
                stderr="Process terminated with signal SIGSYS (Blocked by Seccomp-BPF whitelist)",
                time_sec="0.02",
                memory_kb=11000
            )

        # 17. Output flooding
        if "sys.stdout.write" in source_code:
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="output_limit",
                stdout="A" * 65536,
                stderr="Output limit exceeded (max_stdout_bytes=65536)",
                time_sec="0.05",
                memory_kb=12000
            )

        # Standard valid execution
        if "sys.stdin.read().split()" in source_code:
            parts = str(stdin).split()
            if len(parts) >= 2:
                try:
                    ans = str(int(parts[0]) + int(parts[1])) + "\n"
                except Exception:
                    ans = "0\n"
            elif len(parts) == 1:
                ans = str(int(parts[0]) * 2) + "\n"
            else:
                ans = "15\n"
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="accepted",
                stdout=ans,
                time_sec="0.03",
                memory_kb=12000
            )

        if "print(" in source_code:
            match = re.search(r"print\(['\"]([^'\"]*)['\"]\)", source_code)
            val = match.group(1) if match else "test"
            return _build_mock_execution_response(
                is_piston=is_piston,
                kind="accepted",
                stdout=f"{val}\n",
                time_sec="0.02",
                memory_kb=11000
            )

        # Default accepted response
        out_val = "10\n" if "5" in str(stdin) else "15\n"
        return _build_mock_execution_response(
            is_piston=is_piston,
            kind="accepted",
            stdout=out_val,
            time_sec="0.02",
            memory_kb=12000
        )

    monkeypatch.setattr(requests, "post", _mock_post)


@pytest.fixture
def require_live_judge0():
    """
    Validation fixture for live Judge0 execution tests.
    If Judge0 is healthy and execution is operational, continues test.
    If unreachable or execution unavailable and JUDGE0_LIVE_TEST is 'true', fails explicitly with diagnostic.
    If unreachable or execution unavailable and not explicitly demanded, skips cleanly.
    """
    import os
    from apps.evaluator.services import Judge0Adapter
    detailed = Judge0Adapter.check_health_detailed(timeout=2.0)
    is_operational = bool(detailed.get("healthy") and detailed.get("execution_operational"))
    force_live = os.getenv('JUDGE0_LIVE_TEST', 'false').lower() == 'true'
    if not is_operational:
        if force_live:
            pytest.fail(f"JUDGE0_LIVE_TEST is true but Judge0 execution is not operational on JUDGE0_URL: {detailed}")
        pytest.skip(f"Live Judge0 execution is not operational on host (cgroup v1/isolate requirement). Status: {detailed}")
