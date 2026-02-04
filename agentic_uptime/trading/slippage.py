from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import MarketSnapshot, OrderSide


@dataclass
class SlippageDecision:
    allowed: bool
    slippage_bps: float
    reason: Optional[str] = None


@dataclass
class SlippageGuard:
    max_slippage_bps: float = 50.0
    max_price_impact_bps: float = 75.0

    def evaluate(
        self,
        expected_price: float,
        actual_price: float,
        side: OrderSide,
        snapshot: Optional[MarketSnapshot] = None,
    ) -> SlippageDecision:
        if expected_price <= 0 or actual_price <= 0:
            return SlippageDecision(False, 0.0, "invalid_price")
        slippage_bps = self._adverse_bps(expected_price, actual_price, side)
        if slippage_bps > self.max_slippage_bps:
            return SlippageDecision(False, slippage_bps, "slippage_exceeded")
        if snapshot:
            price_impact = self._price_impact_bps(snapshot, actual_price)
            if price_impact > self.max_price_impact_bps:
                return SlippageDecision(False, slippage_bps, "price_impact_exceeded")
        return SlippageDecision(True, slippage_bps, None)

    @staticmethod
    def _adverse_bps(expected: float, actual: float, side: OrderSide) -> float:
        if side == "buy":
            return max(0.0, (actual - expected) / expected * 10_000)
        return max(0.0, (expected - actual) / expected * 10_000)

    @staticmethod
    def _price_impact_bps(snapshot: MarketSnapshot, actual: float) -> float:
        if snapshot.mid <= 0:
            return 0.0
        return abs(actual - snapshot.mid) / snapshot.mid * 10_000
