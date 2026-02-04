from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from ..utils.env import get_env
from .execution import ExecutionConfig
from .risk import RiskPolicy
from .slippage import SlippageGuard
from .strategy import MovingAverageCrossStrategy, Strategy


class TradingRiskConfig(BaseModel):
    max_position_pct: float = 0.2
    max_notional_per_trade: float = 10_000.0
    max_daily_loss: float = 1_000.0
    max_drawdown_pct: float = 0.2
    max_volatility: float = 0.08
    max_order_qty: float = 1_000.0
    max_open_positions: int = 10
    max_exposure_pct: float = 0.8
    min_cash_pct: float = 0.1
    allow_short: bool = False
    max_spread_bps: float = 50.0

    def to_policy(self) -> RiskPolicy:
        return RiskPolicy(**self.model_dump())


class TradingExecutionConfig(BaseModel):
    max_retries: int = 2
    retry_backoff_sec: float = 0.5
    max_consecutive_failures: int = 3
    circuit_breaker_timeout_sec: int = 60
    fallback_to_limit: bool = True
    limit_price_offset_bps: float = 10.0
    max_latency_ms: int = 2_000

    def to_execution(self) -> ExecutionConfig:
        return ExecutionConfig(**self.model_dump())


class TradingSlippageConfig(BaseModel):
    max_slippage_bps: float = 50.0
    max_price_impact_bps: float = 75.0

    def to_guard(self) -> SlippageGuard:
        return SlippageGuard(**self.model_dump())


class TradingStrategyConfig(BaseModel):
    type: Literal["ma_cross"] = "ma_cross"
    symbol: str = "BTCUSD"
    short_window: int = 5
    long_window: int = 20
    order_size: float = 0.01

    def to_strategy(self) -> Strategy:
        if self.type == "ma_cross":
            return MovingAverageCrossStrategy(
                symbol=self.symbol,
                short_window=self.short_window,
                long_window=self.long_window,
                order_size=self.order_size,
            )
        raise ValueError(f"Unsupported strategy type: {self.type}")


class TradingMarketDataConfig(BaseModel):
    type: Literal["csv"] = "csv"
    symbol: str = "BTCUSD"
    csv_path: Optional[Path] = None
    spread_bps: float = 10.0
    volatility_window: int = 20


class TradingExchangeConfig(BaseModel):
    type: Literal["paper", "binance_us"] = "paper"
    api_key_env: str = "BINANCE_US_API_KEY"
    api_secret_env: str = "BINANCE_US_API_SECRET"
    base_url: str = "https://api.binance.us"
    cash_asset: str = "USD"


class TradingConfig(BaseModel):
    mode: Literal["backtest", "paper", "live"] = "backtest"
    log_dir: Path = Path("logs")
    journal_path: Path = Path("logs/trading_journal.jsonl")
    starting_cash: float = 10_000.0
    poll_interval_sec: int = 5
    risk: TradingRiskConfig = Field(default_factory=TradingRiskConfig)
    execution: TradingExecutionConfig = Field(default_factory=TradingExecutionConfig)
    slippage: TradingSlippageConfig = Field(default_factory=TradingSlippageConfig)
    strategy: TradingStrategyConfig = Field(default_factory=TradingStrategyConfig)
    market_data: TradingMarketDataConfig = Field(default_factory=TradingMarketDataConfig)
    exchange: TradingExchangeConfig = Field(default_factory=TradingExchangeConfig)


def load_trading_config(path: Path) -> TradingConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    try:
        config = TradingConfig(**raw)
    except ValidationError as exc:
        details = exc.errors(include_url=False, include_context=False)
        raise SystemExit(f"Trading config validation failed: {details}") from exc
    base_dir = path.parent
    config.log_dir = _resolve_path(base_dir, config.log_dir)
    config.journal_path = _resolve_path(base_dir, config.journal_path)
    if config.market_data.csv_path:
        config.market_data.csv_path = _resolve_path(base_dir, config.market_data.csv_path)
    return config


def resolve_exchange_secrets(config: TradingExchangeConfig) -> tuple[str, str]:
    api_key = get_env(config.api_key_env, required=True)
    api_secret = get_env(config.api_secret_env, required=True)
    return api_key, api_secret


def _resolve_path(base_dir: Path, path: Path) -> Path:
    return path if path.is_absolute() else base_dir / path
