from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from ..models import ExecutionResult, Fill, MarketSnapshot, Order, PortfolioState


@dataclass
class BinanceUSConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://api.binance.us"
    recv_window: int = 5_000
    cash_asset: str = "USD"


class BinanceUSClient:
    def __init__(self, config: BinanceUSConfig) -> None:
        self.config = config

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        book = self._public_get("/api/v3/ticker/bookTicker", {"symbol": symbol})
        price = self._public_get("/api/v3/ticker/price", {"symbol": symbol})
        bid = float(book["bidPrice"])
        ask = float(book["askPrice"])
        last = float(price["price"])
        return MarketSnapshot(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volatility=0.0,
        )

    def get_account(self) -> Dict[str, float]:
        account = self._signed_get("/api/v3/account")
        balances = {b["asset"]: float(b["free"]) for b in account.get("balances", [])}
        return balances

    def get_portfolio(self) -> PortfolioState:
        balances = self.get_account()
        cash = balances.get(self.config.cash_asset, 0.0)
        return PortfolioState(cash=cash)

    def place_order(self, order: Order) -> ExecutionResult:
        params = {
            "symbol": order.symbol,
            "side": order.side.upper(),
            "type": order.order_type.upper(),
            "quantity": self._format_qty(order.quantity),
        }
        if order.order_type == "limit":
            if not order.limit_price:
                return ExecutionResult(
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    message="limit_price_required",
                )
            params["price"] = self._format_price(order.limit_price)
            params["timeInForce"] = order.time_in_force
        response = self._signed_post("/api/v3/order", params)
        status = response.get("status", "").upper()
        executed_qty = float(response.get("executedQty", 0))
        fills: List[Fill] = []
        total_quote = 0.0
        if response.get("fills"):
            for fill in response["fills"]:
                price = float(fill["price"])
                qty = float(fill["qty"])
                fee = float(fill.get("commission", 0))
                fills.append(Fill(price=price, quantity=qty, fee=fee))
                total_quote += price * qty
        avg_price = total_quote / executed_qty if executed_qty else 0.0
        mapped_status = self._map_status(status)
        return ExecutionResult(
            status=mapped_status,
            filled_qty=executed_qty,
            avg_price=avg_price,
            message=status or "order_submitted",
            fills=fills,
        )

    def _public_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict:
        url = f"{self.config.base_url}{path}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def _signed_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict:
        return self._signed_request("GET", path, params or {})

    def _signed_post(self, path: str, params: Dict[str, str]) -> Dict:
        return self._signed_request("POST", path, params)

    def _signed_request(self, method: str, path: str, params: Dict[str, str]) -> Dict:
        params = params.copy()
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.config.recv_window
        query = self._encode_params(params)
        signature = hmac.new(
            self.config.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        headers = {"X-MBX-APIKEY": self.config.api_key}
        url = f"{self.config.base_url}{path}"
        response = requests.request(method, url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _encode_params(params: Dict[str, str]) -> str:
        return urllib.parse.urlencode({k: params[k] for k in sorted(params.keys())})

    @staticmethod
    def _map_status(status: str) -> str:
        if status == "FILLED":
            return "filled"
        if status == "PARTIALLY_FILLED":
            return "partial"
        if status in {"REJECTED", "EXPIRED"}:
            return "rejected"
        return "new"

    @staticmethod
    def _format_qty(qty: float) -> str:
        return f"{qty:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_price(price: float) -> str:
        return f"{price:.8f}".rstrip("0").rstrip(".")
