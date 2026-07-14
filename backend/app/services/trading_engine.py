from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import LogEntry, OrderStatus, Position, Signal, Trade
from app.schemas.dto import AgentAnalysisOut, MarketCoin, PositionUpdateOut, TradingDecision, TradingRunOut, TradingTickOut
from app.services.agents import AgentOrchestrator
from app.services.cooldown import LossCooldownGuard
from app.services.exchange import ExchangeClient
from app.services.execution import ExecutionService
from app.services.learning import LearningService
from app.services.market_quality import MarketQualityGate
from app.services.market_scanner import MarketScanner
from app.services.optimizer import StrategyOptimizerService
from app.services.performance_guard import PerformanceGuardService
from app.services.pnl import PnlMetricsService
from app.services.pretrade_quality import PreTradeQualityGate
from app.services.risk_manager import RiskManager, RiskSettings
from app.services.strategy import StrategyCore
from app.services.telegram_bot import TelegramNotifier


class TradingEngine:
    def __init__(self, exchange: ExchangeClient | None = None) -> None:
        self.exchange = exchange or ExchangeClient()
        self.scanner = MarketScanner(self.exchange)
        self.market_quality = MarketQualityGate()
        self.strategy = StrategyCore()
        self.optimizer = StrategyOptimizerService()
        self.risk = RiskManager()
        self.execution = ExecutionService(self.exchange)
        self.guard = PerformanceGuardService()
        self.cooldown_guard = LossCooldownGuard()
        self.pnl_metrics = PnlMetricsService()
        self.quality_gate = PreTradeQualityGate()
        self.agents = AgentOrchestrator()
        self.learning = LearningService()
        self.telegram = TelegramNotifier()
        self.settings = get_settings()

    async def run_once(self, db: AsyncSession, settings: RiskSettings, timeframe: str = "1h") -> TradingRunOut:
        balance = (await self.exchange.get_balance()).get("USDT", settings.balance)
        settings = self._settings_with_balance(settings, balance)
        coins = await self.scanner.scan()
        guard = await self.guard.evaluate(db)
        if not guard.allowed:
            db.add(LogEntry(level="WARNING", message=f"Performance guard blocked entries: {guard.reason}"))
            await db.commit()
            return TradingRunOut(
                scanned=len(coins),
                opened=0,
                skipped=len(coins),
                decisions=[
                    TradingDecision(symbol=coin.symbol, signal="WAIT", score=coin.rating, action="SKIPPED", reason=f"performance guard: {guard.reason}")
                    for coin in coins
                ],
            )
        open_count = await self._open_positions_count(db)
        open_symbols = await self._open_symbols(db)
        side_counts = await self._open_side_counts(db)
        daily_pnl = (await self.pnl_metrics.summary(db)).pnl_day
        exposure = await self._portfolio_exposure(db)
        decisions: list[TradingDecision] = []

        for coin in sorted(coins, key=lambda item: item.rating, reverse=True):
            signal = self.strategy.evaluate(coin)
            db_signal = Signal(symbol=coin.symbol, signal=signal.signal, score=signal.score)
            db.add(db_signal)
            trade_settings = settings
            optimizer_reason = ""

            optimization = await self.optimizer.best_for(db, coin.symbol, timeframe)
            if optimization:
                trade_settings, optimizer_reason = self.optimizer.apply_to_risk_settings(trade_settings, optimization)

            if coin.symbol in open_symbols:
                accepted, reason = False, "position already open for symbol"
            else:
                accepted, reason = self.risk.can_open(signal, trade_settings, open_count, daily_pnl)
                if accepted and optimizer_reason:
                    reason = f"{reason}; {optimizer_reason}"
            if accepted:
                cooldown = await self.cooldown_guard.assess(db, coin.symbol)
                if not cooldown.allowed:
                    accepted = False
                    reason = cooldown.reason
            if accepted:
                learning = await self.learning.assess_entry(db, coin, signal.signal)
                if not learning.allowed:
                    accepted = False
                    reason = learning.reason
                elif learning.risk_multiplier < 1:
                    trade_settings = replace(trade_settings, risk_percent=round(trade_settings.risk_percent * learning.risk_multiplier, 4))
                    reason = f"{reason}; {learning.reason}"
                elif learning.penalty > 0:
                    reason = f"{reason}; {learning.reason}"
            if accepted:
                market_quality = self.market_quality.assess(coin)
                if not market_quality.allowed:
                    accepted = False
                    reason = market_quality.reason
                elif market_quality.risk_multiplier < 1:
                    trade_settings = replace(trade_settings, risk_percent=round(trade_settings.risk_percent * market_quality.risk_multiplier, 4))
                    reason = f"{reason}; {market_quality.reason}"
            if accepted:
                quality = await self.quality_gate.assess(db, coin.symbol, timeframe, trade_settings)
                if not quality.allowed:
                    accepted = False
                    reason = quality.reason
                elif quality.risk_multiplier < 1:
                    trade_settings = replace(trade_settings, risk_percent=round(trade_settings.risk_percent * quality.risk_multiplier, 4))
                    reason = f"{reason}; {quality.reason}"
                elif "warning" in quality.reason:
                    reason = f"{reason}; {quality.reason}"
            if accepted:
                side = "LONG" if signal.signal == "BUY" else "SHORT"
                direction_allowed, direction_reason, direction_multiplier = self.risk.directional_exposure(
                    side=side,
                    side_counts=side_counts,
                    max_same_side_positions=self.settings.max_same_side_positions,
                    reduction_start=self.settings.directional_risk_reduction_start,
                    risk_multiplier=self.settings.directional_risk_multiplier,
                )
                if not direction_allowed:
                    accepted = False
                    reason = direction_reason
                elif direction_multiplier < 1:
                    trade_settings = replace(trade_settings, risk_percent=round(trade_settings.risk_percent * direction_multiplier, 4))
                    reason = f"{reason}; {direction_reason}"
            if accepted:
                accepted, reason, candidate_notional = self._exposure_gate(coin, signal.signal, balance, trade_settings, exposure)
            else:
                candidate_notional = 0.0
            if accepted:
                committee = await self._committee_gate(db, coin, signal.signal)
                if committee and not self._committee_allows_signal(committee, signal.signal):
                    accepted = False
                    reason = (
                        f"committee rejected: final={committee.final_action}, "
                        f"consensus={committee.consensus_score:.2f}, confidence={committee.final_confidence:.2f}"
                    )
            if accepted:
                position = await self._open_position(db, coin, signal.signal, signal.reasons, balance, trade_settings)
                if position:
                    open_count += 1
                    open_symbols.add(coin.symbol)
                    side_counts[position.side] = side_counts.get(position.side, 0) + 1
                    exposure["gross"] += candidate_notional
                    exposure["symbols"][coin.symbol] = exposure["symbols"].get(coin.symbol, 0.0) + candidate_notional
                    db.add(LogEntry(level="INFO", message=f"Opened {signal.signal} paper position for {coin.symbol}"))
                    message = (
                        f"Position opened\n"
                        f"{position.side} {coin.symbol}\n"
                        f"Entry: {position.entry_price:.4f}\n"
                        f"Stop: {position.stop:.4f}\n"
                        f"Take: {position.take:.4f}\n"
                        f"Score: {signal.score}"
                    )
                    await self.telegram.broadcast(message)
                    decisions.append(
                        TradingDecision(symbol=coin.symbol, signal=signal.signal, score=signal.score, action="OPENED", reason=reason)
                    )
                else:
                    decisions.append(
                        TradingDecision(symbol=coin.symbol, signal=signal.signal, score=signal.score, action="SKIPPED", reason="position size is zero")
                    )
            else:
                db.add(LogEntry(level="INFO", message=f"Skipped {coin.symbol}: {reason}"))
                decisions.append(
                    TradingDecision(symbol=coin.symbol, signal=signal.signal, score=signal.score, action="SKIPPED", reason=reason)
                )

        await db.commit()
        opened = sum(1 for item in decisions if item.action == "OPENED")
        return TradingRunOut(scanned=len(coins), opened=opened, skipped=len(decisions) - opened, decisions=decisions)

    async def manage_open_positions(self, db: AsyncSession) -> TradingTickOut:
        positions = (
            await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.asc()))
        ).scalars().all()
        if not positions:
            return TradingTickOut(checked=0, closed=0, updated=[])

        market = {coin.symbol: coin for coin in await self.scanner.scan([position.symbol for position in positions])}
        updates: list[PositionUpdateOut] = []

        for position in positions:
            coin = market.get(position.symbol)
            if not coin:
                continue
            previous_price = position.current_price
            position.current_price = coin.price
            position.highest_price = max(position.highest_price or position.entry_price, coin.price)
            position.lowest_price = min(position.lowest_price or position.entry_price, coin.price)
            if await self._apply_partial_take_profit(db, position, coin.price):
                db.add(LogEntry(level="INFO", message=f"Partially closed {position.symbol} #{position.id}: remaining={position.volume:.6f}"))
            if self._apply_breakeven(position):
                db.add(LogEntry(level="INFO", message=f"Moved {position.symbol} #{position.id} stop to breakeven: stop={position.stop:.4f}"))
            self._apply_trailing_stop(position)
            position.pnl = await self._position_total_pnl(db, position, coin.price)
            exit_reason = self._exit_reason(position)
            if exit_reason:
                await self._close_position(db, position, coin.price, exit_reason)
            updates.append(
                PositionUpdateOut(
                    id=position.id,
                    symbol=position.symbol,
                    side=position.side,
                    previous_price=previous_price,
                    current_price=position.current_price,
                    pnl=position.pnl,
                    status=position.status,
                    exit_reason=position.exit_reason,
                    stop=position.stop,
                    take=position.take,
                )
            )

        await db.commit()
        closed = sum(1 for item in updates if item.status == "CLOSED")
        return TradingTickOut(checked=len(positions), closed=closed, updated=updates)

    async def _open_position(
        self,
        db: AsyncSession,
        coin: MarketCoin,
        signal: str,
        signal_reasons: list[str],
        balance: float,
        settings: RiskSettings,
    ) -> Position | None:
        side = "LONG" if signal == "BUY" else "SHORT"
        stop, take, initial_risk = self._exit_plan(coin.price, coin.atr, side, settings)
        volume = self.risk.position_size(balance, settings.risk_percent, coin.price, stop)
        if volume <= 0:
            return None
        entry_order = await self.execution.execute_market(
            db,
            coin.symbol,
            "buy" if side == "LONG" else "sell",
            volume,
            coin.price,
            "ENTRY",
        )
        if entry_order.status != OrderStatus.FILLED.value or not entry_order.average_price:
            return None
        entry_price = entry_order.average_price
        volume = entry_order.filled_amount or entry_order.requested_amount
        stop, take, initial_risk = self._exit_plan(entry_price, coin.atr, side, settings)
        position = Position(
            symbol=coin.symbol,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            volume=volume,
            stop=stop,
            take=take,
            initial_risk=initial_risk,
            breakeven_applied=False,
            breakeven_trigger_r=settings.breakeven_trigger_r,
            breakeven_offset_percent=settings.breakeven_offset_percent,
            partial_take_profit_r=settings.partial_take_profit_r,
            partial_close_percent=settings.partial_close_percent,
            partial_taken=False,
            trailing_stop_percent=settings.trailing_stop_percent,
            highest_price=entry_price,
            lowest_price=entry_price,
            entry_context=self.learning.entry_context(coin, signal, signal_reasons),
        )
        db.add(position)
        await db.flush()
        db.add(Trade(position_id=position.id, symbol=coin.symbol, side=side, entry_price=entry_price, exit_price=None, profit=-entry_order.fee))
        return position

    def _exit_plan(self, entry_price: float, atr: float, side: str, settings: RiskSettings) -> tuple[float, float, float]:
        percent_risk = entry_price * settings.stop_loss_percent / 100
        atr_risk = atr * settings.atr_stop_multiplier if atr > 0 else 0
        initial_risk = round(max(atr_risk, percent_risk), 8)
        reward = initial_risk * settings.risk_reward_ratio
        if side == "LONG":
            return round(entry_price - initial_risk, 8), round(entry_price + reward, 8), initial_risk
        return round(entry_price + initial_risk, 8), round(entry_price - reward, 8), initial_risk

    def _exposure_gate(
        self,
        coin: MarketCoin,
        signal: str,
        balance: float,
        settings: RiskSettings,
        exposure: dict,
    ) -> tuple[bool, str, float]:
        side = "LONG" if signal == "BUY" else "SHORT"
        stop, _take, _initial_risk = self._exit_plan(coin.price, coin.atr, side, settings)
        volume = self.risk.position_size(balance, settings.risk_percent, coin.price, stop)
        candidate_notional = self.risk.position_notional(coin.price, volume)
        accepted, reason = self.risk.can_add_exposure(
            balance=balance,
            current_gross_exposure=exposure["gross"],
            current_symbol_exposure=exposure["symbols"].get(coin.symbol, 0.0),
            candidate_notional=candidate_notional,
            max_gross_exposure_percent=self.settings.max_gross_exposure_percent,
            max_symbol_exposure_percent=self.settings.max_symbol_exposure_percent,
        )
        return accepted, reason, candidate_notional

    async def _committee_gate(self, db: AsyncSession, coin: MarketCoin, signal: str) -> AgentAnalysisOut | None:
        if not self.settings.ai_committee_enabled or signal not in {"BUY", "SELL"}:
            return None
        analysis = await self.agents.analyze_coin(db, coin)
        db.add(
            LogEntry(
                level="INFO",
                message=(
                    f"AI committee {coin.symbol}: final={analysis.final_action}, "
                    f"consensus={analysis.consensus_score:.2f}, confidence={analysis.final_confidence:.2f}"
                ),
            )
        )
        return analysis

    def _committee_allows_signal(self, analysis: AgentAnalysisOut, signal: str) -> bool:
        return (
            analysis.approved
            and analysis.final_action == signal
            and analysis.consensus_score >= self.settings.ai_committee_min_consensus
        )

    async def _apply_partial_take_profit(self, db: AsyncSession, position: Position, price: float) -> bool:
        if position.partial_taken or not self._partial_take_profit_reached(position, price):
            return False
        close_volume = self._partial_close_volume(position)
        if close_volume <= 0 or close_volume >= position.volume:
            return False
        exit_order = await self.execution.execute_market(
            db,
            position.symbol,
            "sell" if position.side == "LONG" else "buy",
            close_volume,
            price,
            "PARTIAL_TAKE_PROFIT",
        )
        if exit_order.status != OrderStatus.FILLED.value or not exit_order.average_price:
            db.add(LogEntry(level="ERROR", message=f"Failed partial take profit for {position.symbol} #{position.id}"))
            return False
        partial_profit = self._profit_for_volume(position, exit_order.average_price, close_volume) - exit_order.fee
        position.volume = round(position.volume - close_volume, 8)
        position.partial_taken = True
        db.add(
            Trade(
                position_id=position.id,
                symbol=position.symbol,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_order.average_price,
                profit=round(partial_profit, 4),
            )
        )
        position.pnl = await self._position_total_pnl(db, position, price)
        await self.telegram.broadcast(
            f"Partial take profit\n"
            f"{position.side} {position.symbol}\n"
            f"Closed: {close_volume:.6f}\n"
            f"Exit: {exit_order.average_price:.4f}\n"
            f"Profit: {partial_profit:.2f}"
        )
        return True

    def _partial_take_profit_reached(self, position: Position, price: float) -> bool:
        initial_risk = position.initial_risk or abs(position.entry_price - position.stop)
        if initial_risk <= 0:
            return False
        trigger = initial_risk * (position.partial_take_profit_r or 1.0)
        if position.side == "LONG":
            return price >= position.entry_price + trigger
        return price <= position.entry_price - trigger

    def _partial_close_volume(self, position: Position) -> float:
        close_percent = min(max(position.partial_close_percent or 0.0, 0.0), 90.0)
        return round(position.volume * close_percent / 100, 8)

    async def _close_position(self, db: AsyncSession, position: Position, exit_price: float, reason: str) -> None:
        exit_order = await self.execution.execute_market(
            db,
            position.symbol,
            "sell" if position.side == "LONG" else "buy",
            position.volume,
            exit_price,
            f"EXIT_{reason}",
        )
        if exit_order.status != OrderStatus.FILLED.value or not exit_order.average_price:
            db.add(LogEntry(level="ERROR", message=f"Failed to close {position.symbol} #{position.id}: {reason}"))
            return
        position.status = "CLOSED"
        position.exit_reason = reason
        position.closed_at = datetime.now(timezone.utc)
        position.current_price = exit_order.average_price
        trade = (
            await db.execute(
                select(Trade)
                .where(Trade.position_id == position.id, Trade.exit_price.is_(None))
                .order_by(Trade.created_at.desc())
            )
        ).scalars().first()
        if not trade:
            trade = (
                await db.execute(
                    select(Trade)
                    .where(Trade.symbol == position.symbol, Trade.exit_price.is_(None))
                    .order_by(Trade.created_at.desc())
            )
        ).scalars().first()
        previous_realized = await self._position_profit_sum(db, position.id, exclude_trade_id=trade.id if trade else None)
        final_trade_profit = self._final_trade_profit(
            existing_trade_profit=float(trade.profit or 0.0) if trade else 0.0,
            position=position,
            exit_price=exit_order.average_price,
            exit_fee=exit_order.fee,
        )
        if trade:
            trade.exit_price = exit_order.average_price
            trade.profit = final_trade_profit
        else:
            db.add(
                Trade(
                    position_id=position.id,
                    symbol=position.symbol,
                    side=position.side,
                    entry_price=position.entry_price,
                    exit_price=exit_order.average_price,
                    profit=final_trade_profit,
                )
            )
        position.pnl = self._total_closed_profit(previous_realized, final_trade_profit)
        await self.learning.record_closed_position(db, position, position.pnl, reason)
        db.add(LogEntry(level="INFO", message=f"Closed {position.symbol} #{position.id}: {reason}, pnl={position.pnl:.2f}"))
        db.add(LogEntry(level="INFO", message=f"Learning updated from {position.symbol} #{position.id}: reason={reason}, pnl={position.pnl:.2f}"))
        await self.telegram.broadcast(
            f"Position closed\n"
            f"{position.side} {position.symbol}\n"
            f"Reason: {reason}\n"
            f"Exit: {exit_order.average_price:.4f}\n"
            f"PnL: {position.pnl:.2f}"
        )

    def _apply_trailing_stop(self, position: Position) -> None:
        if position.trailing_stop_percent <= 0:
            return
        if position.side == "LONG":
            trailing_stop = position.highest_price * (1 - position.trailing_stop_percent / 100)
            position.stop = max(position.stop, trailing_stop)
        else:
            trailing_stop = position.lowest_price * (1 + position.trailing_stop_percent / 100)
            position.stop = min(position.stop, trailing_stop)

    def _apply_breakeven(self, position: Position) -> bool:
        if position.breakeven_applied:
            return False
        initial_risk = position.initial_risk or abs(position.entry_price - position.stop)
        if initial_risk <= 0:
            return False
        trigger = initial_risk * (position.breakeven_trigger_r or 1.0)
        offset = position.entry_price * (position.breakeven_offset_percent or 0.0) / 100
        if position.side == "LONG" and position.current_price >= position.entry_price + trigger:
            position.stop = max(position.stop, position.entry_price + offset)
            position.breakeven_applied = True
            return True
        if position.side == "SHORT" and position.current_price <= position.entry_price - trigger:
            position.stop = min(position.stop, position.entry_price - offset)
            position.breakeven_applied = True
            return True
        return False

    def _exit_reason(self, position: Position) -> str | None:
        if position.side == "LONG":
            if position.current_price <= position.stop:
                return "STOP_LOSS"
            if position.current_price >= position.take:
                return "TAKE_PROFIT"
        else:
            if position.current_price >= position.stop:
                return "STOP_LOSS"
            if position.current_price <= position.take:
                return "TAKE_PROFIT"
        return None

    def _pnl(self, position: Position, price: float) -> float:
        multiplier = 1 if position.side == "LONG" else -1
        return round((price - position.entry_price) * position.volume * multiplier, 4)

    def _profit_for_volume(self, position: Position, price: float, volume: float) -> float:
        multiplier = 1 if position.side == "LONG" else -1
        return round((price - position.entry_price) * volume * multiplier, 4)

    def _final_trade_profit(self, existing_trade_profit: float, position: Position, exit_price: float, exit_fee: float) -> float:
        remaining_profit = self._profit_for_volume(position, exit_price, position.volume)
        return round(existing_trade_profit + remaining_profit - exit_fee, 4)

    def _total_closed_profit(self, previous_realized: float, final_trade_profit: float) -> float:
        return round(previous_realized + final_trade_profit, 4)

    async def _position_profit_sum(self, db: AsyncSession, position_id: int | None, exclude_trade_id: int | None = None) -> float:
        if position_id is None:
            return 0.0
        query = select(func.coalesce(func.sum(Trade.profit), 0.0)).where(Trade.position_id == position_id)
        if exclude_trade_id is not None:
            query = query.where(Trade.id != exclude_trade_id)
        result = await db.execute(query)
        return float(result.scalar_one())

    async def _position_total_pnl(self, db: AsyncSession, position: Position, price: float) -> float:
        realized_profit = await self._position_profit_sum(db, position.id)
        unrealized_profit = self._pnl(position, price)
        return round(realized_profit + unrealized_profit, 4)

    async def _open_positions_count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
        return int(result.scalar_one())

    async def _open_symbols(self, db: AsyncSession) -> set[str]:
        result = await db.execute(select(Position.symbol).where(Position.status == "OPEN"))
        return set(result.scalars().all())

    async def _open_side_counts(self, db: AsyncSession) -> dict[str, int]:
        result = await db.execute(
            select(Position.side, func.count(Position.id))
            .where(Position.status == "OPEN")
            .group_by(Position.side)
        )
        counts = {"LONG": 0, "SHORT": 0}
        for side, count in result.all():
            counts[str(side)] = int(count)
        return counts

    async def _daily_pnl(self, db: AsyncSession) -> float:
        return (await self.pnl_metrics.summary(db)).pnl_day

    def _settings_with_balance(self, settings: RiskSettings, balance: float) -> RiskSettings:
        return replace(settings, balance=max(float(balance), 0.0))

    async def _portfolio_exposure(self, db: AsyncSession) -> dict:
        result = await db.execute(select(Position).where(Position.status == "OPEN"))
        symbols: dict[str, float] = {}
        gross = 0.0
        for position in result.scalars().all():
            notional = self.risk.position_notional(position.current_price, position.volume)
            gross += notional
            symbols[position.symbol] = symbols.get(position.symbol, 0.0) + notional
        return {"gross": round(gross, 4), "symbols": symbols}
