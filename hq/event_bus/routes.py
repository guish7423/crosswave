from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from hq.event_bus.bus import EventBus

router = APIRouter(prefix="/api/hq/events", tags=["events"])


def _get_bus() -> EventBus:
    return EventBus()


@router.post("")
async def publish_event(request: Request):
    body = await request.json()
    bus = _get_bus()
    event = await bus.publish(
        event_type=body.get("type", "custom"),
        source=body.get("source", "unknown"),
        data=body.get("data"),
    )
    return {"ok": True, "event_id": event.event_id, "type": event.type.value}


@router.get("")
async def list_events(limit: int = 50, source: str | None = None):
    bus = _get_bus()
    events = bus.history
    if source:
        events = [e for e in events if e.source == source]
    return {
        "events": [
            {
                "id": e.event_id,
                "type": e.type.value,
                "source": e.source,
                "data": e.data,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events[-limit:]
        ]
    }


@router.get("/stream")
async def event_stream(request: Request):
    return StreamingResponse(
        _get_bus().sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
