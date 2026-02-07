from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


@dataclass
class AuditEvent:
    actor: str
    action: str
    status: str
    details: Dict[str, Any]
    timestamp: str


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, actor: str, action: str, status: str, details: Dict[str, Any]) -> None:
        event = AuditEvent(
            actor=actor,
            action=action,
            status=status,
            details=details,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")
