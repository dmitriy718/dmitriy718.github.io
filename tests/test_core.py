import json
from pathlib import Path

import pytest

from agentic_uptime.audit import AuditLogger
from agentic_uptime.config import AgentConfig, load_config
from agentic_uptime.logging_setup import setup_logging
from agentic_uptime.memory import MemoryStore
from agentic_uptime.rbac import RBAC, Role
from agentic_uptime.utils.env import get_env
from agentic_uptime.utils.file_tail import TailState, read_new_lines
from agentic_uptime.utils.retry import retry
from agentic_uptime.utils.subprocess_runner import run_command


def test_load_config_resolves_paths(tmp_path: Path) -> None:
    config_text = """
paths:
  data_dir: data
  logs_dir: logs
  audit_log: logs/audit.jsonl
  memory_db: data/memory.sqlite
checks: []
services:
  - name: api
    repo_path: repo
    log_paths:
      - logs/app.log
rbac_roles: []
"""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_text, encoding="utf-8")
    config = load_config(config_file)
    assert config.paths.data_dir == tmp_path / "data"
    assert config.paths.logs_dir == tmp_path / "logs"
    assert config.paths.audit_log == tmp_path / "logs" / "audit.jsonl"
    assert config.paths.memory_db == tmp_path / "data" / "memory.sqlite"
    assert config.services[0].repo_path == tmp_path / "repo"
    assert config.services[0].log_paths[0] == tmp_path / "logs" / "app.log"


def test_rbac_authorization() -> None:
    rbac = RBAC(
        roles=[Role(name="admin", allow={"restart_service"})],
        agent_name="agent",
        agent_role="admin",
    )
    assert rbac.authorize("restart_service") is True
    assert rbac.authorize("deploy") is False
    with pytest.raises(PermissionError):
        rbac.require("deploy")


def test_audit_logger_writes(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger(audit_path)
    audit.log("agent", "restart", "ok", {"service": "api"})
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["actor"] == "agent"
    assert payload["action"] == "restart"


def test_memory_store_flow(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite")
    incident_id = store.record_incident("api", "http", "critical", "down")
    store.record_action(incident_id, "restart_systemd", "ok", "done")
    store.resolve_incident(incident_id)
    incidents = store.recent_incidents()
    assert incidents
    assert incidents[0].id == incident_id
    assert incidents[0].resolved_at is not None


def test_retry_utility() -> None:
    state = {"count": 0}

    def flaky() -> str:
        state["count"] += 1
        if state["count"] < 2:
            raise ValueError("fail")
        return "ok"

    result = retry(flaky, retries=2, delay_sec=0.01)
    assert result == "ok"


def test_file_tail_reads_new_lines(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("line1\n", encoding="utf-8")
    state = TailState()
    first = read_new_lines(log_file, state)
    assert first == ["line1"]
    log_file.write_text("line1\nline2\n", encoding="utf-8")
    second = read_new_lines(log_file, state)
    assert second == ["line2"]


def test_get_env_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(RuntimeError):
        get_env("MISSING_ENV", required=True)


def test_subprocess_env_merge() -> None:
    result = run_command(
        ["python3", "-c", "import os; print(os.getenv('FOO', ''))"],
        env={"FOO": "bar"},
    )
    assert result.exit_code == 0
    assert result.stdout == "bar"


def test_setup_logging_creates_log(tmp_path: Path) -> None:
    setup_logging(tmp_path)
    logger = __import__("logging").getLogger("test")
    logger.info("hello")
    log_file = tmp_path / "agent.log"
    assert log_file.exists()
