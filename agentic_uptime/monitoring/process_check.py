from __future__ import annotations

import psutil

from .base import CheckResult, HealthCheck


class ProcessCheck(HealthCheck):
    async def check(self) -> CheckResult:
        matches = [
            proc
            for proc in psutil.process_iter(attrs=["name", "cpu_percent", "memory_info"])
            if proc.info.get("name") == self.config.process_name
        ]
        count = len(matches)
        if count < self.config.min_count:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Process count {count} below {self.config.min_count}",
                meta={"count": count},
            )
        max_cpu = self.config.max_cpu_percent
        if max_cpu is not None:
            high_cpu = [p for p in matches if (p.info.get("cpu_percent") or 0) > max_cpu]
            if high_cpu:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=f"High CPU for {len(high_cpu)} processes",
                    meta={"count": count},
                )
        max_mem = self.config.max_memory_mb
        if max_mem is not None:
            high_mem = [
                p
                for p in matches
                if (p.info.get("memory_info") and p.info["memory_info"].rss)
                and (p.info["memory_info"].rss / (1024 * 1024) > max_mem)
            ]
            if high_mem:
                return CheckResult(
                    name=self.name,
                    status="warn",
                    message=f"High memory for {len(high_mem)} processes",
                    meta={"count": count},
                )
        return CheckResult(
            name=self.name,
            status="ok",
            message=f"Process count {count} ok",
            meta={"count": count},
        )
