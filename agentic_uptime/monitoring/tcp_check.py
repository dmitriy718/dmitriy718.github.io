from __future__ import annotations

import asyncio
import time

from .base import CheckResult, HealthCheck


class TCPCheck(HealthCheck):
    async def check(self) -> CheckResult:
        start = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.port),
                timeout=self.config.timeout_sec,
            )
            writer.close()
            await writer.wait_closed()
            latency_ms = int((time.perf_counter() - start) * 1000)
            return CheckResult(
                name=self.name,
                status="ok",
                message="TCP port open",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"TCP check failed: {exc}",
                latency_ms=latency_ms,
            )
