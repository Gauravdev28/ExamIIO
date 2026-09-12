"""
Comprehensive Unit and Integration Tests for Provider-Neutral Code Execution Engine.
Tests: ExecutionProviderFactory, CodeExecutionService, PistonAdapter, Judge0Adapter, Fail-Closed Security.
"""
import pytest
import requests
from unittest.mock import patch, MagicMock

from apps.evaluator.execution import (
    CodeExecutionService,
    ExecutionProviderFactory,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    CanonicalLanguage,
    PistonAdapter,
    Judge0Adapter,
    LanguageConfigurationError,
    SandboxUnavailableError,
)


class TestCanonicalLanguageAndContract:
    def test_canonical_language_normalization(self):
        assert CanonicalLanguage.normalize('python') == 'PYTHON'
        assert CanonicalLanguage.normalize('python3') == 'PYTHON'
        assert CanonicalLanguage.normalize('PY') == 'PYTHON'
        assert CanonicalLanguage.normalize('c++') == 'CPP'
        assert CanonicalLanguage.normalize('cpp') == 'CPP'
        assert CanonicalLanguage.normalize('g++') == 'CPP'
        assert CanonicalLanguage.normalize('java') == 'JAVA'
        assert CanonicalLanguage.normalize('openjdk') == 'JAVA'

    def test_execution_request_limit_clamping(self):
        req = ExecutionRequest(
            source_code="print(1)",
            language="PYTHON",
            cpu_time_limit_ms=50,  # Below min 100
            memory_limit_mb=5000,  # Above max 1024
            max_stdout_bytes=500,  # Below min 1024
        )
        assert req.cpu_time_limit_ms == 100
        assert req.memory_limit_mb == 1024
        assert req.max_stdout_bytes == 1024


class TestExecutionProviderFactory:
    def test_factory_resolves_piston(self):
        adapter = ExecutionProviderFactory.get_provider('PISTON')
        assert isinstance(adapter, PistonAdapter)
        assert adapter.name == 'PISTON'

    def test_factory_resolves_judge0(self):
        adapter = ExecutionProviderFactory.get_provider('JUDGE0')
        assert isinstance(adapter, Judge0Adapter)
        assert adapter.name == 'JUDGE0'

    def test_factory_fallback_on_unknown(self):
        adapter = ExecutionProviderFactory.get_provider('UNKNOWN_PROVIDER')
        assert isinstance(adapter, PistonAdapter)


class TestPistonAdapterMocked:
    @pytest.fixture
    def adapter(self):
        return PistonAdapter()

    def test_piston_success_execution(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "language": "python",
                    "version": "3.10.0",
                    "run": {
                        "stdout": "42\n",
                        "stderr": "",
                        "code": 0,
                        "signal": None,
                        "output": "42\n"
                    }
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="print(42)", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout == "42\n"
        assert res.exit_code == 0
        assert res.infrastructure_error is False

    def test_piston_compilation_error(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "language": "gcc",
                    "version": "10.2.0",
                    "compile": {
                        "stdout": "",
                        "stderr": "error: expected ';' before '}' token",
                        "code": 1,
                        "signal": None,
                        "output": "error: expected ';' before '}' token"
                    }
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="int main() { return 0 }", language="CPP")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.COMPILATION_ERROR.value
        assert "expected ';'" in res.compile_output
        assert res.infrastructure_error is False

    def test_piston_timeout(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "language": "python",
                    "version": "3.10.0",
                    "run": {
                        "stdout": "",
                        "stderr": "Timed out",
                        "code": 137,
                        "signal": "SIGKILL",
                        "output": "Timed out"
                    }
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="while True: pass", language="PYTHON", cpu_time_limit_ms=2000)
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.TIME_LIMIT.value
        assert res.infrastructure_error is False

    def test_piston_runtime_error(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "language": "python",
                    "version": "3.10.0",
                    "run": {
                        "stdout": "",
                        "stderr": "ZeroDivisionError: division by zero",
                        "code": 1,
                        "signal": None,
                        "output": "ZeroDivisionError: division by zero"
                    }
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="print(1/0)", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.RUNTIME_ERROR.value
        assert "ZeroDivisionError" in res.stderr
        assert res.infrastructure_error is False

    def test_piston_sandbox_unavailable_fails_closed(self, adapter, monkeypatch):
        def _mock_conn_err(url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "post", _mock_conn_err)
        req = ExecutionRequest(source_code="print(1)", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.SANDBOX_UNAVAILABLE.value
        assert res.infrastructure_error is True
        assert "FAIL_CLOSED" in res.stderr

    def test_piston_health_check_detailed(self, adapter, monkeypatch):
        def _mock_get(url, **kwargs):
            class MockResp:
                status_code = 200
                def json(self):
                    return [
                        {"language": "python", "version": "3.10.0"},
                        {"language": "gcc", "version": "10.2.0"},
                        {"language": "java", "version": "15.0.2"}
                    ]
            return MockResp()

        def _mock_post(url, **kwargs):
            class MockResp:
                status_code = 200
                def json(self):
                    return {
                        "run": {"stdout": "CODEGUARD_HEALTH\n", "code": 0}
                    }
            return MockResp()

        monkeypatch.setattr(requests, "get", _mock_get)
        monkeypatch.setattr(requests, "post", _mock_post)

        detailed = adapter.check_health_detailed(timeout=1.0)
        assert detailed["healthy"] is True
        assert detailed["api_reachable"] is True
        assert detailed["worker_operational"] is True
        assert detailed["execution_operational"] is True
        assert detailed["runtimes_count"] == 3


class TestJudge0AdapterMocked:
    @pytest.fixture
    def adapter(self):
        return Judge0Adapter()

    def test_judge0_success_execution(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 201
            def json(self):
                return {
                    "status": {"id": 3, "description": "Accepted"},
                    "stdout": "Hello World\n",
                    "time": "0.05",
                    "memory": 1200
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="print('Hello World')", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.ACCEPTED.value
        assert res.stdout == "Hello World\n"
        assert res.execution_time_ms == 50
        assert res.memory_kb == 1200
        assert res.infrastructure_error is False

    def test_judge0_internal_error_classified_as_infra(self, adapter, monkeypatch):
        class MockResponse:
            status_code = 201
            def json(self):
                return {
                    "status": {"id": 13, "description": "Internal Error"},
                    "stderr": "isolate: write /sys/fs/cgroup/memory: No such file or directory"
                }

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockResponse())
        req = ExecutionRequest(source_code="print(1)", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.JUDGE_INTERNAL_ERROR.value
        assert res.infrastructure_error is True

    def test_judge0_sandbox_offline_fails_closed(self, adapter, monkeypatch):
        def _mock_conn_err(url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "post", _mock_conn_err)
        req = ExecutionRequest(source_code="print(1)", language="PYTHON")
        res = adapter.execute(req)

        assert res.status == ExecutionStatus.SANDBOX_UNAVAILABLE.value
        assert res.infrastructure_error is True
        assert "FAIL_CLOSED" in res.stderr
