from __future__ import annotations

from .base import CheckResult, HealthCheck
from ..utils.subprocess_runner import run_command


class ScriptCheck(HealthCheck):
    async def check(self) -> CheckResult:
        result = run_command(
            self.config.command,
            timeout_sec=self.config.timeout_sec,
            shell=self.config.shell,
        )
        if result.exit_code != self.config.expected_exit_code:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Script failed: {result.stderr or result.stdout}",
                meta={"exit_code": result.exit_code},
            )
        return CheckResult(
            name=self.name,
            status="ok",
            message="Script succeeded",
            meta={"stdout": result.stdout},
        )
