from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .models import MarketSnapshot


class MarketDataProvider:
    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        raise NotImplementedError


@dataclass
class StaticMarketData(MarketDataProvider):
    snapshot: MarketSnapshot

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        return self.snapshot


@dataclass
class ExchangeMarketData(MarketDataProvider):
    exchange: object

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        return self.exchange.get_snapshot(symbol)


@dataclass
class RollingVolatility:
    window: int = 20
    _prices: List[float] = None

    def __post_init__(self) -> None:
        self._prices = []

    def update(self, price: float) -> float:
        self._prices.append(price)
        if len(self._prices) < 2:
            return 0.0
        window_prices = self._prices[-self.window :]
        returns = []
        for idx in range(1, len(window_prices)):
            prev = window_prices[idx - 1]
            curr = window_prices[idx]
            returns.append((curr - prev) / prev if prev else 0.0)
        if not returns:
            return 0.0
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        return variance ** 0.5


@dataclass
class CSVMarketData(MarketDataProvider):
    path: Path
    symbol: str
    spread_bps: float = 10.0
    volatility_window: int = 20
    _rows: List[Dict[str, str]] = None
    _index: int = 0
    _prices: List[float] = None

    def __post_init__(self) -> None:
        self._rows = []
        self._prices = []
        with self.path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                self._rows.append(row)

    def iter_snapshots(self) -> Iterator[MarketSnapshot]:
        while self._index < len(self._rows):
            yield self.get_snapshot(self.symbol)

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        row = self._rows[self._index]
        self._index += 1
        last = float(row.get("close") or row.get("Close") or row.get("price") or 0.0)
        bid = last * (1 - self.spread_bps / 20_000)
        ask = last * (1 + self.spread_bps / 20_000)
        volatility = self._update_volatility(last)
        return MarketSnapshot(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volatility=volatility,
            timestamp=row.get("timestamp") or row.get("time") or "",
        )

    def _update_volatility(self, price: float) -> float:
        if self._prices:
            last_price = self._prices[-1]
            _ = (price - last_price) / last_price if last_price else 0.0
            self._prices.append(price)
        else:
            self._prices.append(price)
        if len(self._prices) < 2:
            return 0.0
        window_prices = self._prices[-self.volatility_window :]
        returns = []
        for idx in range(1, len(window_prices)):
            prev = window_prices[idx - 1]
            curr = window_prices[idx]
            returns.append((curr - prev) / prev if prev else 0.0)
        if not returns:
            return 0.0
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
