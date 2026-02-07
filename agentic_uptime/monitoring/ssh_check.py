from __future__ import annotations

from .base import CheckResult, HealthCheck
from ..utils.env import get_env
from ..utils.subprocess_runner import run_command


class SSHCheck(HealthCheck):
    async def check(self) -> CheckResult:
        password = get_env(self.config.password_env, required=True)
        target = f"{self.config.user}@{self.config.host}"
        command = [
            "sshpass",
            "-e",
            "ssh",
            "-p",
            str(self.config.port),
            "-o",
            "StrictHostKeyChecking=no",
            target,
            self.config.command,
        ]
        result = run_command(
            command,
            timeout_sec=self.config.timeout_sec,
            env={"SSHPASS": password},
        )
        if result.exit_code != 0:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"SSH check failed: {result.stderr or result.stdout}",
                meta={"exit_code": result.exit_code},
            )
        return CheckResult(
            name=self.name,
            status="ok",
            message="SSH check ok",
            meta={"stdout": result.stdout},
        )
