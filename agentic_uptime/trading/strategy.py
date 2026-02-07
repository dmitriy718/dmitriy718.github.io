from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .models import MarketSnapshot, PortfolioState, TradeSignal


class Strategy:
    def on_snapshot(
        self, snapshot: MarketSnapshot, portfolio: PortfolioState
    ) -> Optional[TradeSignal]:
        raise NotImplementedError

    def reset(self) -> None:
        return None


@dataclass
class MovingAverageCrossStrategy(Strategy):
    symbol: str
    short_window: int = 5
    long_window: int = 20
    order_size: float = 0.01
    _prices: List[float] = field(default_factory=list)
    _last_signal: Optional[str] = None

    def on_snapshot(
        self, snapshot: MarketSnapshot, portfolio: PortfolioState
    ) -> Optional[TradeSignal]:
        if snapshot.symbol != self.symbol:
            return None
        self._prices.append(snapshot.last)
        if len(self._prices) < self.long_window:
            return None
        short_ma = sum(self._prices[-self.short_window :]) / self.short_window
        long_ma = sum(self._prices[-self.long_window :]) / self.long_window
        if short_ma > long_ma and self._last_signal != "buy":
            self._last_signal = "buy"
            return TradeSignal(
                symbol=self.symbol,
                side="buy",
                quantity=self.order_size,
                confidence=0.6,
                expected_price=snapshot.ask,
                reason_codes=["ma_cross_up"],
            )
        if short_ma < long_ma and self._last_signal != "sell":
            self._last_signal = "sell"
            return TradeSignal(
                symbol=self.symbol,
                side="sell",
                quantity=self.order_size,
                confidence=0.6,
                expected_price=snapshot.bid,
                reason_codes=["ma_cross_down"],
            )
        return None

    def reset(self) -> None:
        self._prices.clear()
        self._last_signal = None
