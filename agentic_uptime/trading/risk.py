from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .models import MarketSnapshot, Order, PortfolioState, Position, utc_now


@dataclass
class RiskPolicy:
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


@dataclass
class RiskDecision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    adjusted_qty: Optional[float] = None


class RiskEngine:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def evaluate_order(
        self, order: Order, snapshot: MarketSnapshot, portfolio: PortfolioState
    ) -> RiskDecision:
        reasons: List[str] = []
        expected_price = order.expected_price or snapshot.last or snapshot.mid
        if expected_price <= 0:
            reasons.append("invalid_price")
            return RiskDecision(False, reasons)

        if snapshot.spread_bps > self.policy.max_spread_bps:
            reasons.append("spread_too_wide")

        if snapshot.volatility > self.policy.max_volatility:
            reasons.append("volatility_too_high")

        if order.quantity <= 0:
            reasons.append("invalid_quantity")

        if order.quantity > self.policy.max_order_qty:
            reasons.append("order_qty_exceeds_limit")

        notional = order.quantity * expected_price
        if notional > self.policy.max_notional_per_trade:
            reasons.append("notional_exceeds_limit")

        equity = self._compute_equity(snapshot, portfolio)
        if equity <= 0:
            reasons.append("invalid_equity")
            return RiskDecision(False, reasons)

        if portfolio.peak_equity <= 0:
            portfolio.peak_equity = equity
        drawdown = (portfolio.peak_equity - equity) / portfolio.peak_equity
        if drawdown > self.policy.max_drawdown_pct:
            reasons.append("max_drawdown_exceeded")

        if portfolio.daily_pnl < -self.policy.max_daily_loss:
            reasons.append("daily_loss_limit_exceeded")

        if order.side == "buy":
            if not self._has_cash(portfolio, notional, equity):
                reasons.append("insufficient_cash")
        elif order.side == "sell" and not self.policy.allow_short:
            position = portfolio.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                reasons.append("insufficient_position")

        new_position_qty = self._project_position_qty(order, portfolio)
        if abs(new_position_qty) > 0:
            position_value = abs(new_position_qty * expected_price)
            if position_value / equity > self.policy.max_position_pct:
                reasons.append("position_exceeds_limit")
            if (
                order.symbol not in portfolio.positions
                and len(portfolio.positions) + 1 > self.policy.max_open_positions
            ):
                reasons.append("max_open_positions_exceeded")

        exposure = self._project_total_exposure(order, portfolio, expected_price)
        if exposure / equity > self.policy.max_exposure_pct:
            reasons.append("portfolio_exposure_exceeds_limit")

        remaining_cash = (
            portfolio.cash - notional if order.side == "buy" else portfolio.cash + notional
        )
        if remaining_cash / equity < self.policy.min_cash_pct:
            reasons.append("min_cash_buffer_breached")

        return RiskDecision(allowed=not reasons, reasons=reasons)

    def update_after_fill(
        self,
        portfolio: PortfolioState,
        order: Order,
        fill_price: float,
        fill_qty: float,
    ) -> PortfolioState:
        position = portfolio.positions.get(order.symbol)
        if order.side == "buy":
            cost = fill_price * fill_qty
            portfolio.cash -= cost
            if position:
                total_qty = position.quantity + fill_qty
                position.avg_price = (
                    position.avg_price * position.quantity + fill_price * fill_qty
                ) / total_qty
                position.quantity = total_qty
            else:
                portfolio.positions[order.symbol] = Position(
                    symbol=order.symbol, quantity=fill_qty, avg_price=fill_price
                )
        else:
            proceeds = fill_price * fill_qty
            portfolio.cash += proceeds
            if position:
                position.quantity -= fill_qty
                if position.quantity <= 0:
                    portfolio.positions.pop(order.symbol, None)
        portfolio.equity = self._compute_equity_from_prices(portfolio, order.symbol, fill_price)
        portfolio.peak_equity = max(portfolio.peak_equity, portfolio.equity)
        portfolio.timestamp = utc_now()
        return portfolio

    def _has_cash(self, portfolio: PortfolioState, notional: float, equity: float) -> bool:
        return portfolio.cash - notional >= equity * self.policy.min_cash_pct

    def _project_position_qty(self, order: Order, portfolio: PortfolioState) -> float:
        current = portfolio.positions.get(order.symbol)
        qty = current.quantity if current else 0.0
        return qty + order.quantity if order.side == "buy" else qty - order.quantity

    def _project_total_exposure(
        self, order: Order, portfolio: PortfolioState, price: float
    ) -> float:
        exposure = 0.0
        for position in portfolio.positions.values():
            current_qty = position.quantity
            if position.symbol == order.symbol:
                current_qty = self._project_position_qty(order, portfolio)
                exposure += abs(current_qty * price)
            else:
                exposure += abs(current_qty * position.avg_price)
        return exposure

    def _compute_equity(self, snapshot: MarketSnapshot, portfolio: PortfolioState) -> float:
        equity = portfolio.cash
        for position in portfolio.positions.values():
            price = snapshot.last if position.symbol == snapshot.symbol else position.avg_price
            equity += position.quantity * price
        portfolio.equity = equity
        return equity

    def _compute_equity_from_prices(
        self, portfolio: PortfolioState, symbol: str, price: float
    ) -> float:
        equity = portfolio.cash
        for position in portfolio.positions.values():
            current_price = price if position.symbol == symbol else position.avg_price
            equity += position.quantity * current_price
        portfolio.equity = equity
        return equity
