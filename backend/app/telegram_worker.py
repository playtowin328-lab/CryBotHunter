import asyncio

from app.db.session import AsyncSessionLocal
from app.safety_manager import configure_stdout_logging
from app.services.telegram_bot import TelegramPollingBot


async def main() -> None:
    configure_stdout_logging()
    await TelegramPollingBot().run(AsyncSessionLocal)


if __name__ == "__main__":
    asyncio.run(main())
