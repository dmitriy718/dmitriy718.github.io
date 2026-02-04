import hmac
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from agentic_uptime.analysis.diagnostics import DiagnosticsCollector
from agentic_uptime.audit import AuditLogger
from agentic_uptime.rbac import RBAC, Role
from agentic_uptime.webhooks.server import create_app
from agentic_uptime.utils.subprocess_runner import CommandResult


class DummyQueue:
    def __init__(self):
        self.items = []

    async def put(self, item):
        self.items.append(item)


def test_webhook_secret_header() -> None:
    queue = DummyQueue()
    app = create_app(queue, shared_secret="secret")
    client = TestClient(app)
    response = client.post(
        "/webhook",
        headers={"X-Webhook-Secret": "secret"},
        json={"event": "deploy"},
    )
    assert response.status_code == 200


def test_webhook_signature_verification() -> None:
    queue = DummyQueue()
    app = create_app(queue, shared_secret="secret")
    client = TestClient(app)
    body = b'{"event":"deploy"}'
    digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"
    response = client.post(
        "/webhook",
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        data=body,
    )
    assert response.status_code == 200


def test_diagnostics_collector(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audit = AuditLogger(tmp_path / "audit.jsonl")
    rbac = RBAC(
        roles=[Role(name="admin", allow={"run_command"})],
        agent_name="agent",
        agent_role="admin",
    )

    def fake_run(*_args, **_kwargs):
        return CommandResult(command="cmd", exit_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("agentic_uptime.analysis.diagnostics.run_command", fake_run)
    log_path = tmp_path / "app.log"
    log_path.write_text("line1\nline2\n", encoding="utf-8")
    collector = DiagnosticsCollector(rbac, audit)
    context = collector.collect(log_paths=[log_path], systemd_service="nginx")
    assert any(key.startswith("log:") for key in context.keys())
    assert "systemd_status" in context
