from __future__ import annotations

from sqlalchemy import create_engine, text

from .base import CheckResult, HealthCheck


class DatabaseCheck(HealthCheck):
    async def check(self) -> CheckResult:
        try:
            engine = create_engine(self.config.dsn)
            with engine.connect() as conn:
                result = conn.execute(text(self.config.query))
                value = result.scalar()
            comparator = self.config.comparator
            expected = self.config.expected
            comparison = {
                ">": value > expected,
                ">=": value >= expected,
                "<": value < expected,
                "<=": value <= expected,
                "==": value == expected,
                "!=": value != expected,
            }[comparator]
            if comparison:
                return CheckResult(
                    name=self.name,
                    status="ok",
                    message=f"Database check passed ({value} {comparator} {expected})",
                    meta={"value": value},
                )
            return CheckResult(
                name=self.name,
                status="warn",
                message=f"Database check failed ({value} not {comparator} {expected})",
                meta={"value": value},
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status="critical",
                message=f"Database check failed: {exc}",
            )
