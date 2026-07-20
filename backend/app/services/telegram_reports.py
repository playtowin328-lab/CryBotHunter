from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.models.entities import Position
from app.schemas.dto import PositionUpdateOut, TradingDecision, TradingRunOut, TradingTickOut


EXIT_REASON_LABELS = {
    "STOP_LOSS": "сработал стоп-лосс",
    "TAKE_PROFIT": "достигнут тейк-профит",
    "EMERGENCY_DRAWDOWN": "аварийное закрытие из-за лимита просадки",
    "MANUAL": "закрыто вручную",
}

DECISION_REASON_LABELS = {
    "strategy returned WAIT": "строгий торговый сигнал ещё не сформирован",
    "position already open for symbol": "по этому инструменту уже есть открытая позиция",
    "maximum open positions reached": "достигнут лимит открытых позиций",
    "signal score below minimum rating": "оценка сигнала ниже допустимого порога",
    "daily loss limit reached": "достигнут дневной лимит убытка",
    "gross exposure limit reached": "достигнут общий лимит нагрузки на депозит",
    "symbol exposure limit reached": "достигнут лимит нагрузки по инструменту",
    "paper exploration position limit reached": "достигнут лимит исследовательских paper-позиций",
    "paper exploration cooldown is active": "для инструмента ещё действует пауза между тестовыми входами",
}


def format_worker_started(*, paper_trading: bool, loop_seconds: int, exploration_enabled: bool) -> str:
    return (
        "🟢 Торговый сервис запущен\n"
        f"Режим: {'PAPER — виртуальные деньги' if paper_trading else 'LIVE — реальные ордера'}\n"
        f"Проверка рынка: каждые {loop_seconds} сек.\n"
        f"Исследовательские входы: {'включены' if paper_trading and exploration_enabled else 'выключены'}\n"
        "Бот будет сообщать о входах, сопровождении, закрытиях, прибыли/убытке и причинах отказа."
    )


def format_trade_opened(
    position: Position,
    *,
    score: int,
    reason: str,
    paper_trading: bool,
    exploration: bool,
) -> str:
    notional = float(position.entry_price) * float(position.volume)
    risk_amount = abs(float(position.entry_price) - float(position.stop)) * float(position.volume)
    reward_amount = abs(float(position.take) - float(position.entry_price)) * float(position.volume)
    source = (
        "исследовательский paper-вход: строгий сигнал был WAIT, направление выбрано по рыночному уклону"
        if exploration
        else "основная стратегия и все защитные проверки разрешили вход"
    )
    return (
        "🧪 ОТКРЫТА ТЕСТОВАЯ ПОЗИЦИЯ\n" if paper_trading else "🚀 ОТКРЫТА РЕАЛЬНАЯ ПОЗИЦИЯ\n"
    ) + (
        f"ID: #{position.id}\n"
        f"Инструмент: {position.symbol}\n"
        f"Направление: {_side_label(position.side)}\n"
        f"Вход: {_price(position.entry_price)}\n"
        f"Объём: {float(position.volume):.8f} ({notional:.2f} USDT)\n"
        f"Стоп-лосс: {_price(position.stop)} (плановый риск ≈ {risk_amount:.2f} USDT)\n"
        f"Тейк-профит: {_price(position.take)} (цель ≈ {reward_amount:.2f} USDT)\n"
        f"Трейлинг-стоп: {float(position.trailing_stop_percent):.2f}%\n"
        f"Оценка сигнала: {score}/100\n"
        f"Почему вошёл: {source}.\n"
        f"Решение проверок: {human_reason(reason)}.\n"
        "Что дальше: цена и PnL отслеживаются автоматически; бот сообщит о переносе защиты, частичной фиксации и закрытии."
    )


def format_protection_update(position: Position, event: str) -> str:
    label = "стоп перенесён в безубыток" if event == "BREAKEVEN" else event
    return (
        "🛡 ОБНОВЛЕНА ЗАЩИТА ПОЗИЦИИ\n"
        f"#{position.id} {position.symbol} {_side_label(position.side)}\n"
        f"Событие: {label}\n"
        f"Текущая цена: {_price(position.current_price)}\n"
        f"Новый стоп: {_price(position.stop)}\n"
        f"Текущий PnL: {float(position.pnl):+.2f} USDT"
    )


def format_partial_take_profit(
    position: Position,
    *,
    closed_volume: float,
    exit_price: float,
    profit: float,
) -> str:
    return (
        "💰 ЧАСТЬ ПРИБЫЛИ ЗАФИКСИРОВАНА\n"
        f"#{position.id} {position.symbol} {_side_label(position.side)}\n"
        f"Закрытый объём: {closed_volume:.8f}\n"
        f"Цена фиксации: {_price(exit_price)}\n"
        f"Результат части: {profit:+.2f} USDT\n"
        f"Осталось в позиции: {float(position.volume):.8f}\n"
        f"Общий текущий PnL: {float(position.pnl):+.2f} USDT"
    )


def format_trade_closed(position: Position, *, exit_price: float, reason: str) -> str:
    pnl = float(position.pnl or 0.0)
    result = "прибыль" if pnl > 0 else "убыток" if pnl < 0 else "без результата"
    duration = _duration(position.entered_at, position.closed_at)
    context = position.entry_context or {}
    exploration = bool(context.get("paper_exploration"))
    learning = (
        "Результат записан в память сделок и будет учитыватьcя при следующих входах."
        if exploration or context
        else "Результат сохранён в истории сделок."
    )
    return (
        "✅ ПОЗИЦИЯ ЗАКРЫТА\n" if pnl >= 0 else "🔴 ПОЗИЦИЯ ЗАКРЫТА С УБЫТКОМ\n"
    ) + (
        f"ID: #{position.id}\n"
        f"Инструмент: {position.symbol}\n"
        f"Направление: {_side_label(position.side)}\n"
        f"Вход: {_price(position.entry_price)}\n"
        f"Выход: {_price(exit_price)}\n"
        f"Причина: {EXIT_REASON_LABELS.get(reason, reason)}\n"
        f"Время в позиции: {duration}\n"
        f"Итог: {pnl:+.2f} USDT ({result})\n"
        f"Что произошло: {_close_explanation(position.side, exit_price, position.entry_price, reason)}\n"
        f"Обучение: {learning}"
    )


def format_cycle_report(
    run: TradingRunOut,
    tick: TradingTickOut,
    *,
    paper_trading: bool,
) -> str:
    lines = [
        "📊 ОТЧЁТ ТОРГОВОГО ЦИКЛА",
        f"Режим: {'PAPER' if paper_trading else 'LIVE'}",
        f"Проверено инструментов: {run.scanned}",
        f"Открыто позиций: {run.opened}",
        f"Пропущено: {run.skipped}",
        f"Проверено открытых позиций: {tick.checked}",
        f"Закрыто позиций: {tick.closed}",
        f"Обновлений памяти по сделкам: {tick.closed}",
    ]
    if run.decisions:
        lines.extend(["", "Решения:"])
        lines.extend(_decision_lines(run.decisions))
    if tick.updated:
        lines.extend(["", "Открытые позиции и изменения:"])
        lines.extend(_position_update_lines(tick.updated))
    if run.opened == 0 and tick.closed == 0:
        lines.extend(["", "Итог: бот работает, но в этом цикле новый вход не прошёл условия."])
    return "\n".join(lines)


def format_worker_error(title: str, detail: str) -> str:
    return (
        "⚠️ ОШИБКА ТОРГОВОГО СЕРВИСА\n"
        f"Событие: {title}\n"
        f"Подробности: {detail[:1200]}\n"
        "Новые входы не выполняются, пока цикл не восстановится; открытые позиции будут проверены повторно."
    )


def human_reason(reason: str) -> str:
    normalized = reason.strip()
    if normalized in DECISION_REASON_LABELS:
        return DECISION_REASON_LABELS[normalized]
    translated = normalized
    for source, target in DECISION_REASON_LABELS.items():
        translated = translated.replace(source, target)
    translated = translated.replace("risk accepted", "базовая проверка риска пройдена")
    translated = translated.replace(
        "paper exploration keeps hard risk and market-quality gates",
        "для исследовательского входа сохранены лимиты риска, ликвидности и экспозиции",
    )
    translated = translated.replace("paper exploration from WAIT", "исследовательский вход из сигнала WAIT")
    return translated or "причина не указана"


def split_telegram_message(text: str, limit: int = 4000) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    chunks: list[str] = []
    current = ""
    for line in clean.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current = line
    if current:
        chunks.append(current)
    return chunks


def _decision_lines(decisions: Iterable[TradingDecision]) -> list[str]:
    lines: list[str] = []
    for decision in decisions:
        action = "ОТКРЫТА" if decision.action == "OPENED" else "ПРОПУЩЕНА"
        signal = {"BUY": "ПОКУПКА", "SELL": "ПРОДАЖА", "WAIT": "ОЖИДАНИЕ"}.get(
            decision.signal,
            decision.signal,
        )
        lines.append(
            f"• {decision.symbol}: {signal} → {action}, оценка {decision.score}/100\n"
            f"  Причина: {human_reason(decision.reason)}"
        )
    return lines


def _position_update_lines(updates: Iterable[PositionUpdateOut]) -> list[str]:
    lines: list[str] = []
    for item in updates:
        status = "закрыта" if item.status == "CLOSED" else "открыта"
        movement = _percent_change(item.current_price, item.entry_price or item.previous_price)
        lines.append(
            f"• #{item.id} {item.symbol} {_side_label(item.side)}: {status}, "
            f"цена {_price(item.current_price)}, движение {movement:+.2f}%, PnL {item.pnl:+.2f} USDT, "
            f"SL {_price(item.stop)}, TP {_price(item.take)}"
        )
    return lines


def _side_label(side: str) -> str:
    return "LONG / покупка" if side.upper() == "LONG" else "SHORT / продажа"


def _price(value: float) -> str:
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}".replace(",", " ")
    if abs(number) >= 1:
        return f"{number:.4f}"
    return f"{number:.8f}"


def _percent_change(current: float, entry: float) -> float:
    base = float(entry)
    if base == 0:
        return 0.0
    return (float(current) / base - 1) * 100


def _duration(start: datetime | None, end: datetime | None) -> str:
    if not start:
        return "неизвестно"
    finish = end or datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if finish.tzinfo is None:
        finish = finish.replace(tzinfo=timezone.utc)
    seconds = max(int((finish - start).total_seconds()), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"


def _close_explanation(side: str, exit_price: float, entry_price: float, reason: str) -> str:
    movement = _percent_change(exit_price, entry_price)
    effective = movement if side.upper() == "LONG" else -movement
    direction = "в пользу позиции" if effective > 0 else "против позиции" if effective < 0 else "без движения"
    trigger = EXIT_REASON_LABELS.get(reason, reason)
    return f"цена изменилась на {movement:+.2f}% ({direction}); {trigger}"
