import pytest

from app.services.exchange import ExchangeClient
from app.services.execution import ExecutionService


def test_exchange_blocks_live_without_sandbox_by_default(monkeypatch):
    client = ExchangeClient()
    monkeypatch.setattr(client.settings, "exchange_sandbox_enabled", False)
    monkeypatch.setattr(client.settings, "allow_live_trading_without_sandbox", False)

    with pytest.raises(RuntimeError):
        client._assert_live_safety()


def test_exchange_allows_live_with_sandbox(monkeypatch):
    client = ExchangeClient()
    monkeypatch.setattr(client.settings, "exchange_sandbox_enabled", True)
    monkeypatch.setattr(client.settings, "allow_live_trading_without_sandbox", False)

    client._assert_live_safety()


def test_exchange_order_params_include_client_id_and_reduce_only():
    client = ExchangeClient(exchange="bybit")
    params = client._order_params(client_order_id="cbh-1-exit", reduce_only=True)

    assert params["clientOrderId"] == "cbh-1-exit"
    assert params["orderLinkId"] == "cbh-1-exit"
    assert params["reduceOnly"] is True


def test_execution_client_order_id_is_stable_and_safe():
    client_order_id = ExecutionService()._client_order_id(42, "EXIT_TAKE_PROFIT")

    assert client_order_id == "cbh-42-exit_take_profit"
