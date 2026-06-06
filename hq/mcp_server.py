"""HQ MCP server — exposes CrossWave AI OS capabilities via JSON-RPC 2.0 over SSE."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.mcp import (
    JSONRPCError,
    JSONRPCErrorCode,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    parse_message,
    serialize_message,
)
from app.core.mcp.transport_sse import SSETransport

from hq.plugin_registry.registry import get_registry
from hq.plugin_registry.models import PluginRegisterRequest
from hq.event_bus.bus import EventBus
from hq.event_bus.models import EventType

logger = logging.getLogger(__name__)


_TOOL_REGISTRY = [
    {
        "name": "crosswave.plugins.list",
        "description": "List all registered plugins/products in the CrossWave AI OS",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crosswave.plugins.get",
        "description": "Get plugin details by ID",
        "inputSchema": {"type": "object", "properties": {"plugin_id": {"type": "string"}}, "required": ["plugin_id"]},
    },
    {
        "name": "crosswave.plugins.register",
        "description": "Register a new plugin/product in the CrossWave AI OS",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "base_url": {"type": "string"},
                "description": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "version", "base_url"],
        },
    },
    {
        "name": "crosswave.plugins.heartbeat",
        "description": "Update plugin heartbeat timestamp",
        "inputSchema": {"type": "object", "properties": {"plugin_id": {"type": "string"}}, "required": ["plugin_id"]},
    },
    {
        "name": "crosswave.events.publish",
        "description": "Publish an event to the CrossWave event bus",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "source": {"type": "string"},
                "data": {"type": "object"},
            },
            "required": ["event_type", "source"],
        },
    },
    {
        "name": "crosswave.events.history",
        "description": "Get recent event history",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []},
    },
    {
        "name": "crosswave.system.status",
        "description": "Get overall CrossWave AI OS system health status",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crosswave.nocobase.stats",
        "description": "Get NocoBase collection stats (employee/order counts)",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crosswave.nocobase.summary",
        "description": "Get rich NocoBase summary with MRR and status distributions",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crosswave.nocobase.query",
        "description": "Query any NocoBase collection by name",
        "inputSchema": {
            "type": "object",
            "properties": {"collection": {"type": "string"}},
            "required": ["collection"],
        },
    },
]


class HQMCPError(Exception):
    pass


class HQMCServer:
    def __init__(self):
        self._transport = SSETransport()
        self._handlers: dict[str, Any] = {}
        self._register_handlers()

    def _register_handlers(self):
        for tool in _TOOL_REGISTRY:
            name = tool["name"]
            method_name = name.replace(".", "_")
            handler = getattr(self, f"_handle_{method_name}", None)
            if handler:
                self._handlers[name] = handler

    @property
    def transport(self) -> SSETransport:
        return self._transport

    def get_tool_definitions(self) -> list[dict]:
        return [dict(t) for t in _TOOL_REGISTRY]

    async def initialize(self):
        await self._transport.connect()

    async def shutdown(self):
        await self._transport.disconnect()

    async def handle_message(self, raw_body: str | bytes) -> str:
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode()
        try:
            msg = parse_message(raw_body)
        except JSONRPCError as e:
            return serialize_message(e)
        except Exception as e:
            return serialize_message(JSONRPCError(code=JSONRPCErrorCode.PARSE_ERROR, message=f"Parse error: {e}"))

        if isinstance(msg, JSONRPCNotification):
            await self._dispatch_notification(msg)
            return ""

        if isinstance(msg, JSONRPCRequest):
            response = await self._dispatch_request(msg)
            payload = serialize_message(response)
            await self._transport.send_jsonrpc_response(json.loads(payload))
            return ""

        return serialize_message(JSONRPCError(code=JSONRPCErrorCode.INVALID_REQUEST, message="Unexpected message type"))

    async def _dispatch_request(self, req: JSONRPCRequest) -> JSONRPCResponse | JSONRPCError:
        method = req.method
        if method == "ping":
            return JSONRPCResponse(result={"status": "pong"}, id=req.id)
        if method == "initialize":
            params = req.params or {}
            return JSONRPCResponse(result={
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "crosswave-hq-mcp", "version": "0.1.0"},
            }, id=req.id)
        if method == "notifications/initialized":
            return JSONRPCResponse(result={"status": "ok"}, id=req.id)
        if method == "tools/list":
            return JSONRPCResponse(result={"tools": self.get_tool_definitions()}, id=req.id)

        handler = self._handlers.get(method)
        if handler is None:
            return JSONRPCError(code=JSONRPCErrorCode.METHOD_NOT_FOUND, message=f"Method not found: {method}", id=req.id)
        try:
            params = req.params or {}
            if asyncio.iscoroutinefunction(handler):
                result = await handler(params)
            else:
                result = handler(params)
            return JSONRPCResponse(result=result, id=req.id)
        except Exception as e:
            logger.exception("Handler error for %s", method)
            return JSONRPCError(code=JSONRPCErrorCode.INTERNAL_ERROR, message=f"Handler error: {e}", id=req.id)

    async def _dispatch_notification(self, notification: JSONRPCNotification):
        handler = self._handlers.get(notification.method)
        if handler is None:
            return
        try:
            params = notification.params or {}
            if asyncio.iscoroutinefunction(handler):
                await handler(params)
            else:
                handler(params)
        except Exception:
            logger.exception("Notification handler error for %s", notification.method)

    async def sse_events(self):
        async for event in self._transport.iter_events():
            yield event

    # ── Tool handlers ──────────────────────────────────────────────────────

    async def _handle_crosswave_plugins_list(self, params: dict) -> dict:
        registry = get_registry()
        plugins = registry.list()
        return {"plugins": [p.model_dump() for p in plugins], "count": len(plugins)}

    async def _handle_crosswave_plugins_get(self, params: dict) -> dict:
        registry = get_registry()
        plugin = registry.get(params["plugin_id"])
        if not plugin:
            return {"error": "not_found"}
        return plugin.model_dump()

    async def _handle_crosswave_plugins_register(self, params: dict) -> dict:
        registry = get_registry()
        req = PluginRegisterRequest(
            name=params["name"],
            version=params["version"],
            base_url=params["base_url"],
            description=params.get("description", ""),
            capabilities=params.get("capabilities", []),
        )
        info = registry.register(req)
        return {"id": info.id, "name": info.name, "status": info.status.value}

    async def _handle_crosswave_plugins_heartbeat(self, params: dict) -> dict:
        registry = get_registry()
        info = registry.heartbeat(params["plugin_id"])
        if not info:
            return {"error": "not_found"}
        return {"id": info.id, "status": info.status.value}

    async def _handle_crosswave_events_publish(self, params: dict) -> dict:
        bus = EventBus()
        event = await bus.publish(params["event_type"], params["source"], params.get("data"))
        return {"event_id": event.event_id, "type": event.type.value}

    async def _handle_crosswave_events_history(self, params: dict) -> dict:
        bus = EventBus()
        limit = params.get("limit", 20)
        history = bus.history[-limit:]
        return {"events": [{"id": e.event_id, "type": e.type.value, "source": e.source, "data": e.data} for e in history]}

    async def _handle_crosswave_system_status(self, params: dict) -> dict:
        registry = get_registry()
        statuses = await registry.check_all_health()
        return {"plugins": statuses, "healthy_count": sum(1 for s in statuses if s["status"] == "healthy")}

    async def _handle_crosswave_nocobase_stats(self, params: dict) -> dict:
        from hq.nocobase_client import get_stats
        return await get_stats()

    async def _handle_crosswave_nocobase_summary(self, params: dict) -> dict:
        from hq.nocobase_client import get_summary
        return await get_summary()

    async def _handle_crosswave_nocobase_query(self, params: dict) -> dict:
        from hq.nocobase_client import list_all
        items = await list_all(params["collection"])
        return {"collection": params["collection"], "count": len(items), "items": items}


hq_mcp_server = HQMCServer()
