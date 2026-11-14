import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import cast

from sqlalchemy.engine import RowMapping

from super_ai.memory.sqlite.jobs import JobOutcome, JobRepository
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobContext:
    repository: JobRepository
    job: RowMapping

    @property
    def id(self) -> str:
        return str(self.job["id"])

    @property
    def scope(self) -> OwnerScope:
        owner = str(self.job["owner_user_id"])
        return OwnerScope(owner, owner)

    @property
    def payload(self) -> JsonObject:
        return cast(JsonObject, self.job["payload"])

    async def emit(self, kind: str, data: JsonObject) -> None:
        if not await self.repository.append_event(
            self.job, kind, data, owner_user_id=self.scope.owner_user_id
        ):
            raise asyncio.CancelledError


JobHandler = Callable[[JobContext], Awaitable[None]]


class JobHandlers:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        if not kind or kind in self._handlers:
            raise ValueError("任务类型为空或已注册")
        self._handlers[kind] = handler

    def kinds(self) -> tuple[str, ...]:
        return tuple(self._handlers)

    def get(self, kind: str) -> JobHandler:
        return self._handlers[kind]


class JobWorker:
    def __init__(
        self,
        repository: JobRepository,
        handlers: JobHandlers,
        *,
        concurrency: int = 2,
        lease_seconds: float = 30,
        poll_seconds: float = 0.2,
    ) -> None:
        if concurrency < 1 or lease_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("worker 配置无效")
        self.repository = repository
        self.handlers = handlers
        self.concurrency = concurrency
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self._slots: list[asyncio.Task[None]] = []

    async def __aenter__(self) -> "JobWorker":
        self._slots = [asyncio.create_task(self._slot()) for _ in range(self.concurrency)]
        return self

    async def __aexit__(self, *_: object) -> None:
        for slot in self._slots:
            slot.cancel()
        await asyncio.gather(*self._slots, return_exceptions=True)
        self._slots.clear()

    async def _slot(self) -> None:
        while True:
            try:
                await self.repository.recover_expired()
                kinds = self.handlers.kinds()
                job = await self.repository.claim(kinds, self.lease_seconds) if kinds else None
                if job is not None:
                    await self._execute(job)
                    continue
            except Exception:
                logger.warning("后台任务轮询或状态写入失败，将继续轮询。")
            await asyncio.sleep(self.poll_seconds)

    async def _invoke(self, job: RowMapping) -> JobOutcome:
        try:
            await self.handlers.get(str(job["kind"]))(JobContext(self.repository, job))
        except Exception:
            return "handler_error"
        return "succeeded"

    async def _execute(self, job: RowMapping) -> None:
        deadline = monotonic() + float(job["timeout_seconds"])
        interval = min(self.poll_seconds, self.lease_seconds / 3)
        task = asyncio.create_task(self._invoke(job))
        try:
            while True:
                remaining = max(0, deadline - monotonic())
                done, _ = await asyncio.wait((task,), timeout=min(interval, remaining))
                if done:
                    outcome = "handler_error" if task.cancelled() else task.result()
                    await self.repository.finish(job, outcome)
                    return
                current = await self.repository.heartbeat(job, self.lease_seconds)
                if current is None:
                    return
                if current["cancel_requested_at"] is not None or monotonic() >= deadline:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    await self.repository.finish(job, "timeout")
                    return
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
