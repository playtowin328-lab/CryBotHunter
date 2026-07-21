from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import WorkerHeartbeat


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HeartbeatEvent:
    kind: str
    worker_name: str
    status: str
    detail: dict
    last_seen_at: datetime
    age_seconds: int


class WorkerHeartbeatService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def record(self, worker_name: str, *, status: str, detail: dict | None = None) -> None:
        if not self.settings.worker_heartbeat_enabled:
            return
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            item = await db.get(WorkerHeartbeat, worker_name)
            if item is None:
                item = WorkerHeartbeat(worker_name=worker_name)
                db.add(item)
            item.status = status[:16]
            item.detail = detail or {}
            item.last_seen_at = now
            if status == "OK":
                item.last_success_at = now
            await db.commit()

    async def watchdog_events(self) -> list[HeartbeatEvent]:
        if not self.settings.worker_heartbeat_enabled:
            return []
        now = datetime.now(timezone.utc)
        stale_seconds = max(int(self.settings.worker_heartbeat_stale_seconds), 60)
        events: list[HeartbeatEvent] = []
        async with AsyncSessionLocal() as db:
            items = (
                await db.execute(
                    select(WorkerHeartbeat)
                    .order_by(WorkerHeartbeat.worker_name.asc())
                    .with_for_update(skip_locked=True)
                )
            ).scalars().all()
            for item in items:
                last_seen = _aware(item.last_seen_at)
                age_seconds = max(int((now - last_seen).total_seconds()), 0)
                transition = heartbeat_transition(
                    last_seen=last_seen,
                    stale_alerted=item.stale_alerted,
                    now=now,
                    stale_seconds=stale_seconds,
                )
                if transition == "STALE":
                    item.stale_alerted = True
                    events.append(
                        HeartbeatEvent(
                            kind="STALE",
                            worker_name=item.worker_name,
                            status=item.status,
                            detail=item.detail or {},
                            last_seen_at=last_seen,
                            age_seconds=age_seconds,
                        )
                    )
                elif transition == "RECOVERED":
                    item.stale_alerted = False
                    events.append(
                        HeartbeatEvent(
                            kind="RECOVERED",
                            worker_name=item.worker_name,
                            status=item.status,
                            detail=item.detail or {},
                            last_seen_at=last_seen,
                            age_seconds=age_seconds,
                        )
                    )
            await db.commit()
        return events


class HeartbeatReporter:
    def __init__(self, worker_name: str) -> None:
        self.worker_name = worker_name
        self.settings = get_settings()
        self.service = WorkerHeartbeatService()
        self.status = "STARTING"
        self.detail: dict = {}
        self._task: asyncio.Task | None = None
        self._write_lock = asyncio.Lock()

    async def start(self) -> None:
        if not self.settings.worker_heartbeat_enabled or self._task is not None:
            return
        await self._safe_record()
        self._task = asyncio.create_task(self._run(), name=f"heartbeat:{self.worker_name}")

    async def set_status(self, status: str, detail: dict | None = None) -> None:
        self.status = status
        self.detail = detail or {}
        await self._safe_record()

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        interval = max(int(self.settings.worker_heartbeat_interval_seconds), 10)
        while True:
            await asyncio.sleep(interval)
            await self._safe_record()

    async def _safe_record(self) -> None:
        async with self._write_lock:
            try:
                await self.service.record(self.worker_name, status=self.status, detail=self.detail)
            except Exception as exc:
                logger.warning(
                    "Worker heartbeat write failed worker=%s error=%s",
                    self.worker_name,
                    type(exc).__name__,
                )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def heartbeat_transition(
    *,
    last_seen: datetime,
    stale_alerted: bool,
    now: datetime,
    stale_seconds: int,
) -> str | None:
    is_stale = _aware(last_seen) < _aware(now) - timedelta(seconds=max(int(stale_seconds), 1))
    if is_stale and not stale_alerted:
        return "STALE"
    if not is_stale and stale_alerted:
        return "RECOVERED"
    return None
