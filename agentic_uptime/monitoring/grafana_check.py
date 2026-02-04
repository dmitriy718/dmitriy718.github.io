from __future__ import annotations

import httpx

from .base import CheckResult, HealthCheck
from ..utils.env import get_env


class GrafanaCheck(HealthCheck):
    async def check(self) -> CheckResult:
        headers = {}
        api_key = get_env(self.config.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                health_resp = await client.get(
                    f"{self.config.base_url}/api/health", headers=headers
                )
                health_resp.raise_for_status()
                alerts_resp = await client.get(
                    f"{self.config.base_url}/api/alerts", headers=headers
                )
                alerts_resp.raise_for_status()
            alerts = alerts_resp.json() if alerts_resp.content else []
            matching = [
                alert
                for alert in alerts
                if alert.get("state") in self.config.alert_states
            ]
            if matching:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=f"Grafana alerts: {len(matching)} active",
                    meta={"alerts": matching[:5]},
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message="Grafana healthy",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Grafana check failed: {exc}",
            )
