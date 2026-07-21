import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest

from app.services.telegram_bot import TelegramNotifier, TelegramPollingBot


@pytest.mark.asyncio
async def test_broadcast_sends_formatted_text_and_photo(monkeypatch):
    requests: list[tuple[str, dict]] = []

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    monkeypatch.setattr("app.services.telegram_bot.httpx.AsyncClient", Client)
    notifier = TelegramNotifier()
    notifier.settings = SimpleNamespace(
        telegram_bot_token="test-token",
        telegram_allowed_chat_ids=[12345],
    )
    notifier.base_url = "https://telegram.invalid/bottest-token"

    delivered = await notifier.broadcast(
        "<b>Красивый отчёт</b>",
        photo=b"jpeg-bytes",
        photo_filename="position-42.jpg",
        photo_caption="<b>Карточка сделки</b>",
    )

    assert delivered == 1
    assert requests[0][0].endswith("/sendMessage")
    assert requests[0][1]["json"]["parse_mode"] == "HTML"
    assert requests[1][0].endswith("/sendPhoto")
    assert requests[1][1]["data"]["caption"] == "<b>Карточка сделки</b>"
    assert requests[1][1]["files"]["photo"] == (
        "position-42.jpg",
        b"jpeg-bytes",
        "image/jpeg",
    )


@pytest.mark.asyncio
async def test_polling_conflict_log_does_not_expose_bot_token(monkeypatch, caplog):
    bot = TelegramPollingBot()
    bot.notifier.settings = SimpleNamespace(telegram_bot_token="super-secret-token")
    request = httpx.Request("GET", "https://api.telegram.org/botsuper-secret-token/getUpdates")
    response = httpx.Response(409, request=request)

    async def conflict():
        raise httpx.HTTPStatusError("conflict", request=request, response=response)

    async def stop_after_log(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(bot, "_get_updates", conflict)
    monkeypatch.setattr("app.services.telegram_bot.asyncio.sleep", stop_after_log)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(asyncio.CancelledError):
            await bot.run(session_factory=None)

    output = caplog.text
    assert "another poller is active" in output
    assert "super-secret-token" not in output
    assert "api.telegram.org" not in output
