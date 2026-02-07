from __future__ import annotations

import re
import time
from collections import deque

from .base import CheckResult, HealthCheck
from ..utils.file_tail import TailState, read_new_lines


class LogCheck(HealthCheck):
    def __init__(self, name: str, config: object) -> None:
        super().__init__(name, config)
        self._state = TailState()
        self._hits = deque()
        self._pattern = re.compile(self.config.regex)

    async def check(self) -> CheckResult:
        now = time.time()
        lines = read_new_lines(self.config.file_path, self._state)
        for line in lines:
            if self._pattern.search(line):
                self._hits.append(now)
        while self._hits and now - self._hits[0] > self.config.window_sec:
            self._hits.popleft()
        if len(self._hits) >= self.config.min_hits:
            return CheckResult(
                name=self.name,
                status="warn",
                message=f"Log pattern hit {len(self._hits)} times",
                meta={"hits": len(self._hits)},
            )
        return CheckResult(
            name=self.name,
            status="ok",
            message="No log anomalies",
        )
