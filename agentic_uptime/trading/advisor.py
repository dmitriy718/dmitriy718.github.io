from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from ..analysis.llm_client import LLMClient
from .explainability import ParameterAdjustment
from .risk import RiskPolicy


@dataclass
class AdvisorResult:
    approved: bool
    adjustments: List[ParameterAdjustment]
    raw_response: str
    blocked_reasons: List[str]


class SafetyGuard:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def validate(self, adjustments: List[ParameterAdjustment]) -> List[str]:
        reasons: List[str] = []
        for adj in adjustments:
            if adj.param.startswith("risk."):
                reasons.extend(self._validate_risk_adjustment(adj))
        return reasons

    def _validate_risk_adjustment(self, adj: ParameterAdjustment) -> List[str]:
        reasons: List[str] = []
        if adj.param == "risk.max_notional_per_trade" and adj.value > self.policy.max_notional_per_trade:
            reasons.append("increase_max_notional_denied")
        if adj.param == "risk.max_position_pct" and adj.value > self.policy.max_position_pct:
            reasons.append("increase_max_position_denied")
        if adj.param == "risk.max_drawdown_pct" and adj.value > self.policy.max_drawdown_pct:
            reasons.append("increase_drawdown_denied")
        if adj.param == "risk.min_cash_pct" and adj.value < self.policy.min_cash_pct:
            reasons.append("lower_min_cash_denied")
        return reasons


class TradingLLMAdvisor:
    def __init__(self, llm: LLMClient, policy: RiskPolicy) -> None:
        self.llm = llm
        self.guard = SafetyGuard(policy)

    def suggest(self, context: str) -> AdvisorResult:
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a trading risk analyst. "
                    "Return JSON list of adjustments with keys: param, value, reason."
                ),
            },
            {"role": "user", "content": context},
        ]
        response = self.llm.chat(prompt)
        adjustments = self._parse_response(response)
        violations = self.guard.validate(adjustments)
        return AdvisorResult(
            approved=not violations,
            adjustments=adjustments,
            raw_response=response,
            blocked_reasons=violations,
        )

    def _parse_response(self, response: str) -> List[ParameterAdjustment]:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            return []
        adjustments = []
        for item in payload:
            adjustments.append(
                ParameterAdjustment(
                    param=item["param"],
                    value=float(item["value"]),
                    reason=item.get("reason", ""),
                )
            )
        return adjustments
