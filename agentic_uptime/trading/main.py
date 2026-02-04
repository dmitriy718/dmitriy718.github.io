from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..logging_setup import setup_logging
from .backtest import Backtester, BacktestConfig
from .config import load_trading_config, resolve_exchange_secrets
from .execution import ExecutionConfig, ExecutionEngine
from .exchanges.binance_us import BinanceUSClient, BinanceUSConfig
from .exchanges.paper import PaperConfig, PaperExchangeClient
from .explainability import DecisionJournal
from .market_data import CSVMarketData, ExchangeMarketData, RollingVolatility
from .models import PortfolioState
from .risk import RiskEngine
from .slippage import SlippageGuard


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Trading Engine")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("trading_config.yml"),
        help="Trading config YAML",
    )
    args = parser.parse_args()
    config = load_trading_config(args.config)
    setup_logging(config.log_dir)

    if config.mode == "backtest":
        _run_backtest(config)
    elif config.mode in {"paper", "live"}:
        _run_live(config)
    else:
        raise SystemExit(f"Unsupported mode: {config.mode}")


def _run_backtest(config) -> None:
    if not config.market_data.csv_path:
        raise SystemExit("Backtest requires market_data.csv_path")
    data = CSVMarketData(
        path=config.market_data.csv_path,
        symbol=config.market_data.symbol,
        spread_bps=config.market_data.spread_bps,
        volatility_window=config.market_data.volatility_window,
    )
    strategy = config.strategy.to_strategy()
    backtest = Backtester(
        data=data,
        strategy=strategy,
        risk_policy=config.risk.to_policy(),
        execution_config=config.execution.to_execution(),
        backtest_config=BacktestConfig(
            starting_cash=config.starting_cash,
            journal_path=config.journal_path,
        ),
    )
    result = backtest.run()
    print("Backtest metrics:", result.metrics)
    if result.adjustments:
        print("Suggested adjustments:")
        for adj in result.adjustments:
            print(f"- {adj.param} -> {adj.value} ({adj.reason})")


def _run_live(config) -> None:
    strategy = config.strategy.to_strategy()
    risk_engine = RiskEngine(config.risk.to_policy())
    slippage_guard = config.slippage.to_guard()
    execution_config = config.execution.to_execution()
    journal = DecisionJournal(config.journal_path)
    volatility = RollingVolatility(window=config.market_data.volatility_window)

    market_data = None
    if config.exchange.type == "binance_us":
        api_key, api_secret = resolve_exchange_secrets(config.exchange)
        live_exchange = BinanceUSClient(
            BinanceUSConfig(
                api_key=api_key,
                api_secret=api_secret,
                base_url=config.exchange.base_url,
                cash_asset=config.exchange.cash_asset,
            )
        )
        market_data = ExchangeMarketData(live_exchange)
    else:
        if not config.market_data.csv_path:
            raise SystemExit("CSV market data required for non-binance exchange")
        market_data = CSVMarketData(
            path=config.market_data.csv_path,
            symbol=config.market_data.symbol,
            spread_bps=config.market_data.spread_bps,
            volatility_window=config.market_data.volatility_window,
        )
        live_exchange = None

    if config.mode == "live":
        if not live_exchange:
            raise SystemExit("Live mode requires binance_us exchange config")
        exchange = live_exchange
        portfolio = exchange.get_portfolio()
    else:
        portfolio = PortfolioState(cash=config.starting_cash)
        exchange = PaperExchangeClient(
            data_provider=market_data,
            portfolio=portfolio,
            config=PaperConfig(),
        )
    execution = ExecutionEngine(
        exchange=exchange,
        risk_engine=risk_engine,
        slippage_guard=slippage_guard,
        config=execution_config,
        journal=journal,
    )

    while True:
        snapshot = market_data.get_snapshot(config.market_data.symbol)
        snapshot.volatility = volatility.update(snapshot.last)
        signal = strategy.on_snapshot(snapshot, portfolio)
        if signal:
            execution.execute_signal(signal, snapshot, portfolio)
        time.sleep(config.poll_interval_sec)


if __name__ == "__main__":
    main()
