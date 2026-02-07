from __future__ import annotations

import time
import httpx

from .base import CheckResult, HealthCheck
from ..utils.env import get_env


class DatadogCheck(HealthCheck):
    async def check(self) -> CheckResult:
        api_key = get_env(self.config.api_key_env, required=True)
        app_key = get_env(self.config.app_key_env, required=True)
        headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                if self.config.monitor_id is not None:
                    resp = await client.get(
                        f"{self.config.base_url}/api/v1/monitor/{self.config.monitor_id}",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    monitor = resp.json()
                    state = monitor.get("overall_state", "").lower()
                    if state in {"alert", "warn", "no data"}:
                        return CheckResult(
                            name=self.name,
                            status="warn",
                            message=f"Datadog monitor in state {state}",
                            meta={"monitor": monitor.get("name")},
                        )
                elif self.config.query:
                    now = int(time.time())
                    resp = await client.get(
                        f"{self.config.base_url}/api/v1/query",
                        headers=headers,
                        params={
                            "query": self.config.query,
                            "from": now - 300,
                            "to": now,
                        },
                    )
                    resp.raise_for_status()
                else:
                    return CheckResult(
                        name=self.name,
                        status="critical",
                        message="Datadog check missing monitor_id or query",
                    )
            return CheckResult(
                name=self.name,
                status="ok",
                message="Datadog check ok",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Datadog check failed: {exc}",
            )
