import asyncio
from pathlib import Path

import httpx
import psutil
import pytest
import respx

from agentic_uptime.config import (
    DatabaseCheckConfig,
    DatadogCheckConfig,
    GrafanaCheckConfig,
    HTTPCheckConfig,
    LogCheckConfig,
    ProcessCheckConfig,
    PrometheusCheckConfig,
    ScriptCheckConfig,
    SSHCheckConfig,
    SystemdCheckConfig,
    TCPCheckConfig,
)
from agentic_uptime.monitoring.database_check import DatabaseCheck
from agentic_uptime.monitoring.datadog_check import DatadogCheck
from agentic_uptime.monitoring.grafana_check import GrafanaCheck
from agentic_uptime.monitoring.http_check import HTTPCheck
from agentic_uptime.monitoring.log_check import LogCheck
from agentic_uptime.monitoring.process_check import ProcessCheck
from agentic_uptime.monitoring.prometheus_check import PrometheusCheck
from agentic_uptime.monitoring.script_check import ScriptCheck
from agentic_uptime.monitoring.ssh_check import SSHCheck
from agentic_uptime.monitoring.systemd_check import SystemdCheck
from agentic_uptime.monitoring.tcp_check import TCPCheck
from agentic_uptime.utils.subprocess_runner import CommandResult


@pytest.mark.asyncio
@respx.mock
async def test_http_check_ok() -> None:
    respx.get("https://example.com/health").mock(
        return_value=httpx.Response(200)
    )
    config = HTTPCheckConfig(
        name="http",
        type="http",
        url="https://example.com/health",
        expected_status=[200],
    )
    result = await HTTPCheck("http", config).check()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_tcp_check_ok() -> None:
    async def handler(reader, writer):
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    config = TCPCheckConfig(
        name="tcp",
        type="tcp",
        host="127.0.0.1",
        port=port,
        timeout_sec=2,
    )
    result = await TCPCheck("tcp", config).check()
    server.close()
    await server.wait_closed()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_process_check_ok() -> None:
    process_name = psutil.Process().name()
    config = ProcessCheckConfig(
        name="proc",
        type="process",
        process_name=process_name,
        min_count=1,
    )
    result = await ProcessCheck("proc", config).check()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_systemd_check_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args, **_kwargs):
        return CommandResult(command="systemctl", exit_code=0, stdout="active", stderr="")

    monkeypatch.setattr(
        "agentic_uptime.monitoring.systemd_check.run_command", fake_run
    )
    config = SystemdCheckConfig(
        name="systemd",
        type="systemd",
        service_name="nginx",
    )
    result = await SystemdCheck("systemd", config).check()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_script_check_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args, **_kwargs):
        return CommandResult(command="script", exit_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("agentic_uptime.monitoring.script_check.run_command", fake_run)
    config = ScriptCheckConfig(
        name="script",
        type="script",
        command="echo ok",
    )
    result = await ScriptCheck("script", config).check()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_log_check_detects_pattern(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("ok\nerror: failure\n", encoding="utf-8")
    config = LogCheckConfig(
        name="log",
        type="log",
        file_path=log_file,
        regex="error",
        min_hits=1,
        window_sec=60,
    )
    result = await LogCheck("log", config).check()
    assert result.status == "warn"


@pytest.mark.asyncio
async def test_database_check_sqlite() -> None:
    config = DatabaseCheckConfig(
        name="db",
        type="database",
        dsn="sqlite+pysqlite:///:memory:",
        query="SELECT 1",
        comparator="==",
        expected=1,
    )
    result = await DatabaseCheck("db", config).check()
    assert result.status == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_prometheus_check_warn() -> None:
    respx.get("http://localhost:9090/api/v1/query").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "data": {"result": [{"value": [0, "2"]}]}},
        )
    )
    config = PrometheusCheckConfig(
        name="prom",
        type="prometheus",
        base_url="http://localhost:9090",
        query="up",
        comparator=">",
        threshold=1,
    )
    result = await PrometheusCheck("prom", config).check()
    assert result.status == "warn"


@pytest.mark.asyncio
@respx.mock
async def test_grafana_check_alerts() -> None:
    respx.get("http://localhost:3000/api/health").mock(
        return_value=httpx.Response(200, json={"database": "ok"})
    )
    respx.get("http://localhost:3000/api/alerts").mock(
        return_value=httpx.Response(
            200,
            json=[{"state": "alerting", "name": "CPU high"}],
        )
    )
    config = GrafanaCheckConfig(
        name="graf",
        type="grafana",
        base_url="http://localhost:3000",
    )
    result = await GrafanaCheck("graf", config).check()
    assert result.status == "warn"


@pytest.mark.asyncio
@respx.mock
async def test_datadog_check_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATADOG_API_KEY", "x")
    monkeypatch.setenv("DATADOG_APP_KEY", "y")
    respx.get("https://api.datadoghq.com/api/v1/monitor/123").mock(
        return_value=httpx.Response(200, json={"overall_state": "Alert"})
    )
    config = DatadogCheckConfig(
        name="dd",
        type="datadog",
        monitor_id=123,
        base_url="https://api.datadoghq.com",
    )
    result = await DatadogCheck("dd", config).check()
    assert result.status == "warn"


@pytest.mark.asyncio
async def test_ssh_check_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSH_PASSWORD", "secret")

    def fake_run(*_args, **_kwargs):
        return CommandResult(command="ssh", exit_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("agentic_uptime.monitoring.ssh_check.run_command", fake_run)
    config = SSHCheckConfig(
        name="ssh",
        type="ssh",
        host="127.0.0.1",
        user="root",
        command="echo ok",
    )
    result = await SSHCheck("ssh", config).check()
    assert result.status == "ok"
