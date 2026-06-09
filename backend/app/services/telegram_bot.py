import asyncio
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Position, Trade
from app.services.exchange import ExchangeClient

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token)

    async def send_message(self, chat_id: int, text: str) -> None:
        if not self.enabled:
            return
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text})

    async def broadcast(self, text: str) -> None:
        for chat_id in self.settings.telegram_allowed_chat_ids:
            await self.send_message(chat_id, text)


class TelegramCommandService:
    async def handle(self, command: str, db: AsyncSession) -> str:
        command = command.strip()
        if not command:
            return "Send a command: /balance, /stats, /positions."
        command = command.split()[0].lower()
        if command == "/start":
            return "CryBotHunter online. Commands: /chatid, /balance, /stats, /positions, /stop"
        if command == "/stop":
            return "Notifications stay controlled by Railway variables. Stop the telegram service to disable polling."
        if command == "/balance":
            balance = await ExchangeClient().get_balance()
            return "\n".join([f"{asset}: {amount:.2f}" for asset, amount in balance.items()])
        if command == "/stats":
            trades_count, pnl = (
                await db.execute(select(func.count(Trade.id), func.coalesce(func.sum(Trade.profit), 0.0)))
            ).one()
            wins = (await db.execute(select(func.count(Trade.id)).where(Trade.profit > 0))).scalar_one()
            win_rate = (int(wins) / int(trades_count) * 100) if trades_count else 0
            return f"Trades: {trades_count}\nPnL: {float(pnl):.2f}\nWin Rate: {win_rate:.2f}%"
        if command == "/positions":
            positions = (
                await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))
            ).scalars().all()
            if not positions:
                return "No open positions."
            return "\n".join(
                f"#{item.id} {item.symbol} {item.side} entry={item.entry_price:.4f} pnl={item.pnl:.2f}"
                for item in positions
            )
        return "Unknown command. Use /balance, /stats, /positions."


class TelegramPollingBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.notifier = TelegramNotifier()
        self.commands = TelegramCommandService()
        self.offset = 0

    async def run(self, session_factory) -> None:
        if not self.notifier.enabled:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        logger.info("Telegram polling bot started")
        while True:
            try:
                updates = await self._get_updates()
                for update in updates:
                    self.offset = max(self.offset, update["update_id"] + 1)
                    await self._handle_update(update, session_factory)
            except Exception:
                logger.exception("Telegram polling error")
                await asyncio.sleep(5)

    async def _get_updates(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.get(
                f"{self.notifier.base_url}/getUpdates",
                params={"timeout": 30, "offset": self.offset, "allowed_updates": '["message"]'},
            )
            response.raise_for_status()
            return response.json().get("result", [])

    async def _handle_update(self, update: dict, session_factory) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = int(chat.get("id"))
        text = message.get("text", "").strip()

        if self.settings.telegram_allowed_chat_ids and chat_id not in self.settings.telegram_allowed_chat_ids:
            await self.notifier.send_message(chat_id, "This chat is not allowed.")
            return

        if text and text.split()[0].lower() == "/chatid":
            await self.notifier.send_message(chat_id, f"chat_id: {chat_id}")
            return

        async with session_factory() as db:
            reply = await self.commands.handle(text, db)
        await self.notifier.send_message(chat_id, reply)
