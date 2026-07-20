from datetime import datetime, timedelta, timezone

from app.models.entities import Position
from app.schemas.dto import PositionUpdateOut, TradingDecision, TradingRunOut, TradingTickOut
from app.services.telegram_reports import (
    format_cycle_report,
    format_trade_closed,
    format_trade_opened,
    split_telegram_message,
)


def position() -> Position:
    return Position(
        id=42,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=100,
        current_price=104,
        volume=2,
        stop=98,
        take=106,
        initial_risk=2,
        trailing_stop_percent=0.8,
        pnl=8,
        entry_context={"paper_exploration": True},
        entered_at=datetime.now(timezone.utc) - timedelta(minutes=35),
        closed_at=datetime.now(timezone.utc),
    )


def test_open_report_explains_test_entry_and_risk_plan():
    report = format_trade_opened(
        position(),
        score=73,
        reason="risk accepted; paper exploration from WAIT",
        paper_trading=True,
        exploration=True,
    )

    assert "ОТКРЫТА ТЕСТОВАЯ ПОЗИЦИЯ" in report
    assert "BTC/USDT" in report
    assert "плановый риск" in report
    assert "строгий сигнал был WAIT" in report
    assert "Что дальше" in report


def test_close_report_explains_outcome_and_learning():
    report = format_trade_closed(position(), exit_price=104, reason="TAKE_PROFIT")

    assert "ПОЗИЦИЯ ЗАКРЫТА" in report
    assert "достигнут тейк-профит" in report
    assert "Итог: +8.00 USDT" in report
    assert "Обучение:" in report


def test_cycle_report_contains_every_decision_and_position_update():
    run = TradingRunOut(
        scanned=2,
        opened=1,
        skipped=1,
        decisions=[
            TradingDecision(symbol="BTC/USDT", signal="BUY", score=73, action="OPENED", reason="paper exploration from WAIT"),
            TradingDecision(symbol="ETH/USDT", signal="WAIT", score=61, action="SKIPPED", reason="strategy returned WAIT"),
        ],
    )
    tick = TradingTickOut(
        checked=1,
        closed=0,
        updated=[
            PositionUpdateOut(
                id=42,
                symbol="BTC/USDT",
                side="LONG",
                entry_price=100,
                previous_price=103,
                current_price=104,
                volume=2,
                pnl=8,
                status="OPEN",
                stop=98,
                take=106,
            )
        ],
    )

    report = format_cycle_report(run, tick, paper_trading=True)

    assert "BTC/USDT" in report
    assert "ETH/USDT" in report
    assert "строгий торговый сигнал ещё не сформирован" in report
    assert "PnL +8.00 USDT" in report


def test_long_telegram_report_is_split_without_data_loss():
    text = "\n".join(f"строка {index}: " + "x" * 60 for index in range(200))
    chunks = split_telegram_message(text, limit=500)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert "строка 199" in chunks[-1]
