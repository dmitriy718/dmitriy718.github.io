from __future__ import annotations

from .base import CheckResult, HealthCheck
from ..utils.subprocess_runner import run_command


class SystemdCheck(HealthCheck):
    async def check(self) -> CheckResult:
        result = run_command(
            ["systemctl", "is-active", self.config.service_name],
            timeout_sec=self.config.timeout_sec,
        )
        if result.exit_code != 0:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Systemd service not active: {result.stdout or result.stderr}",
                meta={"service": self.config.service_name},
            )
        return CheckResult(
            name=self.name,
            status="ok",
            message="Systemd service active",
            meta={"service": self.config.service_name},
        )
