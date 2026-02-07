import json

import pytest

from agentic_uptime.analysis.llm_client import LLMClient
from agentic_uptime.config import LLMConfig
from agentic_uptime.integrations.github import GitHubClient
from agentic_uptime.integrations.gitlab import GitLabClient
from agentic_uptime.notifications.email import EmailNotifier
from agentic_uptime.notifications.slack import SlackNotifier
from agentic_uptime.notifications.telegram import TelegramNotifier


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)

    def json(self):
        return self._payload


def test_github_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert "Authorization" in headers
        assert "workflows" in url
        return DummyResponse(status_code=204)

    monkeypatch.setattr("requests.post", fake_post)
    client = GitHubClient()
    response = client.dispatch_workflow("org/repo", "deploy.yml", "main", {"env": "prod"})
    assert response == "Workflow dispatched"


def test_gitlab_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "token")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert headers["PRIVATE-TOKEN"] == "token"
        return DummyResponse(status_code=201)

    monkeypatch.setattr("requests.post", fake_post)
    client = GitLabClient()
    response = client.trigger_pipeline("123", "main", {"ENV": "prod"})
    assert response == "Pipeline triggered"


def test_slack_notifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test")

    def fake_post(url, data=None, timeout=None):
        assert url == "https://hooks.slack.test"
        payload = json.loads(data)
        assert "text" in payload
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)
    notifier = SlackNotifier("SLACK_WEBHOOK_URL")
    notifier.send("Alert", "Something happened", level="warn")


def test_telegram_notifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")

    def fake_post(url, json=None, timeout=None):
        assert "sendMessage" in url
        assert json["chat_id"] == "123"
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)
    notifier = TelegramNotifier("TELEGRAM_BOT_TOKEN", "123")
    notifier.send("Alert", "Ping", level="info")


def test_email_notifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    sent = {}

    class DummySMTP:
        def __init__(self, host, port):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, email):
            sent["subject"] = email["Subject"]

    monkeypatch.setattr("smtplib.SMTP", DummySMTP)
    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        username_env="SMTP_USER",
        password_env="SMTP_PASSWORD",
        from_addr="agent@example.com",
        to_addrs=["oncall@example.com"],
    )
    notifier.send("Alert", "Message", level="critical")
    assert sent["host"] == "smtp.example.com"


def test_llm_client_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")

    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResponse(
            payload={"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr("requests.post", fake_post)
    llm = LLMClient(LLMConfig(enabled=True, provider="openai"))
    response = llm.chat([{"role": "user", "content": "hi"}])
    assert response == "ok"
