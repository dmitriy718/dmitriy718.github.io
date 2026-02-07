from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


def run_command(
    command: Union[str, List[str]],
    timeout_sec: int = 30,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    shell: bool = False,
) -> CommandResult:
    if isinstance(command, list):
        cmd_display = " ".join(shlex.quote(part) for part in command)
    else:
        cmd_display = command
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        command,
        timeout=timeout_sec,
        capture_output=True,
        text=True,
        env=merged_env,
        cwd=cwd,
        shell=shell,
        check=False,
    )
    return CommandResult(
        command=cmd_display,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
