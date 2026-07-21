from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image

from app.models.entities import Position
from app.schemas.dto import TradingDecision, TradingRunOut, TradingTickOut
from app.services.telegram_cards import CARD_SIZE, render_cycle_card, render_position_card


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
        status="OPEN",
        entry_context={
            "paper_exploration": True,
            "notional": 200.0,
            "risk_reward_ratio": 3.0,
        },
        entered_at=datetime.now(timezone.utc) - timedelta(minutes=35),
    )


def assert_valid_card(payload: bytes) -> None:
    assert len(payload) > 30_000
    with Image.open(BytesIO(payload)) as image:
        assert image.format == "JPEG"
        assert image.size == CARD_SIZE
        assert image.mode == "RGB"


def test_position_card_is_rendered_as_telegram_ready_jpeg():
    payload = render_position_card(position(), event="OPENED", score=73)

    assert_valid_card(payload)


def test_cycle_card_is_rendered_as_telegram_ready_jpeg():
    run = TradingRunOut(
        scanned=5,
        opened=1,
        skipped=4,
        decisions=[
            TradingDecision(
                symbol="BTC/USDT",
                signal="BUY",
                score=73,
                action="OPENED",
                reason="risk accepted",
            )
        ],
    )
    tick = TradingTickOut(checked=3, closed=0, updated=[])

    payload = render_cycle_card(run, tick, paper_trading=True)

    assert_valid_card(payload)
