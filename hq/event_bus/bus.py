import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from hq.event_bus.models import Event, EventType, Subscription


class EventBus:
    """In-memory pub/sub event bus with SSE streaming support."""

    _instance: "EventBus | None" = None
    _subscriptions: list[Subscription]
    _history: list[Event]
    _history_max: int
    _sse_queues: list[asyncio.Queue]
    _lock: asyncio.Lock

    def __new__(cls, history_max: int = 500) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, history_max: int = 500) -> None:
        if not hasattr(self, "_subscriptions"):
            self._subscriptions = []
            self._history = []
            self._history_max = history_max
            self._sse_queues = []
            self._lock = asyncio.Lock()

    @property
    def history(self) -> list[Event]:
        return list(self._history)

    async def publish(self, event_type: str, source: str, data: dict | None = None) -> Event:
        event = Event(
            type=EventType._value2member_map_.get(event_type, EventType.CUSTOM),
            source=source,
            data=data or {},
            timestamp=datetime.now(timezone.utc),
            event_id=str(uuid.uuid4())[:12],
        )
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max:]
            for sub in self._subscriptions:
                if sub.event_type is not None and sub.event_type != event.type:
                    continue
                if sub.source_filter and source != sub.source_filter:
                    continue
                try:
                    if asyncio.iscoroutinefunction(sub.callback):
                        await sub.callback(event)
                    else:
                        sub.callback(event)
                except Exception:
                    pass
            for q in self._sse_queues:
                await q.put(event)
        return event

    def subscribe(self, callback: callable, event_type: EventType | None = None, source_filter: str | None = None) -> Subscription:
        sub = Subscription(event_type=event_type, callback=callback, source_filter=source_filter)
        self._subscriptions.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subscriptions = [s for s in self._subscriptions if s is not sub]

    async def sse_stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue()
        self._sse_queues.append(queue)
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event.type.value}\ndata: {event.source}|{event.event_id}|{event.data}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: \n\n"
        finally:
            self._sse_queues.remove(queue)
