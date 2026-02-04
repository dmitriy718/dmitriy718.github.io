from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .audit import AuditLogger
from .config import AgentConfig, CheckConfig, ServiceConfig
from .memory import MemoryStore
from .rbac import RBAC, Role
from .monitoring.base import CheckResult, HealthCheck
from .monitoring.database_check import DatabaseCheck
from .monitoring.datadog_check import DatadogCheck
from .monitoring.grafana_check import GrafanaCheck
from .monitoring.http_check import HTTPCheck
from .monitoring.log_check import LogCheck
from .monitoring.process_check import ProcessCheck
from .monitoring.prometheus_check import PrometheusCheck
from .monitoring.script_check import ScriptCheck
from .monitoring.ssh_check import SSHCheck
from .monitoring.systemd_check import SystemdCheck
from .monitoring.tcp_check import TCPCheck
from .notifications.base import NotificationManager
from .repair.auto_heal import AutoHealer, IncidentContext


@dataclass
class CheckState:
    failure_count: int = 0
    ok_count: int = 0
    incident_id: Optional[int] = None
    last_status: str = "unknown"


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        audit: AuditLogger,
        memory: MemoryStore,
        rbac: RBAC,
        notifier: NotificationManager,
        auto_healer: AutoHealer,
    ) -> None:
        self.config = config
        self.audit = audit
        self.memory = memory
        self.rbac = rbac
        self.notifier = notifier
        self.auto_healer = auto_healer
        self.logger = logging.getLogger(__name__)
        self.checks: Dict[str, HealthCheck] = {}
        self.check_configs: Dict[str, CheckConfig] = {}
        self.states: Dict[str, CheckState] = {}
        self.services: Dict[str, ServiceConfig] = {
            svc.name: svc for svc in config.services
        }
        self.semaphore = asyncio.Semaphore(config.max_concurrent_checks)
        self._build_checks()

    def _build_checks(self) -> None:
        mapping = {
            "http": HTTPCheck,
            "tcp": TCPCheck,
            "process": ProcessCheck,
            "systemd": SystemdCheck,
            "prometheus": PrometheusCheck,
            "grafana": GrafanaCheck,
            "datadog": DatadogCheck,
            "log": LogCheck,
            "script": ScriptCheck,
            "database": DatabaseCheck,
            "ssh": SSHCheck,
        }
        for check in self.config.checks:
            if not check.enabled:
                continue
            cls = mapping.get(check.type)
            if not cls:
                raise ValueError(f"Unsupported check type: {check.type}")
            instance = cls(check.name, check)
            self.checks[check.name] = instance
            self.check_configs[check.name] = check
            self.states[check.name] = CheckState()

    async def run(self, webhook_queue: Optional[asyncio.Queue] = None) -> None:
        tasks = [self._run_check_loop(name, check) for name, check in self.checks.items()]
        if webhook_queue is not None:
            tasks.append(self._run_webhook_loop(webhook_queue))
        await asyncio.gather(*tasks)

    async def _run_check_loop(self, name: str, check: HealthCheck) -> None:
        config = self.check_configs[name]
        while True:
            async with self.semaphore:
                result = await check.check()
            await self._handle_result(config, result)
            jitter = random.uniform(0, self.config.polling_jitter_sec)
            await asyncio.sleep(config.interval_sec + jitter)

    async def _handle_result(self, config: CheckConfig, result: CheckResult) -> None:
        state = self.states[result.name]
        if result.status in {"critical", "warn"}:
            state.failure_count += 1
            state.ok_count = 0
            if state.failure_count >= config.failure_policy.fail_after:
                if state.incident_id is None:
                    incident_id = self.memory.record_incident(
                        service=config.service or "unknown",
                        check_name=result.name,
                        status=result.status,
                        message=result.message,
                    )
                    state.incident_id = incident_id
                    incident = IncidentContext(
                        incident_id=incident_id,
                        check_name=result.name,
                        status=result.status,
                        message=result.message,
                    )
                    service = self.services.get(config.service or "")
                    report = await asyncio.to_thread(
                        self.auto_healer.handle_incident, incident, service
                    )
                    self._notify_incident(result, report)
        else:
            state.ok_count += 1
            state.failure_count = 0
            if state.incident_id and state.ok_count >= config.failure_policy.recover_after:
                self.memory.resolve_incident(state.incident_id)
                if config.notify_on_recover:
                    self._notify_recovery(result)
                state.incident_id = None
        state.last_status = result.status

    def _notify_incident(self, result: CheckResult, report: Dict[str, Any]) -> None:
        if not self.rbac.authorize("notify"):
            return
        title = f"Incident: {result.name}"
        message = f"{result.message}\nReport: {report}"
        self.notifier.notify(title, message, level=result.status)

    def _notify_recovery(self, result: CheckResult) -> None:
        if not self.rbac.authorize("notify"):
            return
        title = f"Recovery: {result.name}"
        message = f"{result.message}"
        self.notifier.notify(title, message, level="ok")

    async def _run_webhook_loop(self, queue: asyncio.Queue) -> None:
        while True:
            payload = await queue.get()
            self.logger.info("Webhook received: %s", payload.get("event", "unknown"))
            for name, check in self.checks.items():
                config = self.check_configs[name]
                async with self.semaphore:
                    result = await check.check()
                await self._handle_result(config, result)
            queue.task_done()


def build_rbac(config: AgentConfig) -> RBAC:
    roles = [Role(name=role.name, allow=set(role.allow)) for role in config.rbac_roles]
    return RBAC(
        roles=roles,
        agent_name=config.agent.name,
        agent_role=config.agent.role,
    )
