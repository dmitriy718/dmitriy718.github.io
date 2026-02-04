from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union, Annotated

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    logs_dir: Path = Path("logs")
    audit_log: Path = Path("logs/audit.jsonl")
    memory_db: Path = Path("data/memory.sqlite")


class RBACRole(BaseModel):
    name: str
    allow: List[str] = Field(default_factory=list)


class AgentIdentity(BaseModel):
    name: str = "agent"
    role: str = "admin"


class FailurePolicy(BaseModel):
    fail_after: int = 2
    recover_after: int = 1


class BaseCheckConfig(BaseModel):
    name: str
    type: str
    interval_sec: int = 30
    timeout_sec: int = 10
    service: Optional[str] = None
    enabled: bool = True
    failure_policy: FailurePolicy = Field(default_factory=FailurePolicy)
    notify_on_warn: bool = True
    notify_on_recover: bool = True


class HTTPCheckConfig(BaseCheckConfig):
    type: Literal["http"]
    url: HttpUrl
    method: Literal["GET", "POST", "HEAD", "PUT", "DELETE", "PATCH"] = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    expected_status: List[int] = Field(default_factory=lambda: [200])
    max_latency_ms: Optional[int] = None
    verify_tls: bool = True
    follow_redirects: bool = True


class TCPCheckConfig(BaseCheckConfig):
    type: Literal["tcp"]
    host: str
    port: int


class ProcessCheckConfig(BaseCheckConfig):
    type: Literal["process"]
    process_name: str
    min_count: int = 1
    max_cpu_percent: Optional[float] = None
    max_memory_mb: Optional[int] = None


class SystemdCheckConfig(BaseCheckConfig):
    type: Literal["systemd"]
    service_name: str


class PrometheusCheckConfig(BaseCheckConfig):
    type: Literal["prometheus"]
    base_url: HttpUrl
    query: str
    comparator: Literal[">", ">=", "<", "<=", "=="] = ">"
    threshold: float


class GrafanaCheckConfig(BaseCheckConfig):
    type: Literal["grafana"]
    base_url: HttpUrl
    api_key_env: str = "GRAFANA_API_KEY"
    alert_states: List[str] = Field(default_factory=lambda: ["alerting"])


class DatadogCheckConfig(BaseCheckConfig):
    type: Literal["datadog"]
    base_url: HttpUrl = "https://api.datadoghq.com"
    api_key_env: str = "DATADOG_API_KEY"
    app_key_env: str = "DATADOG_APP_KEY"
    monitor_id: Optional[int] = None
    query: Optional[str] = None


class LogCheckConfig(BaseCheckConfig):
    type: Literal["log"]
    file_path: Path
    regex: str
    min_hits: int = 1
    window_sec: int = 60


class ScriptCheckConfig(BaseCheckConfig):
    type: Literal["script"]
    command: str
    shell: bool = True
    expected_exit_code: int = 0


class DatabaseCheckConfig(BaseCheckConfig):
    type: Literal["database"]
    dsn: str
    query: str = "SELECT 1"
    comparator: Literal[">", ">=", "<", "<=", "==", "!="] = "=="
    expected: Any = 1


class SSHCheckConfig(BaseCheckConfig):
    type: Literal["ssh"]
    host: str
    user: str
    port: int = 22
    command: str
    password_env: str = "SSH_PASSWORD"


CheckConfig = Annotated[
    Union[
        HTTPCheckConfig,
        TCPCheckConfig,
        ProcessCheckConfig,
        SystemdCheckConfig,
        PrometheusCheckConfig,
        GrafanaCheckConfig,
        DatadogCheckConfig,
        LogCheckConfig,
        ScriptCheckConfig,
        DatabaseCheckConfig,
        SSHCheckConfig,
    ],
    Field(discriminator="type"),
]


class RunbookStepConfig(BaseModel):
    action: Literal[
        "restart_systemd",
        "restart_docker",
        "restart_k8s",
        "ssh_command",
        "run_script",
        "deploy_github",
        "deploy_gitlab",
        "apply_patch",
    ]
    args: Dict[str, Any] = Field(default_factory=dict)


class ServiceConfig(BaseModel):
    name: str
    repo_path: Optional[Path] = None
    log_paths: List[Path] = Field(default_factory=list)
    systemd_service: Optional[str] = None
    docker_container: Optional[str] = None
    k8s_deployment: Optional[str] = None
    k8s_namespace: str = "default"
    tests_command: Optional[str] = None
    runbook: List[RunbookStepConfig] = Field(default_factory=list)


class LLMConfig(BaseModel):
    enabled: bool = True
    provider: Literal["openai", "azure_openai", "ollama"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None
    timeout_sec: int = 30
    max_tokens: int = 800
    temperature: float = 0.2


class SlackConfig(BaseModel):
    enabled: bool = False
    webhook_url_env: str = "SLACK_WEBHOOK_URL"


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    username_env: str = "SMTP_USER"
    password_env: str = "SMTP_PASSWORD"
    from_addr: str = "agent@example.com"
    to_addrs: List[str] = Field(default_factory=list)


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id: str = ""


class NotificationConfig(BaseModel):
    slack: SlackConfig = Field(default_factory=SlackConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class GitHubConfig(BaseModel):
    enabled: bool = False
    token_env: str = "GITHUB_TOKEN"
    api_base: str = "https://api.github.com"


class GitLabConfig(BaseModel):
    enabled: bool = False
    token_env: str = "GITLAB_TOKEN"
    api_base: str = "https://gitlab.com/api/v4"


class OrchestrationConfig(BaseModel):
    docker_host: Optional[str] = None
    kubeconfig: Optional[Path] = None


class WebhookServerConfig(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    shared_secret_env: str = "WEBHOOK_SECRET"


class AgentConfig(BaseModel):
    agent: AgentIdentity = Field(default_factory=AgentIdentity)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    rbac_roles: List[RBACRole] = Field(default_factory=list)
    checks: List[CheckConfig] = Field(default_factory=list)
    services: List[ServiceConfig] = Field(default_factory=list)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    webhooks: WebhookServerConfig = Field(default_factory=WebhookServerConfig)
    polling_jitter_sec: int = 3
    max_concurrent_checks: int = 10

    @field_validator("rbac_roles")
    @classmethod
    def ensure_admin_role(cls, value: List[RBACRole]) -> List[RBACRole]:
        if not value:
            return [
                RBACRole(
                    name="admin",
                    allow=[
                        "read_logs",
                        "restart_service",
                        "deploy",
                        "apply_patch",
                        "run_command",
                        "ssh",
                        "notify",
                    ],
                )
            ]
        return value


def load_config(path: Path) -> AgentConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    try:
        config = AgentConfig(**raw)
        return resolve_paths(config, base_dir=path.parent)
    except ValidationError as exc:
        details = exc.errors(include_url=False, include_context=False)
        raise SystemExit(f"Config validation failed: {details}") from exc


def resolve_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value
    return default


def resolve_paths(config: AgentConfig, base_dir: Path) -> AgentConfig:
    def _resolve(path: Optional[Path]) -> Optional[Path]:
        if not path:
            return path
        return path if path.is_absolute() else base_dir / path

    config.paths.data_dir = _resolve(config.paths.data_dir) or config.paths.data_dir
    config.paths.logs_dir = _resolve(config.paths.logs_dir) or config.paths.logs_dir
    config.paths.audit_log = _resolve(config.paths.audit_log) or config.paths.audit_log
    config.paths.memory_db = _resolve(config.paths.memory_db) or config.paths.memory_db
    if config.orchestration.kubeconfig:
        config.orchestration.kubeconfig = _resolve(config.orchestration.kubeconfig)
    for check in config.checks:
        if isinstance(check, LogCheckConfig):
            check.file_path = _resolve(check.file_path) or check.file_path
    for service in config.services:
        if service.repo_path:
            service.repo_path = _resolve(service.repo_path)
        service.log_paths = [_resolve(path) or path for path in service.log_paths]
    return config
