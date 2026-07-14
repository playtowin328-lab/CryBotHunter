import ast
from pathlib import Path

import ccxt
import pytest

from app.safety_manager import SafetyManager, ShutdownController


SAFETY_ENVIRONMENT = (
    "APP_PROCESS",
    "DEFAULT_EXCHANGE",
    "EXCHANGE_DEFAULT_TYPE",
    "PAPER_TRADING",
    "LIVE_TRADING",
    "LIVE_TRADING_ENABLED",
    "EXCHANGE_SANDBOX_ENABLED",
    "API_KEY",
    "API_SECRET",
    "EXCHANGE_API_KEY",
    "EXCHANGE_SECRET_KEY",
    "SAFETY_CHECK_ENABLED",
    "SAFETY_REQUIRE_API_CREDENTIALS",
    "SAFETY_VALIDATE_PRIVATE_API",
    "SAFETY_RETRY_ATTEMPTS",
    "SAFETY_RETRY_INITIAL_SECONDS",
    "SAFETY_RETRY_MAX_SECONDS",
)


class FakeExchange:
    def __init__(self, fail_time_attempts: int = 0, ticker: dict | None = None) -> None:
        self.fail_time_attempts = fail_time_attempts
        self.ticker = ticker or {"symbol": "BTC/USDT", "last": 65_000.0, "timestamp": 1_750_000_000_000}
        self.time_calls = 0
        self.balance_calls = 0
        self.close_calls = 0

    def fetch_time(self) -> int:
        self.time_calls += 1
        if self.time_calls <= self.fail_time_attempts:
            raise ccxt.NetworkError("temporary network failure")
        return 1_750_000_000_000

    def fetch_ticker(self, _symbol: str) -> dict:
        return self.ticker

    def fetch_balance(self) -> dict:
        self.balance_calls += 1
        return {"total": {"USDT": 100.0, "BTC": None}}

    def close(self) -> None:
        self.close_calls += 1


def clear_safety_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SAFETY_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_paper_preflight_checks_public_real_market_without_credentials(monkeypatch):
    clear_safety_environment(monkeypatch)
    fake = FakeExchange()

    report = await SafetyManager(exchange_factory=lambda _config: fake).run()

    assert report.ok is True
    assert report.mode == "PAPER"
    assert report.last_price == 65_000.0
    assert report.private_api_checked is False
    assert fake.balance_calls == 0
    assert fake.close_calls == 1


@pytest.mark.asyncio
async def test_live_preflight_exits_when_credentials_are_missing(monkeypatch):
    clear_safety_environment(monkeypatch)
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")

    with pytest.raises(SystemExit) as exc_info:
        await SafetyManager(exchange_factory=lambda _config: FakeExchange()).run_or_exit()

    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_live_preflight_validates_private_balance(monkeypatch):
    clear_safety_environment(monkeypatch)
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("API_SECRET", "test-secret")
    fake = FakeExchange()

    report = await SafetyManager(exchange_factory=lambda _config: fake).run()

    assert report.mode == "LIVE"
    assert report.private_api_checked is True
    assert fake.balance_calls == 1


@pytest.mark.asyncio
async def test_network_failure_retries_with_backoff(monkeypatch):
    clear_safety_environment(monkeypatch)
    monkeypatch.setenv("SAFETY_RETRY_ATTEMPTS", "3")
    monkeypatch.setenv("SAFETY_RETRY_INITIAL_SECONDS", "0.25")
    fake = FakeExchange(fail_time_attempts=2)
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    report = await SafetyManager(exchange_factory=lambda _config: fake, sleep=record_sleep).run()

    assert report.ok is True
    assert fake.time_calls == 3
    assert fake.close_calls == 3
    assert sleeps == [0.25, 0.5]


@pytest.mark.asyncio
async def test_invalid_exchange_payload_stops_worker(monkeypatch):
    clear_safety_environment(monkeypatch)
    fake = FakeExchange(ticker={"symbol": "BTC/USDT", "last": 0})

    with pytest.raises(SystemExit) as exc_info:
        await SafetyManager(exchange_factory=lambda _config: fake).run_or_exit()

    assert exc_info.value.code == 1
    assert fake.close_calls == 1


@pytest.mark.asyncio
async def test_shutdown_controller_wakes_waiter():
    shutdown = ShutdownController()

    shutdown.request("test")

    assert shutdown.requested is True
    assert await shutdown.wait(30) is True


def test_rl_worker_does_not_import_stable_baselines_service_at_module_load():
    worker_path = Path(__file__).parents[1] / "app" / "rl_worker.py"
    module = ast.parse(worker_path.read_text(encoding="utf-8"))
    top_level_imports = [
        alias.name
        for node in module.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]

    assert "RlTrainingService" not in top_level_imports


def test_stable_baselines_callback_stops_immediately_after_shutdown_flag():
    pytest.importorskip("stable_baselines3")
    from app.services.rl_training import ShutdownCallback

    shutdown = ShutdownController()
    callback = ShutdownCallback(lambda: shutdown.requested)

    shutdown.request("test")

    assert callback._on_step() is False
