from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

from ..audit import AuditLogger
from ..rbac import RBAC
from ..utils.subprocess_runner import run_command


class DiagnosticsCollector:
    def __init__(self, rbac: RBAC, audit: AuditLogger) -> None:
        self.rbac = rbac
        self.audit = audit

    def _run(self, action: str, command: list[str], timeout_sec: int = 20) -> str:
        self.rbac.require("run_command")
        result = run_command(command, timeout_sec=timeout_sec)
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action=action,
            status=status,
            details={"command": result.command, "exit_code": result.exit_code},
        )
        output = result.stdout or result.stderr
        return output

    def collect(
        self,
        log_paths: Iterable[Path],
        systemd_service: Optional[str] = None,
        repo_path: Optional[Path] = None,
        docker_container: Optional[str] = None,
    ) -> Dict[str, str]:
        context: Dict[str, str] = {}
        for path in log_paths:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore")
                context[f"log:{path}"] = "\n".join(content.splitlines()[-200:])
        if systemd_service:
            context["systemd_status"] = self._run(
                "systemd_status", ["systemctl", "status", systemd_service, "--no-pager"]
            )
        if docker_container:
            context["docker_ps"] = self._run("docker_ps", ["docker", "ps", "--no-trunc"])
            context["docker_logs"] = self._run(
                "docker_logs",
                ["docker", "logs", "--tail", "200", docker_container],
            )
        if repo_path:
            context["git_recent"] = self._run(
                "git_recent",
                ["git", "-C", str(repo_path), "log", "-n", "5", "--oneline"],
            )
            context["git_status"] = self._run(
                "git_status",
                ["git", "-C", str(repo_path), "status", "--short"],
            )
        return context
