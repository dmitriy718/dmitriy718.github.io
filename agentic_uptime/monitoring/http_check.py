from __future__ import annotations

import time
from typing import Optional

import httpx

from .base import CheckResult, HealthCheck


class HTTPCheck(HealthCheck):
    async def check(self) -> CheckResult:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                follow_redirects=self.config.follow_redirects,
                verify=self.config.verify_tls,
                timeout=self.config.timeout_sec,
            ) as client:
                response = await client.request(
                    self.config.method,
                    str(self.config.url),
                    headers=self.config.headers,
                    content=self.config.body,
                )
            latency_ms = int((time.perf_counter() - start) * 1000)
            if response.status_code not in self.config.expected_status:
                return CheckResult(
                    name=self.name,
                    status="critical",
                    message=f"Unexpected status {response.status_code}",
                    latency_ms=latency_ms,
                    meta={"status_code": response.status_code},
                )
            if self.config.max_latency_ms and latency_ms > self.config.max_latency_ms:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=f"High latency {latency_ms}ms",
                    latency_ms=latency_ms,
                    meta={"status_code": response.status_code},
                )
            return CheckResult(
                name=self.name,
                status="ok",
                message="HTTP check passed",
                latency_ms=latency_ms,
                meta={"status_code": response.status_code},
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"HTTP check failed: {exc}",
                latency_ms=latency_ms,
            )
