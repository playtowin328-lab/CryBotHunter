import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.telegram_bot import TelegramPollingBot

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await TelegramPollingBot().run(AsyncSessionLocal)


if __name__ == "__main__":
    asyncio.run(main())
