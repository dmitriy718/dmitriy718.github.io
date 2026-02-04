from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    latency_ms: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HealthCheck:
    def __init__(self, name: str, config: Any) -> None:
        self.name = name
        self.config = config

    async def check(self) -> CheckResult:
        raise NotImplementedError
