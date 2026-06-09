import pytest

from app.services.execution import ExecutionService


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
