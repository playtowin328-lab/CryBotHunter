from types import SimpleNamespace

import pytest

from app.services.telegram_bot import TelegramNotifier


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
