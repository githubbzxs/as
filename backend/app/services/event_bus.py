from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class EventBus:
    """进程内事件分发。"""

    def __init__(self, queue_size: int = 1024) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._queue_size = queue_size

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        message = {
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        stale: list[asyncio.Queue] = []
        for queue in list(self._subscribers):
            try:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(message)
            except Exception:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)
