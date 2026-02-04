import json
from pathlib import Path

import pytest

from agentic_uptime.trading.advisor import TradingLLMAdvisor
from agentic_uptime.trading.backtest import Backtester, BacktestConfig
from agentic_uptime.trading.execution import ExecutionConfig, ExecutionEngine
from agentic_uptime.trading.explainability import DecisionJournal
from agentic_uptime.trading.market_data import CSVMarketData
from agentic_uptime.trading.models import ExecutionResult, MarketSnapshot, Order, PortfolioState, TradeSignal
from agentic_uptime.trading.risk import RiskEngine, RiskPolicy
from agentic_uptime.trading.slippage import SlippageGuard
from agentic_uptime.trading.strategy import MovingAverageCrossStrategy


def test_risk_engine_rejects_high_risk() -> None:
    policy = RiskPolicy(
        max_notional_per_trade=100,
        max_volatility=0.01,
        max_spread_bps=5,
    )
    engine = RiskEngine(policy)
    portfolio = PortfolioState(cash=1000)
    snapshot = MarketSnapshot(
        symbol="BTCUSD", bid=100, ask=110, last=105, volatility=0.05
    )
    order = Order(
        symbol="BTCUSD",
        side="buy",
        quantity=2,
        order_type="market",
        expected_price=105,
    )
    decision = engine.evaluate_order(order, snapshot, portfolio)
    assert decision.allowed is False
    assert "notional_exceeds_limit" in decision.reasons
    assert "volatility_too_high" in decision.reasons
    assert "spread_too_wide" in decision.reasons


def test_slippage_guard_blocks() -> None:
    guard = SlippageGuard(max_slippage_bps=5)
    snapshot = MarketSnapshot(
        symbol="BTCUSD", bid=100, ask=101, last=100.5, volatility=0.0
    )
    decision = guard.evaluate(100, 100.2, "buy", snapshot)
    assert decision.allowed is False
    assert decision.reason == "slippage_exceeded"


def test_execution_engine_fallback_to_limit() -> None:
    class DummyExchange:
        def __init__(self):
            self.orders = []

        def place_order(self, order):
            self.orders.append(order)
            if order.order_type == "market":
                return ExecutionResult(
                    status="filled",
                    filled_qty=1,
                    avg_price=110,
                    message="slip",
                )
            return ExecutionResult(
                status="filled",
                filled_qty=1,
                avg_price=order.limit_price or 0,
                message="limit",
            )

        def get_snapshot(self, symbol):
            return MarketSnapshot(symbol=symbol, bid=100, ask=101, last=100.5, volatility=0.0)

        def get_account(self):
            return {"cash": 1000.0}

        def get_portfolio(self):
            return PortfolioState(cash=1000.0)

    exchange = DummyExchange()
    engine = ExecutionEngine(
        exchange=exchange,
        risk_engine=RiskEngine(RiskPolicy()),
        slippage_guard=SlippageGuard(max_slippage_bps=5),
        config=ExecutionConfig(limit_price_offset_bps=10),
    )
    portfolio = PortfolioState(cash=1000)
    snapshot = exchange.get_snapshot("BTCUSD")
    signal = TradeSignal(symbol="BTCUSD", side="buy", quantity=1, confidence=0.7, expected_price=100)
    decision = engine.execute_signal(signal, snapshot, portfolio)
    assert decision.execution is not None
    assert exchange.orders[-1].order_type == "limit"
    assert decision.execution.avg_price == exchange.orders[-1].limit_price


def test_backtest_creates_journal(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "timestamp,close\n"
        + "\n".join(f"{i},{100 + i}" for i in range(30)),
        encoding="utf-8",
    )
    data = CSVMarketData(path=csv_path, symbol="BTCUSD", spread_bps=5, volatility_window=5)
    strategy = MovingAverageCrossStrategy(symbol="BTCUSD", short_window=2, long_window=3, order_size=0.1)
    journal = tmp_path / "journal.jsonl"
    backtest = Backtester(
        data=data,
        strategy=strategy,
        backtest_config=BacktestConfig(journal_path=journal),
    )
    result = backtest.run()
    assert journal.exists()
    assert result.metrics.total_trades >= 0


def test_llm_advisor_guard_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyLLM:
        def chat(self, _messages):
            return json.dumps(
                [{"param": "risk.max_notional_per_trade", "value": 99999, "reason": "increase"}]
            )

    advisor = TradingLLMAdvisor(DummyLLM(), RiskPolicy(max_notional_per_trade=1000))
    result = advisor.suggest("test")
    assert result.approved is False
    assert "increase_max_notional_denied" in result.blocked_reasons
