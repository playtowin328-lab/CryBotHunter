import asyncio
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Position
from app.services.control import TradingControlService
from app.services.exchange import ExchangeClient
from app.services.performance_guard import PerformanceGuardService
from app.services.pnl import PnlMetricsService
from app.services.reconciliation import OrderReconciliationService

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token)

    async def send_message(self, chat_id: int, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text})
                response.raise_for_status()
                return True
        except httpx.HTTPError:
            logger.exception("Telegram sendMessage failed for chat_id=%s", chat_id)
            return False

    async def broadcast(self, text: str) -> int:
        delivered = 0
        for chat_id in self.settings.telegram_allowed_chat_ids:
            delivered += int(await self.send_message(chat_id, text))
        return delivered


class TelegramCommandService:
    async def handle(self, command: str, db: AsyncSession) -> str:
        command = command.strip()
        if not command:
            return "Send a command: /balance, /stats, /positions."
        command = command.split()[0].lower()
        if command in {"/start", "/help"}:
            return (
                "CryBotHunter online.\n\n"
                "Commands:\n"
                "/status - system mode and open positions\n"
                "/panic - pause new entries\n"
                "/resume - resume new entries\n"
                "/balance - paper/live balance\n"
                "/stats - trading statistics\n"
                "/guard - performance guard status\n"
                "/positions - active positions\n"
                "/reconcile - reconcile local orders\n"
                "/chatid - show this Telegram chat id\n"
                "/stop - deployment hint"
            )
        if command == "/stop":
            return "Notifications stay controlled by Railway variables. Stop the telegram service to disable polling."
        if command == "/panic":
            await TradingControlService().panic("telegram")
            return "PANIC enabled. New entries are paused. Open positions will still be managed."
        if command == "/resume":
            await TradingControlService().resume()
            return "Trading resumed. New entries are allowed again."
        if command == "/status":
            settings = get_settings()
            paused, reason = await TradingControlService().is_paused()
            open_positions = (
                await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
            ).scalar_one()
            mode = "paper trading" if settings.paper_trading else "live trading"
            return f"Status: online\nMode: {mode}\nPaused: {paused} {reason or ''}\nOpen positions: {int(open_positions)}"
        if command == "/balance":
            balance = await ExchangeClient().get_balance()
            return "Balance:\n" + "\n".join([f"{asset}: {amount:.2f}" for asset, amount in balance.items()])
        if command == "/stats":
            pnl = await PnlMetricsService().summary(db)
            return (
                f"Stats:\n"
                f"Closed trades: {pnl.trades_count}\n"
                f"Day PnL: {pnl.pnl_day:.2f}\n"
                f"Week PnL: {pnl.pnl_week:.2f}\n"
                f"Total PnL: {pnl.total_pnl:.2f}\n"
                f"Open PnL: {pnl.open_pnl:.2f}\n"
                f"Win Rate: {pnl.win_rate:.2f}%"
            )
        if command == "/guard":
            report = await PerformanceGuardService().evaluate(db)
            return (
                f"Performance Guard:\n"
                f"Allowed: {report.allowed}\n"
                f"Reason: {report.reason}\n"
                f"Trades: {report.trades_checked}\n"
                f"Win Rate: {report.win_rate:.2f}%\n"
                f"Loss Streak: {report.loss_streak}\n"
                f"Total Profit: {report.total_profit:.2f}"
            )
        if command == "/positions":
            positions = (
                await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))
            ).scalars().all()
            if not positions:
                return "No open positions."
            return "Open positions:\n" + "\n".join(
                f"#{item.id} {item.symbol} {item.side} entry={item.entry_price:.4f} stop={item.stop:.4f} take={item.take:.4f} pnl={item.pnl:.2f}"
                for item in positions
            )
        if command == "/reconcile":
            result = await OrderReconciliationService().reconcile(db)
            return f"Reconciliation:\nChecked: {result['checked']}\nUpdated: {result['updated']}\nFailed: {result['failed']}"
        return "Unknown command. Use /help."


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
        if "id" not in chat:
            return
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
