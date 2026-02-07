from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .execution import ExecutionConfig, ExecutionEngine
from .exchanges.paper import PaperConfig, PaperExchangeClient
from .explainability import (
    DecisionJournal,
    LearningLoop,
    ParameterAdjustment,
    PostTradeAnalyzer,
    TradeMetrics,
)
from .market_data import CSVMarketData
from .models import PortfolioState, TradeDecision
from .risk import RiskEngine, RiskPolicy
from .slippage import SlippageGuard
from .strategy import Strategy


@dataclass
class BacktestConfig:
    starting_cash: float = 10_000.0
    journal_path: Path = Path("logs/backtest_journal.jsonl")
    slippage_bps: float = 5.0
    fee_bps: float = 2.0


@dataclass
class BacktestResult:
    metrics: TradeMetrics
    decisions: List[TradeDecision]
    adjustments: List[ParameterAdjustment]


class Backtester:
    def __init__(
        self,
        data: CSVMarketData,
        strategy: Strategy,
        risk_policy: Optional[RiskPolicy] = None,
        execution_config: Optional[ExecutionConfig] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> None:
        self.data = data
        self.strategy = strategy
        self.risk_engine = RiskEngine(risk_policy or RiskPolicy())
        self.backtest_config = backtest_config or BacktestConfig()
        self.execution_config = execution_config or ExecutionConfig()
        self.portfolio = PortfolioState(cash=self.backtest_config.starting_cash)
        self.journal = DecisionJournal(self.backtest_config.journal_path)
        self.exchange = PaperExchangeClient(
            data_provider=data,
            portfolio=self.portfolio,
            risk_engine=self.risk_engine,
            config=PaperConfig(
                slippage_bps=self.backtest_config.slippage_bps,
                fee_bps=self.backtest_config.fee_bps,
            ),
        )
        self.execution = ExecutionEngine(
            exchange=self.exchange,
            risk_engine=self.risk_engine,
            slippage_guard=SlippageGuard(),
            config=self.execution_config,
            journal=self.journal,
        )

    def run(self) -> BacktestResult:
        decisions: List[TradeDecision] = []
        for snapshot in self.data.iter_snapshots():
            signal = self.strategy.on_snapshot(snapshot, self.portfolio)
            if not signal:
                continue
            decision = self.execution.execute_signal(signal, snapshot, self.portfolio)
            decisions.append(decision)
        analyzer = PostTradeAnalyzer()
        metrics = analyzer.analyze(decisions)
        adjustments = LearningLoop().propose_adjustments(metrics)
        return BacktestResult(metrics=metrics, decisions=decisions, adjustments=adjustments)
