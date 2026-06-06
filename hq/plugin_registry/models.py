from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PluginStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class PluginInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    base_url: str | None = None
    status: PluginStatus = PluginStatus.UNKNOWN
    capabilities: list[str] = Field(default_factory=list)
    registered_at: str = ""
    last_heartbeat: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def touch(self) -> None:
        self.last_heartbeat = datetime.now(timezone.utc).isoformat()
        self.status = PluginStatus.ONLINE


class PluginRegisterRequest(BaseModel):
    name: str
    description: str = ""
    version: str = "0.1.0"
    base_url: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class PluginHealthResult(BaseModel):
    plugin_id: str
    status: PluginStatus
    latency_ms: float | None = None
    error: str | None = None
