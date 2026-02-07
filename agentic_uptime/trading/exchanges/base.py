from __future__ import annotations

from typing import Dict, Protocol

from ..models import ExecutionResult, MarketSnapshot, Order, PortfolioState


class ExchangeClient(Protocol):
    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        raise NotImplementedError

    def place_order(self, order: Order) -> ExecutionResult:
        raise NotImplementedError

    def get_account(self) -> Dict[str, float]:
        raise NotImplementedError

    def get_portfolio(self) -> PortfolioState:
        raise NotImplementedError
