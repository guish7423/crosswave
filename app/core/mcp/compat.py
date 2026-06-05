"""Backward compatibility layer for MCP protocol migration.

Provides adapters to translate between the new JSON-RPC 2.0 format
and any older protocol format used by CrossWave components.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from JSON-RPC 2.0 method names to old-style action names
_METHOD_TO_ACTION: dict[str, str] = {
    "resources/list": "list_resources",
    "resources/read": "read_resource",
    "resources/subscribe": "subscribe_resource",
    "resources/unsubscribe": "unsubscribe_resource",
    "tools/list": "list_tools",
    "tools/call": "call_tool",
    "prompts/list": "list_prompts",
    "prompts/get": "get_prompt",
    "ping": "ping",
    "initialize": "initialize",
    "notifications/initialized": "initialized",
    "$/progress": "progress",
    "logging/setLevel": "set_log_level",
}

# Reverse mapping for converting old responses back to new
_ACTION_TO_METHOD: dict[str, str] = {v: k for k, v in _METHOD_TO_ACTION.items()}


@dataclass
class OldProtocolMessage:
    """Representation of the old (pre-JSON-RPC 2.0) message format."""
    type: str  # "request" or "response"
    action: str = ""
    payload: Any = None
    request_id: Any = None
    status: str = "ok"
    error: str | None = None


OldHandler = Callable[[OldProtocolMessage], Coroutine[Any, Any, dict[str, Any] | None]]


def convert_old_to_new(old: OldProtocolMessage) -> dict[str, Any]:
    """Convert an old protocol message to JSON-RPC 2.0 format."""
    method = _ACTION_TO_METHOD.get(old.action, old.action)

    if old.type == "request":
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if old.payload is not None:
            msg["params"] = old.payload
        if old.request_id is not None:
            msg["id"] = old.request_id
        return msg
    elif old.type == "response":
        msg = {"jsonrpc": "2.0"}
        if old.status == "error" or old.error:
            msg["error"] = {
                "code": -32000,
                "message": old.error or "Unknown error",
            }
        else:
            msg["result"] = old.payload if old.payload is not None else {}
        if old.request_id is not None:
            msg["id"] = old.request_id
        return msg

    raise ValueError(f"Unknown old message type: {old.type}")


def convert_new_to_old(new: dict[str, Any]) -> OldProtocolMessage:
    """Convert a JSON-RPC 2.0 message to old protocol format."""
    if "method" in new:
        # Request or Notification
        raw_method = new.get("method", "")
        action = _METHOD_TO_ACTION.get(raw_method, raw_method) if raw_method else ""
        return OldProtocolMessage(
            type="request",
            action=action or "",
            payload=new.get("params"),
            request_id=new.get("id"),
        )
    elif "result" in new:
        return OldProtocolMessage(
            type="response",
            action="",
            payload=new["result"],
            request_id=new.get("id"),
            status="ok",
        )
    elif "error" in new:
        err = new["error"]
        return OldProtocolMessage(
            type="response",
            action="",
            payload=err.get("data"),
            request_id=new.get("id"),
            status="error",
            error=err.get("message", "Unknown error"),
        )
    raise ValueError("Unknown JSON-RPC message type")


class CompatAdapter:
    """Adapter that allows old-style handlers to work with new protocol requests.

    Maps JSON-RPC 2.0 methods to old-style action names and converts
    message formats transparently.
    """

    def __init__(self):
        self._handlers: dict[str, OldHandler] = {}
        self._fallback: OldHandler | None = None

    def register(self, action: str, handler: OldHandler) -> None:
        """Register an old-style handler for a given action."""
        self._handlers[action] = handler

    def register_fallback(self, handler: OldHandler) -> None:
        """Register a fallback handler for unregistered actions."""
        self._fallback = handler

    def _map_method_to_action(self, method: str) -> str:
        """Map a JSON-RPC 2.0 method name to an old-style action."""
        return _METHOD_TO_ACTION.get(method, method)

    def _map_action_to_method(self, action: str) -> str:
        """Map an old-style action to a JSON-RPC 2.0 method name."""
        return _ACTION_TO_METHOD.get(action, action)

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a JSON-RPC 2.0 request using old-style handlers.

        Returns a JSON-RPC 2.0 response dict, or None if unhandled.
        """
        method = request.get("method", "")
        action = self._map_method_to_action(method)
        handler = self._handlers.get(action) or self._fallback

        if handler is None:
            return None

        old_req = OldProtocolMessage(
            type="request",
            action=action,
            payload=request.get("params"),
            request_id=request.get("id"),
        )

        try:
            result = await handler(old_req)
            if result is None:
                return None
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request.get("id"),
            }
        except Exception as e:
            logger.exception("Compat handler failed for %s", action)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Handler error: {e}",
                },
                "id": request.get("id"),
            }
