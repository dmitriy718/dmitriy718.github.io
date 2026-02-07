from __future__ import annotations

from typing import Any, Dict

from ..audit import AuditLogger
from ..rbac import RBAC
from ..utils.env import get_env
from ..utils.subprocess_runner import run_command
from ..integrations.github import GitHubClient
from ..integrations.gitlab import GitLabClient


class DeploymentManager:
    def __init__(self, rbac: RBAC, audit: AuditLogger) -> None:
        self.rbac = rbac
        self.audit = audit

    def restart_systemd(self, service_name: str) -> str:
        self.rbac.require("restart_service")
        result = run_command(["systemctl", "restart", service_name])
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="restart_systemd",
            status=status,
            details={"service": service_name},
        )
        return result.stdout or result.stderr

    def restart_docker(self, container_name: str) -> str:
        self.rbac.require("restart_service")
        result = run_command(["docker", "restart", container_name])
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="restart_docker",
            status=status,
            details={"container": container_name},
        )
        return result.stdout or result.stderr

    def restart_k8s(self, deployment: str, namespace: str = "default") -> str:
        self.rbac.require("restart_service")
        result = run_command(
            ["kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", namespace]
        )
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="restart_k8s",
            status=status,
            details={"deployment": deployment, "namespace": namespace},
        )
        return result.stdout or result.stderr

    def ssh_command(
        self, host: str, user: str, command: str, port: int, password_env: str
    ) -> str:
        self.rbac.require("ssh")
        password = get_env(password_env, required=True)
        target = f"{user}@{host}"
        result = run_command(
            [
                "sshpass",
                "-e",
                "ssh",
                "-p",
                str(port),
                "-o",
                "StrictHostKeyChecking=no",
                target,
                command,
            ],
            env={"SSHPASS": password},
            timeout_sec=60,
        )
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="ssh_command",
            status=status,
            details={"host": host, "command": command},
        )
        return result.stdout or result.stderr

    def run_script(self, command: str, shell: bool = True) -> str:
        self.rbac.require("run_command")
        result = run_command(command, shell=shell, timeout_sec=120)
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="run_script",
            status=status,
            details={"command": result.command},
        )
        return result.stdout or result.stderr

    def deploy_github(self, repo: str, workflow: str, ref: str, inputs: Dict[str, Any]) -> str:
        self.rbac.require("deploy")
        client = GitHubClient()
        response = client.dispatch_workflow(repo, workflow, ref, inputs)
        self.audit.log(
            actor=self.rbac.agent_name,
            action="deploy_github",
            status="ok",
            details={"repo": repo, "workflow": workflow},
        )
        return response

    def deploy_gitlab(self, project_id: str, ref: str, variables: Dict[str, Any]) -> str:
        self.rbac.require("deploy")
        client = GitLabClient()
        response = client.trigger_pipeline(project_id, ref, variables)
        self.audit.log(
            actor=self.rbac.agent_name,
            action="deploy_gitlab",
            status="ok",
            details={"project": project_id},
        )
        return response

    def execute_step(self, action: str, args: Dict[str, Any]) -> str:
        if action == "restart_systemd":
            return self.restart_systemd(args["service_name"])
        if action == "restart_docker":
            return self.restart_docker(args["container_name"])
        if action == "restart_k8s":
            return self.restart_k8s(args["deployment"], args.get("namespace", "default"))
        if action == "ssh_command":
            return self.ssh_command(
                args["host"],
                args["user"],
                args["command"],
                int(args.get("port", 22)),
                args.get("password_env", "SSH_PASSWORD"),
            )
        if action == "run_script":
            return self.run_script(args["command"], args.get("shell", True))
        if action == "deploy_github":
            return self.deploy_github(
                args["repo"],
                args["workflow"],
                args["ref"],
                args.get("inputs", {}),
            )
        if action == "deploy_gitlab":
            return self.deploy_gitlab(
                args["project_id"],
                args["ref"],
                args.get("variables", {}),
            )
        raise ValueError(f"Unsupported runbook action: {action}")
