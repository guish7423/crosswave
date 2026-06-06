import asyncio

import pytest

from hq.event_bus import EventBus, EventType
from hq.event_bus.bus import EventBus as _EventBus


@pytest.fixture(autouse=True)
def reset_event_bus():
    _EventBus._instance = None
    yield


class TestEventBusUnit:
    def test_singleton(self):
        b1 = EventBus()
        b2 = EventBus()
        assert b1 is b2

    @pytest.mark.asyncio
    async def test_publish_and_history(self):
        bus = EventBus()
        event = await bus.publish("custom", "test-source", {"msg": "hello"})
        assert event.source == "test-source"
        assert event.data == {"msg": "hello"}
        assert len(bus.history) == 1

    @pytest.mark.asyncio
    async def test_subscribe_callback(self):
        bus = EventBus()
        received = []

        def cb(event):
            received.append(event)

        sub = bus.subscribe(cb)
        await bus.publish("custom", "src", {"x": 1})
        assert len(received) == 1
        assert received[0].data == {"x": 1}

        bus.unsubscribe(sub)
        await bus.publish("custom", "src", {"x": 2})
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e), event_type=EventType.USER_LOGIN)
        await bus.publish("user.login", "auth", {})
        await bus.publish("custom", "other", {})
        assert len(received) == 1
        assert received[0].type == EventType.USER_LOGIN

    @pytest.mark.asyncio
    async def test_history_max(self):
        bus = EventBus(history_max=3)
        for i in range(5):
            await bus.publish("custom", "src", {"i": i})
        assert len(bus.history) == 3
        assert bus.history[0].data["i"] == 2


def test_integration_via_http(client):
    from hq.event_bus.bus import EventBus as Bus
    Bus._instance = None
    resp = client.post("/api/hq/events", json={"type": "custom", "source": "test", "data": {"key": "val"}}, headers={"X-HQ-Token": "test-hq-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["type"] == "custom"

    resp = client.get("/api/hq/events", headers={"X-HQ-Token": "test-hq-token"})
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["source"] == "test"
    assert events[0]["data"]["key"] == "val"
