from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import LogEntry, OrderStatus, Position, Signal, Trade
from app.schemas.dto import AgentAnalysisOut, MarketCoin, PositionUpdateOut, TradingDecision, TradingRunOut, TradingTickOut
from app.services.agents import AgentOrchestrator
from app.services.exchange import ExchangeClient
from app.services.execution import ExecutionService
from app.services.market_scanner import MarketScanner
from app.services.performance_guard import PerformanceGuardService
from app.services.risk_manager import RiskManager, RiskSettings
from app.services.strategy import StrategyCore
from app.services.telegram_bot import TelegramNotifier


class TradingEngine:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.strategy = StrategyCore()
        self.risk = RiskManager()
        self.exchange = ExchangeClient()
        self.execution = ExecutionService()
        self.guard = PerformanceGuardService()
        self.agents = AgentOrchestrator()
        self.telegram = TelegramNotifier()
        self.settings = get_settings()

    async def run_once(self, db: AsyncSession, settings: RiskSettings) -> TradingRunOut:
        balance = (await self.exchange.get_balance()).get("USDT", settings.balance)
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
        daily_pnl = await self._daily_pnl(db)
        decisions: list[TradingDecision] = []

        for coin in sorted(coins, key=lambda item: item.rating, reverse=True):
            signal = self.strategy.evaluate(coin)
            db_signal = Signal(symbol=coin.symbol, signal=signal.signal, score=signal.score)
            db.add(db_signal)

            if coin.symbol in open_symbols:
                accepted, reason = False, "position already open for symbol"
            else:
                accepted, reason = self.risk.can_open(signal, settings, open_count, daily_pnl)
            if accepted:
                committee = await self._committee_gate(db, coin, signal.signal)
                if committee and not self._committee_allows_signal(committee, signal.signal):
                    accepted = False
                    reason = (
                        f"committee rejected: final={committee.final_action}, "
                        f"consensus={committee.consensus_score:.2f}, confidence={committee.final_confidence:.2f}"
                    )
            if accepted:
                position = await self._open_position(db, coin, signal.signal, balance, settings)
                if position:
                    open_count += 1
                    open_symbols.add(coin.symbol)
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
            self._apply_trailing_stop(position)
            position.pnl = self._pnl(position, coin.price)
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

    async def _open_position(self, db: AsyncSession, coin: MarketCoin, signal: str, balance: float, settings: RiskSettings) -> Position | None:
        side = "LONG" if signal == "BUY" else "SHORT"
        stop = coin.price * (1 - settings.stop_loss_percent / 100) if side == "LONG" else coin.price * (1 + settings.stop_loss_percent / 100)
        take = coin.price * (1 + settings.take_profit_percent / 100) if side == "LONG" else coin.price * (1 - settings.take_profit_percent / 100)
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
        stop = entry_price * (1 - settings.stop_loss_percent / 100) if side == "LONG" else entry_price * (1 + settings.stop_loss_percent / 100)
        take = entry_price * (1 + settings.take_profit_percent / 100) if side == "LONG" else entry_price * (1 - settings.take_profit_percent / 100)
        position = Position(
            symbol=coin.symbol,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            volume=volume,
            stop=stop,
            take=take,
            trailing_stop_percent=settings.trailing_stop_percent,
            highest_price=entry_price,
            lowest_price=entry_price,
        )
        db.add(position)
        db.add(Trade(symbol=coin.symbol, side=side, entry_price=entry_price, exit_price=None, profit=-entry_order.fee))
        return position

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
        position.pnl = self._pnl(position, exit_order.average_price)
        trade = (
            await db.execute(
                select(Trade)
                .where(Trade.symbol == position.symbol, Trade.exit_price.is_(None))
                .order_by(Trade.created_at.desc())
            )
        ).scalars().first()
        if trade:
            trade.exit_price = exit_order.average_price
            trade.profit = position.pnl - exit_order.fee
            position.pnl = trade.profit
        db.add(LogEntry(level="INFO", message=f"Closed {position.symbol} #{position.id}: {reason}, pnl={position.pnl:.2f}"))
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

    async def _open_positions_count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
        return int(result.scalar_one())

    async def _open_symbols(self, db: AsyncSession) -> set[str]:
        result = await db.execute(select(Position.symbol).where(Position.status == "OPEN"))
        return set(result.scalars().all())

    async def _daily_pnl(self, db: AsyncSession) -> float:
        result = await db.execute(select(func.coalesce(func.sum(Trade.profit), 0.0)))
        return float(result.scalar_one())
