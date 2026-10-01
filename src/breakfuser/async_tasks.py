"""Cancellable asynchronous subagents with interrupt/enqueue steering and wakeups."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from breakfuser.dag import TaskState
from breakfuser.errors import TaskNotFound

Worker = Callable[[str, asyncio.Event, asyncio.Queue[str]], Awaitable[str]]


@dataclass
class AsyncTaskInfo:
    id: str
    instruction: str
    state: TaskState = TaskState.PENDING
    result: str | None = None
    error: str | None = None
    updates: list[str] = field(default_factory=list)


@dataclass
class _Running:
    info: AsyncTaskInfo
    task: asyncio.Task[None]
    cancel_event: asyncio.Event
    queue: asyncio.Queue[str]


class AsyncTaskManager:
    def __init__(self, worker: Worker) -> None:
        self.worker = worker
        self._tasks: dict[str, _Running] = {}
        self._completed: asyncio.Queue[str] = asyncio.Queue()
        self._wake = asyncio.Event()

    async def start_async_task(self, instruction: str) -> str:
        task_id = uuid.uuid4().hex
        info = AsyncTaskInfo(id=task_id, instruction=instruction)
        cancel_event = asyncio.Event()
        queue: asyncio.Queue[str] = asyncio.Queue()
        running = asyncio.create_task(self._run(task_id, instruction, cancel_event, queue))
        self._tasks[task_id] = _Running(info, running, cancel_event, queue)
        info.state = TaskState.RUNNING
        return task_id

    async def _run(
        self, task_id: str, instruction: str, cancel_event: asyncio.Event, queue: asyncio.Queue[str]
    ) -> None:
        info = self._tasks[task_id].info
        try:
            result = await self.worker(instruction, cancel_event, queue)
            info.result = result
            info.state = TaskState.COMPLETED
        except asyncio.CancelledError:
            info.state = TaskState.CANCELLED
        except Exception as exc:
            info.error = str(exc)
            info.state = TaskState.FAILED
        finally:
            if info.state != TaskState.RUNNING:
                await self._completed.put(task_id)
                self._wake.set()

    def _running(self, task_id: str) -> _Running:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFound(task_id) from exc

    async def check_async_task(self, task_id: str) -> AsyncTaskInfo:
        return self._running(task_id).info

    async def list_async_tasks(self, active_only: bool = True) -> list[AsyncTaskInfo]:
        return [
            running.info
            for running in self._tasks.values()
            if not active_only or running.info.state in {TaskState.PENDING, TaskState.RUNNING}
        ]

    async def cancel_async_task(self, task_id: str) -> None:
        running = self._running(task_id)
        running.cancel_event.set()
        running.task.cancel()
        await asyncio.gather(running.task, return_exceptions=True)
        if running.info.state == TaskState.RUNNING:
            running.info.state = TaskState.CANCELLED

    async def update_async_task(
        self,
        task_id: str,
        instruction: str,
        update_strategy: Literal["interrupt", "enqueue"] = "interrupt",
    ) -> None:
        running = self._running(task_id)
        running.info.updates.append(instruction)
        if update_strategy == "enqueue":
            await running.queue.put(instruction)
            return
        running.cancel_event.set()
        running.task.cancel()
        await asyncio.gather(running.task, return_exceptions=True)
        revised = f"{running.info.instruction}\nSteering update: {instruction}"
        running.info.instruction = revised
        running.info.state = TaskState.RUNNING
        running.cancel_event = asyncio.Event()
        running.task = asyncio.create_task(
            self._run(task_id, revised, running.cancel_event, running.queue)
        )

    async def collect_completed(self) -> list[AsyncTaskInfo]:
        completed: list[AsyncTaskInfo] = []
        while not self._completed.empty():
            task_id = self._completed.get_nowait()
            completed.append(self._running(task_id).info)
        return completed

    async def wait_for_completion(self, timeout: float | None = None) -> AsyncTaskInfo:
        async with asyncio.timeout(timeout):
            task_id = await self._completed.get()
            return self._running(task_id).info

    async def cancel_all(self) -> None:
        await asyncio.gather(
            *(
                self.cancel_async_task(task_id)
                for task_id, running in list(self._tasks.items())
                if not running.task.done()
            )
        )
