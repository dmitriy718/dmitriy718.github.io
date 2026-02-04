from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..models import ExecutionResult, Fill, MarketSnapshot, Order, PortfolioState
from ..market_data import MarketDataProvider
from ..risk import RiskEngine


@dataclass
class PaperConfig:
    slippage_bps: float = 5.0
    fee_bps: float = 2.0


class PaperExchangeClient:
    def __init__(
        self,
        data_provider: MarketDataProvider,
        portfolio: PortfolioState,
        risk_engine: Optional[RiskEngine] = None,
        config: Optional[PaperConfig] = None,
    ) -> None:
        self.data_provider = data_provider
        self.portfolio = portfolio
        self.risk_engine = risk_engine
        self.config = config or PaperConfig()

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        return self.data_provider.get_snapshot(symbol)

    def get_account(self) -> Dict[str, float]:
        return {"cash": self.portfolio.cash, "equity": self.portfolio.equity}

    def get_portfolio(self) -> PortfolioState:
        return self.portfolio

    def place_order(self, order: Order) -> ExecutionResult:
        snapshot = self.get_snapshot(order.symbol)
        price = snapshot.ask if order.side == "buy" else snapshot.bid
        slippage = self.config.slippage_bps / 10_000
        fee = self.config.fee_bps / 10_000
        if order.order_type == "limit" and order.limit_price:
            if order.side == "buy" and order.limit_price < snapshot.ask:
                return ExecutionResult(
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    message="limit_price_too_low",
                )
            if order.side == "sell" and order.limit_price > snapshot.bid:
                return ExecutionResult(
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    message="limit_price_too_high",
                )
            price = order.limit_price
        fill_price = price * (1 + slippage) if order.side == "buy" else price * (1 - slippage)
        fill_fee = fill_price * order.quantity * fee
        fill = Fill(price=fill_price, quantity=order.quantity, fee=fill_fee)
        return ExecutionResult(
            status="filled",
            filled_qty=order.quantity,
            avg_price=fill_price,
            message="paper_fill",
            fills=[fill],
        )
