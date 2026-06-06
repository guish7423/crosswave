from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class EventType(StrEnum):
    PLUGIN_REGISTERED = "plugin.registered"
    PLUGIN_DEREGISTERED = "plugin.deregistered"
    PLUGIN_HEALTH_CHANGED = "plugin.health_changed"
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    DEPLOYMENT_CREATED = "deployment.created"
    DEPLOYMENT_UPDATED = "deployment.updated"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CUSTOM = "custom"


@dataclass
class Event:
    type: EventType
    source: str
    data: dict | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str | None = None


@dataclass
class Subscription:
    event_type: EventType | None
    callback: callable
    source_filter: str | None = None
