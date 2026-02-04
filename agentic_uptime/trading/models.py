from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
OrderStatus = Literal["new", "filled", "partial", "rejected", "canceled"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    limit_price: Optional[float] = None
    time_in_force: str = "GTC"
    client_order_id: Optional[str] = None
    expected_price: Optional[float] = None


@dataclass
class Fill:
    price: float
    quantity: float
    fee: float = 0.0
    timestamp: str = field(default_factory=utc_now)


@dataclass
class ExecutionResult:
    status: OrderStatus
    filled_qty: float
    avg_price: float
    message: str
    latency_ms: Optional[int] = None
    fills: List[Fill] = field(default_factory=list)


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    equity: float = 0.0
    peak_equity: float = 0.0
    daily_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    timestamp: str = field(default_factory=utc_now)


@dataclass
class MarketSnapshot:
    symbol: str
    bid: float
    ask: float
    last: float
    volatility: float
    timestamp: str = field(default_factory=utc_now)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid and self.ask else self.last

    @property
    def spread_bps(self) -> float:
        if not self.bid or not self.ask:
            return 0.0
        return (self.ask - self.bid) / self.mid * 10_000


@dataclass
class TradeSignal:
    symbol: str
    side: OrderSide
    quantity: float
    confidence: float
    expected_price: Optional[float] = None
    reason_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TradeDecision:
    timestamp: str
    signal: TradeSignal
    risk_allowed: bool
    risk_reasons: List[str]
    execution: Optional[ExecutionResult] = None
    notes: Dict[str, str] = field(default_factory=dict)
