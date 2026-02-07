from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .models import TradeDecision


class DecisionJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, decision: TradeDecision) -> None:
        payload = {
            "timestamp": decision.timestamp,
            "symbol": decision.signal.symbol,
            "side": decision.signal.side,
            "quantity": decision.signal.quantity,
            "confidence": decision.signal.confidence,
            "reason_codes": decision.signal.reason_codes,
            "risk_allowed": decision.risk_allowed,
            "risk_reasons": decision.risk_reasons,
            "execution": None,
            "notes": decision.notes,
        }
        if decision.execution:
            payload["execution"] = {
                "status": decision.execution.status,
                "filled_qty": decision.execution.filled_qty,
                "avg_price": decision.execution.avg_price,
                "message": decision.execution.message,
                "latency_ms": decision.execution.latency_ms,
            }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


@dataclass
class TradeMetrics:
    total_trades: int
    win_rate: float
    avg_slippage_bps: float
    avg_pnl: float
    max_drawdown_pct: float


class PostTradeAnalyzer:
    def analyze(self, decisions: List[TradeDecision]) -> TradeMetrics:
        trades = [d for d in decisions if d.execution and d.execution.filled_qty > 0]
        if not trades:
            return TradeMetrics(0, 0.0, 0.0, 0.0, 0.0)
        wins = 0
        pnls = []
        slippages = []
        equity = 1.0
        peak = 1.0
        for decision in trades:
            expected = decision.signal.expected_price or decision.execution.avg_price
            actual = decision.execution.avg_price
            pnl = (actual - expected) * decision.execution.filled_qty
            if decision.signal.side == "sell":
                pnl = -pnl
            pnls.append(pnl)
            if pnl > 0:
                wins += 1
            if expected > 0:
                slippage = abs(actual - expected) / expected * 10_000
                slippages.append(slippage)
            equity += pnl
            peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak else 0.0
        return TradeMetrics(
            total_trades=len(trades),
            win_rate=wins / len(trades),
            avg_slippage_bps=sum(slippages) / len(slippages) if slippages else 0.0,
            avg_pnl=sum(pnls) / len(pnls),
            max_drawdown_pct=drawdown,
        )


@dataclass
class ParameterAdjustment:
    param: str
    value: float
    reason: str


class LearningLoop:
    def propose_adjustments(self, metrics: TradeMetrics) -> List[ParameterAdjustment]:
        adjustments: List[ParameterAdjustment] = []
        if metrics.avg_slippage_bps > 50:
            adjustments.append(
                ParameterAdjustment(
                    param="execution.limit_price_offset_bps",
                    value=5.0,
                    reason="High average slippage; tighten limit offset.",
                )
            )
        if metrics.win_rate < 0.4 and metrics.total_trades > 10:
            adjustments.append(
                ParameterAdjustment(
                    param="strategy.order_size",
                    value=0.5,
                    reason="Low win rate; reduce order size.",
                )
            )
        if metrics.max_drawdown_pct > 0.2:
            adjustments.append(
                ParameterAdjustment(
                    param="risk.max_position_pct",
                    value=0.1,
                    reason="Drawdown too high; lower max position.",
                )
            )
        return adjustments
