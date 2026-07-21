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
        telegram_outbox_enabled=False,
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

    class Heartbeat:
        async def start(self):
            return None

        async def set_status(self, *_args, **_kwargs):
            return None

        async def stop(self):
            return None

    async def maintenance():
        return None

    bot.heartbeat = Heartbeat()
    monkeypatch.setattr(bot, "_get_updates", conflict)
    monkeypatch.setattr(bot, "_maintenance", maintenance)
    monkeypatch.setattr("app.services.telegram_bot.asyncio.sleep", stop_after_log)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(asyncio.CancelledError):
            await bot.run(session_factory=None)

    output = caplog.text
    assert "another poller is active" in output
    assert "super-secret-token" not in output
    assert "api.telegram.org" not in output


@pytest.mark.asyncio
async def test_outbox_retry_does_not_duplicate_already_delivered_text():
    item = SimpleNamespace(
        id=7,
        chat_id=12345,
        text="trade report",
        parse_mode="HTML",
        photo=b"jpeg-bytes",
        photo_filename="position-7.jpg",
        photo_caption="card",
        text_sent=False,
        photo_sent=False,
    )

    class Outbox:
        def __init__(self):
            self.failed = 0
            self.delivered = 0

        async def claim(self, **_kwargs):
            return [item]

        async def mark_progress(self, _message_id, *, text_sent=False, photo_sent=False):
            item.text_sent = item.text_sent or text_sent
            item.photo_sent = item.photo_sent or photo_sent

        async def mark_failed(self, _message_id, _error_type):
            self.failed += 1

        async def mark_delivered(self, _message_id):
            self.delivered += 1

    notifier = TelegramNotifier()
    notifier.settings = SimpleNamespace(
        telegram_bot_token="test-token",
        telegram_outbox_enabled=True,
    )
    notifier.outbox = Outbox()
    sent = {"text": 0, "photo": 0}

    async def send_message(*_args, **_kwargs):
        sent["text"] += 1
        return True

    async def send_photo(*_args, **_kwargs):
        sent["photo"] += 1
        return sent["photo"] > 1

    notifier.send_message = send_message
    notifier.send_photo = send_photo

    assert await notifier.flush_outbox() == 0
    assert await notifier.flush_outbox() == 1
    assert sent == {"text": 1, "photo": 2}
    assert notifier.outbox.failed == 1
    assert notifier.outbox.delivered == 1
