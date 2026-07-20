import asyncio
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import LearningRule, LogEntry, Position, RlModel
from app.services.control import TradingControlService
from app.services.exchange import ExchangeClient
from app.services.performance_guard import PerformanceGuardService
from app.services.pnl import PnlMetricsService
from app.services.reconciliation import OrderReconciliationService
from app.services.telegram_reports import human_reason, split_telegram_message

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
        chunks = split_telegram_message(text)
        if not chunks:
            return False
        results = [await self._send_message_chunk(chat_id, chunk) for chunk in chunks]
        return all(results)

    async def _send_message_chunk(self, chat_id: int, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text})
                response.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            logger.warning("Telegram sendMessage failed for chat_id=%s error=%s", chat_id, type(exc).__name__)
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
            return "Отправь команду /help, чтобы увидеть возможности бота."
        command = command.split()[0].lower()
        if command in {"/start", "/help"}:
            return (
                "CryBotHunter работает.\n\n"
                "Команды:\n"
                "/status — режим и состояние системы\n"
                "/report — полный текущий отчёт\n"
                "/positions — открытые позиции\n"
                "/trades — последние закрытые сделки\n"
                "/why — последние решения и причины пропуска\n"
                "/learning — состояние обучения\n"
                "/balance — виртуальный/реальный баланс\n"
                "/stats — торговая статистика\n"
                "/guard — защитные ограничения\n"
                "/panic — остановить новые входы\n"
                "/resume — разрешить новые входы\n"
                "/reconcile — сверить локальные ордера\n"
                "/chatid — показать ID этого чата"
            )
        if command == "/stop":
            return "Остановить сервис можно в Railway. Для временной остановки новых входов используй /panic."
        if command == "/panic":
            if not await TradingControlService().panic("telegram"):
                return "Redis unavailable. Panic state could not be persisted; trading remains fail-closed."
            return "PANIC enabled. New entries are paused. Open positions will still be managed."
        if command == "/resume":
            if not await TradingControlService().resume():
                return "Redis unavailable. Trading remains fail-closed."
            return "Trading resumed. New entries are allowed again."
        if command == "/status":
            settings = get_settings()
            paused, reason = await TradingControlService().is_paused()
            open_positions = (
                await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
            ).scalar_one()
            mode = "PAPER — виртуальные деньги" if settings.paper_trading else "LIVE — реальные ордера"
            return (
                "Статус: онлайн\n"
                f"Режим: {mode}\n"
                f"Новые входы на паузе: {'да' if paused else 'нет'}\n"
                f"Причина паузы: {reason or 'нет'}\n"
                f"Открытых позиций: {int(open_positions)}\n"
                f"Исследовательские входы: {'включены' if settings.paper_trading and settings.paper_exploration_enabled else 'выключены'}"
            )
        if command == "/balance":
            balance = await ExchangeClient().get_balance()
            return "Баланс:\n" + "\n".join([f"{asset}: {amount:.2f}" for asset, amount in balance.items()])
        if command == "/stats":
            pnl = await PnlMetricsService().summary(db)
            return (
                f"Статистика:\n"
                f"Закрытых сделок: {pnl.trades_count}\n"
                f"PnL за день: {pnl.pnl_day:+.2f} USDT\n"
                f"PnL за неделю: {pnl.pnl_week:+.2f} USDT\n"
                f"Общий PnL: {pnl.total_pnl:+.2f} USDT\n"
                f"Открытый PnL: {pnl.open_pnl:+.2f} USDT\n"
                f"Доля прибыльных: {pnl.win_rate:.2f}%"
            )
        if command == "/guard":
            report = await PerformanceGuardService().evaluate(db)
            return (
                f"Защитный фильтр:\n"
                f"Новые входы разрешены: {'да' if report.allowed else 'нет'}\n"
                f"Причина: {human_reason(report.reason)}\n"
                f"Проверено сделок: {report.trades_checked}\n"
                f"Доля прибыльных: {report.win_rate:.2f}%\n"
                f"Серия убытков: {report.loss_streak}\n"
                f"Суммарный результат: {report.total_profit:+.2f} USDT"
            )
        if command == "/positions":
            positions = (
                await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))
            ).scalars().all()
            if not positions:
                return "Открытых позиций сейчас нет."
            return "Открытые позиции:\n" + "\n".join(
                f"#{item.id} {item.symbol} {item.side}\n"
                f"  вход {item.entry_price:.4f}, сейчас {item.current_price:.4f}\n"
                f"  SL {item.stop:.4f}, TP {item.take:.4f}, PnL {item.pnl:+.2f} USDT"
                for item in positions
            )
        if command == "/report":
            pnl = await PnlMetricsService().summary(db)
            positions = (
                await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))
            ).scalars().all()
            lines = [
                "📊 ПОЛНЫЙ ТОРГОВЫЙ ОТЧЁТ",
                f"Открытых позиций: {len(positions)}",
                f"Открытый PnL: {pnl.open_pnl:+.2f} USDT",
                f"PnL за день: {pnl.pnl_day:+.2f} USDT",
                f"Общий PnL: {pnl.total_pnl:+.2f} USDT",
                f"Закрытых сделок: {pnl.trades_count}",
                f"Доля прибыльных: {pnl.win_rate:.2f}%",
            ]
            if positions:
                lines.extend(["", "Позиции:"])
                lines.extend(
                    f"• #{item.id} {item.symbol} {item.side}: вход {item.entry_price:.4f}, "
                    f"сейчас {item.current_price:.4f}, PnL {item.pnl:+.2f}, SL {item.stop:.4f}, TP {item.take:.4f}"
                    for item in positions
                )
            return "\n".join(lines)
        if command == "/trades":
            positions = (
                await db.execute(
                    select(Position)
                    .where(Position.status == "CLOSED")
                    .order_by(Position.closed_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            if not positions:
                return "Закрытых сделок пока нет."
            return "Последние закрытые сделки:\n" + "\n".join(
                f"• #{item.id} {item.symbol} {item.side}: вход {item.entry_price:.4f}, "
                f"выход {item.current_price:.4f}, PnL {item.pnl:+.2f}, причина {item.exit_reason or 'не указана'}"
                for item in positions
            )
        if command == "/why":
            entries = (
                await db.execute(
                    select(LogEntry)
                    .where(LogEntry.message.like("Auto-trade cycle%"))
                    .order_by(LogEntry.created_at.desc())
                    .limit(3)
                )
            ).scalars().all()
            if not entries:
                return "Отчётов торгового цикла пока нет."
            return "Последние решения:\n" + "\n\n".join(human_reason(item.message) for item in entries)
        if command == "/learning":
            rules = int((await db.execute(select(func.count()).select_from(LearningRule))).scalar_one())
            observations = int(
                (await db.execute(select(func.coalesce(func.sum(LearningRule.observations), 0)))).scalar_one()
            )
            models = (
                await db.execute(select(RlModel).order_by(RlModel.created_at.desc()).limit(5))
            ).scalars().all()
            lines = [
                "🧠 СОСТОЯНИЕ ОБУЧЕНИЯ",
                f"Правил из закрытых сделок: {rules}",
                f"Наблюдений по сделкам: {observations}",
                "Последние RL-модели:",
            ]
            lines.extend(
                f"• {item.symbol} {item.timeframe}: {item.status}, "
                f"доходность {float((item.metrics or {}).get('return_percent', 0)):+.2f}%, "
                f"причина {(item.metrics or {}).get('promotion_reason', 'нет')}"
                for item in models
            )
            if not models:
                lines.append("• моделей пока нет")
            return "\n".join(lines)
        if command == "/reconcile":
            result = await OrderReconciliationService().reconcile(db)
            return (
                f"Сверка ордеров:\n"
                f"Проверено: {result['checked']}\n"
                f"Обновлено: {result['updated']}\n"
                f"Ошибок: {result['failed']}"
            )
        return "Неизвестная команда. Используй /help."


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
