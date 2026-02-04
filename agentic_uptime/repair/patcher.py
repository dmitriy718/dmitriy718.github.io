from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Optional

from ..audit import AuditLogger
from ..rbac import RBAC
from ..utils.subprocess_runner import run_command


class PatchApplier:
    def __init__(self, rbac: RBAC, audit: AuditLogger) -> None:
        self.rbac = rbac
        self.audit = audit

    def _validate_diff(self, diff_text: str) -> None:
        file_lines = [
            line[4:].strip()
            for line in diff_text.splitlines()
            if line.startswith("+++ ") or line.startswith("--- ")
        ]
        for file_line in file_lines:
            if file_line.startswith("/"):
                raise ValueError("Patch uses absolute paths")
            if ".." in Path(file_line).parts:
                raise ValueError("Patch attempts directory traversal")

    def apply_patch(self, repo_path: Path, diff_text: str) -> str:
        self.rbac.require("apply_patch")
        self._validate_diff(diff_text)
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(diff_text)
            patch_file = handle.name
        result = run_command(
            ["git", "-C", str(repo_path), "apply", "--whitespace=fix", patch_file],
            timeout_sec=60,
        )
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="apply_patch",
            status=status,
            details={"repo": str(repo_path), "exit_code": result.exit_code},
        )
        if result.exit_code != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout or "Patch applied"

    def run_tests(self, repo_path: Path, command: str) -> str:
        self.rbac.require("run_command")
        result = run_command(
            command,
            cwd=str(repo_path),
            shell=True,
            timeout_sec=300,
        )
        status = "ok" if result.exit_code == 0 else "error"
        self.audit.log(
            actor=self.rbac.agent_name,
            action="run_tests",
            status=status,
            details={"command": result.command},
        )
        if result.exit_code != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout or "Tests passed"
