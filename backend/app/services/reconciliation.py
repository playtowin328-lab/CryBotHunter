from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import LogEntry, Order, OrderStatus
from app.services.exchange import ExchangeClient


class OrderReconciliationService:
    def __init__(self) -> None:
        self.exchange = ExchangeClient()

    async def reconcile(self, db: AsyncSession, stale_minutes: int = 5) -> dict[str, int]:
        orders = (
            await db.execute(
                select(Order)
                .where(Order.status.in_([OrderStatus.NEW.value, OrderStatus.FILLED.value]))
                .order_by(Order.created_at.desc())
                .limit(200)
            )
        ).scalars().all()
        checked = 0
        updated = 0
        failed = 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)

        for order in orders:
            checked += 1
            if order.status == OrderStatus.NEW.value and order.created_at < cutoff:
                order.status = OrderStatus.FAILED.value
                order.raw = {**(order.raw or {}), "reconciliation": "stale_new_order"}
                db.add(LogEntry(level="ERROR", message=f"Order #{order.id} marked failed during reconciliation"))
                failed += 1
                updated += 1
                continue

            if not order.exchange_order_id or order.exchange_order_id.startswith("paper-"):
                continue

            try:
                raw = await self.exchange.fetch_order(order.exchange_order_id, order.symbol)
            except Exception as exc:
                order.raw = {**(order.raw or {}), "reconciliation_error": exc.__class__.__name__}
                continue

            mapped = self._map_status(str(raw.get("status", "")).lower())
            if mapped and mapped != order.status:
                order.status = mapped
                updated += 1
            if raw.get("filled") is not None:
                order.filled_amount = float(raw.get("filled") or 0)
            if raw.get("average") is not None:
                order.average_price = float(raw.get("average") or 0)
            order.raw = {**(order.raw or {}), "exchange_snapshot": raw}

        await db.commit()
        return {"checked": checked, "updated": updated, "failed": failed}

    def _map_status(self, status: str) -> str | None:
        if status in {"closed", "filled"}:
            return OrderStatus.FILLED.value
        if status in {"canceled", "cancelled"}:
            return OrderStatus.CANCELLED.value
        if status in {"rejected", "expired", "failed"}:
            return OrderStatus.FAILED.value
        if status in {"open", "new"}:
            return OrderStatus.NEW.value
        return None
