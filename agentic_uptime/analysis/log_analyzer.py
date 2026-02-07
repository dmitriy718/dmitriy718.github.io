from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .llm_client import LLMClient


@dataclass
class AnalysisReport:
    summary: str
    suspected_cause: str
    recommendations: List[str]
    raw_model_output: Optional[str] = None


class LogAnalyzer:
    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm
        self._patterns = [
            (re.compile(r"connection refused", re.I), "Upstream connection refused"),
            (re.compile(r"timeout", re.I), "Timeout contacting dependency"),
            (re.compile(r"out of memory|oom", re.I), "Memory exhaustion"),
            (re.compile(r"segmentation fault", re.I), "Process crash (segfault)"),
            (re.compile(r"permission denied", re.I), "Permission denied"),
            (re.compile(r"disk full|no space left", re.I), "Disk full"),
            (re.compile(r"migration", re.I), "Database migration issue"),
        ]

    def analyze(self, context: Dict[str, str]) -> AnalysisReport:
        combined = "\n".join(context.values())
        for pattern, meaning in self._patterns:
            if pattern.search(combined):
                return AnalysisReport(
                    summary="Log pattern matched",
                    suspected_cause=meaning,
                    recommendations=[f"Investigate: {meaning}"],
                )
        if self.llm:
            prompt = [
                {
                    "role": "system",
                    "content": "You are a reliability engineer. Analyze logs and suggest root cause and fixes.",
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze the following diagnostic context and provide:\n"
                        "1. Root cause hypothesis\n"
                        "2. Immediate remediation steps\n"
                        "3. Preventive recommendation\n\n"
                        f"Context:\n{combined}"
                    ),
                },
            ]
            try:
                response = self.llm.chat(prompt)
                lines = [line.strip() for line in response.splitlines() if line.strip()]
                summary = lines[0] if lines else "LLM analysis generated"
                return AnalysisReport(
                    summary=summary,
                    suspected_cause=summary,
                    recommendations=lines[1:4] if len(lines) > 1 else [],
                    raw_model_output=response,
                )
            except Exception as exc:
                return AnalysisReport(
                    summary="LLM analysis failed",
                    suspected_cause=str(exc),
                    recommendations=["Review logs manually"],
                )
        return AnalysisReport(
            summary="No obvious log patterns",
            suspected_cause="Unknown",
            recommendations=["Gather additional diagnostics"],
        )
