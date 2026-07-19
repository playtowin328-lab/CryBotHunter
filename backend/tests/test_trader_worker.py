from types import SimpleNamespace

from app.trader_worker import _cycle_summary


def test_cycle_summary_makes_automatic_trade_attempt_visible():
    decisions = [
        SimpleNamespace(
            symbol="BTC/USDT",
            signal="BUY",
            action="OPENED",
            score=91,
            reason="risk accepted",
        ),
        SimpleNamespace(
            symbol="ETH/USDT",
            signal="WAIT",
            action="SKIPPED",
            score=72,
            reason="strategy returned WAIT",
        ),
    ]

    summary = _cycle_summary(scanned=2, opened=1, skipped=1, decisions=decisions, closed=1)

    assert "Auto-trade cycle scanned=2 opened=1 skipped=1 closed=1" in summary
    assert "learning_updates=1" in summary
    assert "BTC/USDT=BUY/OPENED(91)" in summary
