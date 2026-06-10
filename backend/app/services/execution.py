from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Order, OrderStatus
from app.services.exchange import ExchangeClient


class ExecutionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.exchange = ExchangeClient()

    async def execute_market(
        self,
        db: AsyncSession,
        symbol: str,
        side: str,
        amount: float,
        reference_price: float,
        reason: str,
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=side,
            order_type="market",
            status=OrderStatus.NEW.value,
            requested_amount=amount,
            requested_price=reference_price,
            raw={"reason": reason},
        )
        db.add(order)
        await db.flush()
        try:
            if self.settings.paper_trading:
                self._fill_paper(order, reference_price)
            else:
                raw = await self.exchange.create_order(
                    symbol,
                    side,
                    amount,
                    "market",
                    client_order_id=self._client_order_id(order.id, reason),
                    reduce_only=reason.startswith("EXIT") or reason == "PARTIAL_TAKE_PROFIT",
                )
                order.exchange_order_id = str(raw.get("id") or "")
                order.status = OrderStatus.FILLED.value
                order.filled_amount = float(raw.get("filled") or amount)
                order.average_price = float(raw.get("average") or reference_price)
                order.fee = float((raw.get("fee") or {}).get("cost") or 0)
                order.raw = raw
        except Exception as exc:
            order.status = OrderStatus.FAILED.value
            order.raw = {"reason": reason, "error": exc.__class__.__name__}
        order.updated_at = datetime.now(timezone.utc)
        return order

    def _fill_paper(self, order: Order, reference_price: float) -> None:
        slippage_direction = 1 if order.side.lower() == "buy" else -1
        slippage = reference_price * (self.settings.paper_slippage_bps / 10_000) * slippage_direction
        average_price = reference_price + slippage
        notional = abs(average_price * order.requested_amount)
        order.exchange_order_id = f"paper-{order.id}"
        order.status = OrderStatus.FILLED.value
        order.filled_amount = order.requested_amount
        order.average_price = round(average_price, 8)
        order.slippage = round(abs(slippage), 8)
        order.fee = round(notional * self.settings.paper_fee_rate, 8)
        order.raw = {
            **(order.raw or {}),
            "paper": True,
            "fee_rate": self.settings.paper_fee_rate,
            "slippage_bps": self.settings.paper_slippage_bps,
        }

    def _client_order_id(self, order_id: int, reason: str) -> str:
        safe_reason = "".join(char for char in reason.lower() if char.isalnum() or char == "_")[:24]
        return f"cbh-{order_id}-{safe_reason}"
