import pytest

from app.services.execution import ExecutionService
from app.services.exchange import PreparedOrder


class Db:
    def add(self, _obj):
        return None

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_paper_execution_fills_order_with_fee_and_slippage():
    order = await ExecutionService().execute_market(
        Db(),
        symbol="BTC/USDT",
        side="buy",
        amount=2,
        reference_price=100,
        reason="TEST",
    )
    assert order.status == "FILLED"
    assert order.average_price > 100
    assert order.fee > 0
    assert order.slippage > 0


class LowBalanceExchange:
    async def prepare_order(self, symbol, amount, reference_price):
        return PreparedOrder(amount=amount, fee_rate=0.001, min_amount=None, min_cost=None, metadata_available=False)

    async def get_free_balance(self):
        return {"USDT": 50.0}

    async def create_order(self, *args, **kwargs):
        raise AssertionError("create_order should not be called when balance is insufficient")


@pytest.mark.asyncio
async def test_live_execution_blocks_entry_when_free_balance_is_too_low(monkeypatch):
    service = ExecutionService(LowBalanceExchange())
    monkeypatch.setattr(service.settings, "paper_trading", False)

    order = await service.execute_market(
        Db(),
        symbol="BTC/USDT",
        side="buy",
        amount=1,
        reference_price=100,
        reason="ENTRY",
    )

    assert order.status == "FAILED"
    assert order.raw["error"] == "RuntimeError"
    assert "Insufficient free USDT balance" in order.raw["message"]
