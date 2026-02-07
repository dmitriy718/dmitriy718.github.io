from __future__ import annotations

import httpx

from .base import CheckResult, HealthCheck


class PrometheusCheck(HealthCheck):
    async def check(self) -> CheckResult:
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                response = await client.get(
                    f"{self.config.base_url}/api/v1/query",
                    params={"query": self.config.query},
                )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "success":
                return CheckResult(
                    name=self.name,
                    status="critical",
                    message=f"Prometheus query failed: {payload}",
                )
            result = payload.get("data", {}).get("result", [])
            value = 0.0
            if result:
                value = float(result[0]["value"][1])
            comparator = self.config.comparator
            threshold = self.config.threshold
            comparison = {
                ">": value > threshold,
                ">=": value >= threshold,
                "<": value < threshold,
                "<=": value <= threshold,
                "==": value == threshold,
            }[comparator]
            if comparison:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=f"Prometheus value {value} breached {comparator} {threshold}",
                    meta={"value": value},
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message=f"Prometheus value {value} within threshold",
                meta={"value": value},
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Prometheus check failed: {exc}",
            )
