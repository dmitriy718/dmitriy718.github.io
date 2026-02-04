from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .models import ExecutionResult, MarketSnapshot, Order, PortfolioState, TradeDecision, TradeSignal
from .risk import RiskEngine, RiskDecision
from .slippage import SlippageDecision, SlippageGuard
from .explainability import DecisionJournal
from .exchanges.base import ExchangeClient


@dataclass
class ExecutionConfig:
    max_retries: int = 2
    retry_backoff_sec: float = 0.5
    max_consecutive_failures: int = 3
    circuit_breaker_timeout_sec: int = 60
    fallback_to_limit: bool = True
    limit_price_offset_bps: float = 10.0
    max_latency_ms: int = 2_000


@dataclass
class ExecutionHealth:
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0
    last_latency_ms: Optional[int] = None

    def circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until

    def register_failure(self, max_failures: int, timeout_sec: int) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= max_failures:
            self.circuit_open_until = time.time() + timeout_sec

    def register_success(self) -> None:
        self.consecutive_failures = 0


class ExecutionEngine:
    def __init__(
        self,
        exchange: ExchangeClient,
        risk_engine: RiskEngine,
        slippage_guard: SlippageGuard,
        config: Optional[ExecutionConfig] = None,
        journal: Optional[DecisionJournal] = None,
    ) -> None:
        self.exchange = exchange
        self.risk_engine = risk_engine
        self.slippage_guard = slippage_guard
        self.config = config or ExecutionConfig()
        self.health = ExecutionHealth()
        self.journal = journal

    def execute_signal(
        self,
        signal: TradeSignal,
        snapshot: MarketSnapshot,
        portfolio: PortfolioState,
    ) -> TradeDecision:
        order = Order(
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            order_type="market",
            expected_price=signal.expected_price or snapshot.mid,
        )
        risk_decision = self.risk_engine.evaluate_order(order, snapshot, portfolio)
        decision = TradeDecision(
            timestamp=snapshot.timestamp,
            signal=signal,
            risk_allowed=risk_decision.allowed,
            risk_reasons=risk_decision.reasons,
        )
        if not risk_decision.allowed:
            if self.journal:
                self.journal.record(decision)
            return decision
        if risk_decision.adjusted_qty:
            order.quantity = risk_decision.adjusted_qty

        if self.health.circuit_open():
            decision.risk_allowed = False
            decision.risk_reasons.append("circuit_breaker_open")
            if self.journal:
                self.journal.record(decision)
            return decision

        result = self._place_with_retries(order, snapshot)
        decision.execution = result
        if result.status in {"filled", "partial"}:
            slippage = self.slippage_guard.evaluate(
                order.expected_price or snapshot.mid, result.avg_price, order.side, snapshot
            )
            if not slippage.allowed and self.config.fallback_to_limit:
                result = self._fallback_limit(order, snapshot)
                decision.execution = result
            self.risk_engine.update_after_fill(
                portfolio, order, result.avg_price, result.filled_qty
            )
        if self.journal:
            self.journal.record(decision)
        return decision

    def _place_with_retries(self, order: Order, snapshot: MarketSnapshot) -> ExecutionResult:
        attempts = 0
        while attempts <= self.config.max_retries:
            attempts += 1
            start = time.perf_counter()
            result = self.exchange.place_order(order)
            latency_ms = int((time.perf_counter() - start) * 1000)
            result.latency_ms = latency_ms
            if result.status in {"filled", "partial"}:
                self.health.register_success()
                self.health.last_latency_ms = latency_ms
                return result
            self.health.register_failure(
                self.config.max_consecutive_failures,
                self.config.circuit_breaker_timeout_sec,
            )
            if attempts <= self.config.max_retries:
                time.sleep(self.config.retry_backoff_sec * attempts)
        return result

    def _fallback_limit(self, order: Order, snapshot: MarketSnapshot) -> ExecutionResult:
        offset = self.config.limit_price_offset_bps / 10_000
        if order.side == "buy":
            limit_price = (order.expected_price or snapshot.mid) * (1 + offset)
        else:
            limit_price = (order.expected_price or snapshot.mid) * (1 - offset)
        limit_order = Order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type="limit",
            limit_price=limit_price,
            expected_price=order.expected_price,
        )
        return self.exchange.place_order(limit_order)
