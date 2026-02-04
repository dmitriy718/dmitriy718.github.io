import subprocess
from pathlib import Path

import pytest

from agentic_uptime.agent import Agent, build_rbac
from agentic_uptime.audit import AuditLogger
from agentic_uptime.config import (
    AgentConfig,
    HTTPCheckConfig,
    ServiceConfig,
    FailurePolicy,
)
from agentic_uptime.memory import MemoryStore
from agentic_uptime.monitoring.base import CheckResult
from agentic_uptime.notifications.base import NotificationManager, Notifier
from agentic_uptime.repair.auto_heal import AutoHealer, IncidentContext
from agentic_uptime.repair.patcher import PatchApplier
from agentic_uptime.rbac import RBAC, Role
from agentic_uptime.analysis.log_analyzer import LogAnalyzer


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=path, check=True)


def test_patch_applier(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    file_path = repo / "app.txt"
    file_path.write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    diff_text = """diff --git a/app.txt b/app.txt
--- a/app.txt
+++ b/app.txt
@@ -1 +1 @@
-hello
+hello world
"""
    rbac = RBAC(
        roles=[Role(name="admin", allow={"apply_patch"})],
        agent_name="agent",
        agent_role="admin",
    )
    patcher = PatchApplier(rbac, AuditLogger(tmp_path / "audit.jsonl"))
    patcher.apply_patch(repo, diff_text)
    assert file_path.read_text(encoding="utf-8").strip() == "hello world"


def test_patch_applier_rejects_absolute_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    rbac = RBAC(
        roles=[Role(name="admin", allow={"apply_patch"})],
        agent_name="agent",
        agent_role="admin",
    )
    patcher = PatchApplier(rbac, AuditLogger(tmp_path / "audit.jsonl"))
    diff_text = """diff --git a/app.txt b/app.txt
--- /etc/passwd
+++ /etc/passwd
@@ -1 +1 @@
-a
+b
"""
    with pytest.raises(ValueError):
        patcher.apply_patch(repo, diff_text)


def test_auto_healer_runbook(tmp_path: Path) -> None:
    rbac = RBAC(
        roles=[Role(name="admin", allow={"run_command"})],
        agent_name="agent",
        agent_role="admin",
    )
    audit = AuditLogger(tmp_path / "audit.jsonl")
    memory = MemoryStore(tmp_path / "memory.sqlite")

    class DummyDiagnostics:
        def collect(self, **_kwargs):
            return {"log": "error"}

    class DummyDeployment:
        def __init__(self):
            self.calls = []

        def execute_step(self, action, args):
            self.calls.append((action, args))
            return "ok"

    class DummyPatcher:
        def apply_patch(self, *_args, **_kwargs):
            return "patched"

    service = ServiceConfig(
        name="api",
        runbook=[{"action": "run_script", "args": {"command": "echo ok"}}],
    )
    healer = AutoHealer(
        rbac=rbac,
        audit=audit,
        memory=memory,
        diagnostics=DummyDiagnostics(),
        analyzer=LogAnalyzer(),
        deployment=DummyDeployment(),
        patcher=DummyPatcher(),
        llm=None,
    )
    incident = IncidentContext(incident_id=1, check_name="http", status="critical", message="down")
    report = healer.handle_incident(incident, service)
    assert report["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_incident_and_recovery(tmp_path: Path) -> None:
    class DummyNotifier(Notifier):
        def __init__(self):
            self.messages = []

        def send(self, title, message, level="info"):
            self.messages.append((title, level))

    class DummyHealer:
        def __init__(self):
            self.calls = 0

        def handle_incident(self, *_args, **_kwargs):
            self.calls += 1
            return {"status": "ok"}

    config = AgentConfig(
        checks=[
            HTTPCheckConfig(
                name="http",
                type="http",
                url="https://example.com",
                failure_policy=FailurePolicy(fail_after=1, recover_after=1),
            )
        ],
        services=[ServiceConfig(name="svc")],
        rbac_roles=[{"name": "admin", "allow": ["notify"]}],
    )
    audit = AuditLogger(tmp_path / "audit.jsonl")
    memory = MemoryStore(tmp_path / "memory.sqlite")
    rbac = build_rbac(config)
    dummy_notifier = DummyNotifier()
    agent = Agent(
        config=config,
        audit=audit,
        memory=memory,
        rbac=rbac,
        notifier=NotificationManager([dummy_notifier]),
        auto_healer=DummyHealer(),
    )
    result = CheckResult(name="http", status="critical", message="down")
    await agent._handle_result(config.checks[0], result)
    incidents = memory.recent_incidents()
    assert incidents
    ok_result = CheckResult(name="http", status="ok", message="up")
    await agent._handle_result(config.checks[0], ok_result)
    incidents = memory.recent_incidents()
    assert incidents[0].resolved_at is not None
