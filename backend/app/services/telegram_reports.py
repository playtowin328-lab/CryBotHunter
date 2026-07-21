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


def format_worker_started(
    *,
    paper_trading: bool,
    loop_seconds: int,
    exploration_enabled: bool,
    exploration_max_positions: int,
    exploration_risk_percent: float,
    report_interval_minutes: int,
) -> str:
    return (
        "🟢 Торговый сервис запущен\n"
        f"Режим: {'PAPER — виртуальные деньги' if paper_trading else 'LIVE — реальные ордера'}\n"
        f"Проверка рынка: каждые {loop_seconds} сек.\n"
        f"Исследовательские входы: {'включены' if paper_trading and exploration_enabled else 'выключены'}\n"
        f"Максимум тестовых позиций: {exploration_max_positions}\n"
        f"Риск одной тестовой позиции: до {exploration_risk_percent:.3f}% виртуального баланса\n"
        f"Полная периодическая сводка: каждые {report_interval_minutes} мин.\n"
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
    context = position.entry_context or {}
    notional = float(context.get("notional") or float(position.entry_price) * float(position.volume))
    risk_amount = float(
        context.get("planned_risk")
        or abs(float(position.entry_price) - float(position.stop)) * float(position.volume)
    )
    reward_amount = float(
        context.get("planned_reward")
        or abs(float(position.take) - float(position.entry_price)) * float(position.volume)
    )
    risk_reward = float(context.get("risk_reward_ratio") or (reward_amount / risk_amount if risk_amount > 0 else 0))
    stop_distance = float(
        context.get("stop_distance_percent")
        or abs(float(position.entry_price) - float(position.stop)) / float(position.entry_price) * 100
    )
    take_distance = float(
        context.get("take_distance_percent")
        or abs(float(position.take) - float(position.entry_price)) / float(position.entry_price) * 100
    )
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
        f"Время входа: {_format_datetime(position.entered_at)}\n"
        f"Объём: {float(position.volume):.8f} ({notional:.2f} USDT)\n"
        f"Стоп-лосс: {_price(position.stop)} — {stop_distance:.2f}% от входа, плановый риск ≈ {risk_amount:.2f} USDT\n"
        f"Тейк-профит: {_price(position.take)} — {take_distance:.2f}% от входа, цель ≈ {reward_amount:.2f} USDT\n"
        f"Риск/прибыль: 1:{risk_reward:.2f}; риск от баланса: {float(context.get('risk_percent') or 0):.3f}%\n"
        f"Трейлинг-стоп: {float(position.trailing_stop_percent):.2f}%\n"
        f"Безубыток: после {float(position.breakeven_trigger_r or 1.0):.2f}R; частичная фиксация: "
        f"{float(position.partial_close_percent or 50.0):.0f}% позиции при {float(position.partial_take_profit_r or 1.0):.2f}R\n"
        f"Оценка сигнала: {score}/100\n"
        f"Почему вошёл: {source}.\n"
        f"Решение проверок: {human_reason(reason)}.\n"
        f"Рынок при входе: {_entry_context_summary(context)}\n"
        f"Факторы сигнала: {_entry_reason_summary(context)}\n"
        "Что дальше: цена и PnL отслеживаются автоматически; бот сообщит о переносе защиты, частичной фиксации и закрытии."
    )


def format_position_details(position: Position) -> str:
    context = position.entry_context or {}
    notional = float(context.get("notional") or float(position.entry_price) * float(position.volume))
    pnl = float(position.pnl or 0.0)
    pnl_percent = pnl / notional * 100 if notional > 0 else 0.0
    movement = _effective_percent(position.side, position.current_price, position.entry_price)
    stop_distance = _percent_distance(position.current_price, position.stop)
    take_distance = _percent_distance(position.current_price, position.take)
    protection = []
    if position.breakeven_applied:
        protection.append("стоп уже перенесён в безубыток")
    if position.partial_taken:
        protection.append("часть прибыли уже зафиксирована")
    if not protection:
        protection.append("исходный защитный план активен")
    return (
        f"#{position.id} {position.symbol} — {_side_label(position.side)}\n"
        f"Статус: {position.status}; в позиции {_duration(position.entered_at, position.closed_at)}\n"
        f"Вход {_price(position.entry_price)} → сейчас {_price(position.current_price)} "
        f"({movement:+.2f}% для позиции)\n"
        f"Объём: {float(position.volume):.8f}; стоимость при входе: {notional:.2f} USDT\n"
        f"PnL: {pnl:+.2f} USDT ({pnl_percent:+.2f}% от стоимости позиции)\n"
        f"SL {_price(position.stop)} ({stop_distance:.2f}% от текущей цены); "
        f"TP {_price(position.take)} ({take_distance:.2f}%)\n"
        f"Защита: {', '.join(protection)}; трейлинг {float(position.trailing_stop_percent):.2f}%\n"
        f"Контекст входа: {_entry_context_summary(context)}\n"
        f"Причины входа: {_entry_reason_summary(context)}"
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
    notional = float(context.get("notional") or float(position.entry_price) * float(position.volume))
    pnl_percent = pnl / notional * 100 if notional > 0 else 0.0
    planned_risk = float(context.get("planned_risk") or float(position.initial_risk or 0) * float(position.volume))
    result_r = pnl / planned_risk if planned_risk > 0 else 0.0
    effective_move = _effective_percent(position.side, exit_price, position.entry_price)
    best_move = _effective_percent(
        position.side,
        _positive_or_entry(
            position.highest_price if position.side.upper() == "LONG" else position.lowest_price,
            position.entry_price,
        ),
        position.entry_price,
    )
    worst_move = _effective_percent(
        position.side,
        _positive_or_entry(
            position.lowest_price if position.side.upper() == "LONG" else position.highest_price,
            position.entry_price,
        ),
        position.entry_price,
    )
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
        f"Объём: {float(position.volume):.8f}; стоимость при входе: {notional:.2f} USDT\n"
        f"Вход: {_price(position.entry_price)}\n"
        f"Выход: {_price(exit_price)}\n"
        f"Причина: {EXIT_REASON_LABELS.get(reason, reason)}\n"
        f"Время в позиции: {duration}\n"
        f"Итог: {pnl:+.2f} USDT, {pnl_percent:+.2f}% стоимости, {result_r:+.2f}R ({result})\n"
        f"Движение для позиции: итог {effective_move:+.2f}%, лучшее {best_move:+.2f}%, худшее {worst_move:+.2f}%\n"
        f"Что произошло: {_close_explanation(position.side, exit_price, position.entry_price, reason)}\n"
        f"Условия входа: {_entry_context_summary(context)}\n"
        f"Первоначальные факторы: {_entry_reason_summary(context)}\n"
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
        movement = _effective_percent(item.side, item.current_price, item.entry_price or item.previous_price)
        notional = float(item.entry_price or item.current_price) * float(item.volume)
        pnl_percent = float(item.pnl) / notional * 100 if notional > 0 else 0.0
        lines.append(
            f"• #{item.id} {item.symbol} {_side_label(item.side)}: {status}, "
            f"цена {_price(item.current_price)}, результат {movement:+.2f}%, "
            f"PnL {item.pnl:+.2f} USDT ({pnl_percent:+.2f}%), объём {item.volume:.8f}, "
            f"SL {_price(item.stop)} ({_percent_distance(item.current_price, item.stop):.2f}%), "
            f"TP {_price(item.take)} ({_percent_distance(item.current_price, item.take):.2f}%)"
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


def _effective_percent(side: str, current: float, entry: float) -> float:
    movement = _percent_change(current, entry)
    return movement if side.upper() == "LONG" else -movement


def _percent_distance(current: float, target: float) -> float:
    base = float(current)
    if base == 0:
        return 0.0
    return abs(float(target) / base - 1) * 100


def _positive_or_entry(value: float | None, entry: float) -> float:
    candidate = float(value or 0)
    return candidate if candidate > 0 else float(entry)


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "будет записано после сохранения позиции"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _entry_context_summary(context: dict) -> str:
    if not context:
        return "контекст старой позиции не сохранён"
    regime = str(context.get("regime") or "UNKNOWN")
    rating = context.get("rating", "—")
    rsi = context.get("rsi", "—")
    atr = context.get("atr_percent", "—")
    trend = str(context.get("trend_stack") or "—")
    macd = str(context.get("macd_direction") or "—")
    return f"режим {regime}, рейтинг {rating}/100, RSI {rsi}, ATR {atr}%, тренд {trend}, MACD {macd}"


def _entry_reason_summary(context: dict) -> str:
    reasons = context.get("reasons") if context else None
    if not isinstance(reasons, list) or not reasons:
        decision = str(context.get("decision_reason") or "") if context else ""
        return human_reason(decision) if decision else "для старой позиции подробные факторы не сохранены"
    return "; ".join(human_reason(str(reason)) for reason in reasons[:5])


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
