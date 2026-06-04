"""MCP (Model Context Protocol) service — JSON-RPC 2.0 over SSE.

Provides an MCP server endpoint for CrossWave that exposes agent tools,
resources, and prompts to AI clients (e.g. Claude, Cursor) via the
standard MCP protocol using SSE transport.
"""

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

logger = logging.getLogger(__name__)


class MCPService:
    """MCP server implementation for CrossWave.

    Handles JSON-RPC 2.0 messages over SSE transport, dispatching
    methods to the appropriate handlers.
    """

    def __init__(self):
        self._transport = SSETransport()
        self._method_handlers: dict[str, Any] = {}
        self._initialized = False
        self._client_id: str | None = None

        # Register built-in MCP methods
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register standard MCP protocol methods."""
        self._method_handlers["ping"] = self._handle_ping
        self._method_handlers["initialize"] = self._handle_initialize
        self._method_handlers["notifications/initialized"] = self._handle_initialized_notification

    def register_handler(self, method: str, handler: Any) -> None:
        """Register a custom method handler."""
        self._method_handlers[method] = handler

    @property
    def transport(self) -> SSETransport:
        return self._transport

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> None:
        """Initialize the MCP service and transport."""
        await self._transport.connect()
        logger.info("MCP service initialized")

    async def shutdown(self) -> None:
        """Shutdown the MCP service."""
        await self._transport.disconnect()
        self._initialized = False
        logger.info("MCP service shut down")

    async def handle_message(self, raw_body: str | bytes) -> str:
        """Process an incoming JSON-RPC message and return a response.

        Args:
            raw_body: Raw JSON string from the HTTP request body.

        Returns:
            JSON string of the response (or an error response).
        """
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode()

        try:
            msg = parse_message(raw_body)
        except JSONRPCError as e:
            return serialize_message(e)
        except Exception as e:
            return serialize_message(JSONRPCError(
                code=JSONRPCErrorCode.PARSE_ERROR,
                message=f"Unexpected parse error: {e}",
            ))

        # Notifications don't get responses
        if isinstance(msg, JSONRPCNotification):
            await self._dispatch_notification(msg)
            return ""

        # Handle request — send response via SSE stream, return empty for 202
        if isinstance(msg, JSONRPCRequest):
            response = await self._dispatch_request(msg)
            payload = serialize_message(response)
            await self._transport.send_jsonrpc_response(json.loads(payload))
            return ""

        # Response/Error messages from client (shouldn't happen normally)
        if isinstance(msg, JSONRPCResponse):
            logger.warning("Received unexpected response from client: %s", msg)
            return serialize_message(JSONRPCError(
                code=JSONRPCErrorCode.INVALID_REQUEST,
                message="Server does not accept response messages",
                id=msg.id,
            ))

        if isinstance(msg, JSONRPCError):
            logger.warning("Received unexpected error from client: %s", msg)
            return serialize_message(JSONRPCError(
                code=JSONRPCErrorCode.INVALID_REQUEST,
                message="Server does not accept error messages",
                id=msg.id,
            ))

        return serialize_message(JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Unknown message type",
        ))

    async def _dispatch_request(self, request: JSONRPCRequest) -> JSONRPCResponse | JSONRPCError:
        """Dispatch a request to the appropriate handler."""
        method = request.method
        handler = self._method_handlers.get(method)

        if handler is None:
            return JSONRPCError(
                code=JSONRPCErrorCode.METHOD_NOT_FOUND,
                message=f"Method not found: {method}",
                id=request.id,
            )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(request.params, request.id)
            else:
                result = handler(request.params, request.id)
            return JSONRPCResponse(result=result, id=request.id)
        except JSONRPCError as e:
            e.id = request.id
            return e
        except Exception as e:
            logger.exception("Handler error for %s", method)
            return JSONRPCError(
                code=JSONRPCErrorCode.INTERNAL_ERROR,
                message=f"Handler error: {e}",
                id=request.id,
            )

    async def _dispatch_notification(self, notification: JSONRPCNotification) -> None:
        """Dispatch a notification (no response expected)."""
        handler = self._method_handlers.get(notification.method)
        if handler is None:
            logger.debug("No handler for notification: %s", notification.method)
            return
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(notification.params, None)
            else:
                handler(notification.params, None)
        except Exception:
            logger.exception("Notification handler error for %s", notification.method)

    async def _handle_ping(self, params: Any, id: Any) -> dict[str, str]:
        """Handle ping request."""
        return {"status": "pong", "version": "0.3.0"}

    async def _handle_initialize(self, params: Any, id: Any) -> dict[str, Any]:
        """Handle MCP initialize request.

        Returns server capabilities and version info.
        """
        client_info = params or {}
        protocol_version = client_info.get("protocolVersion", "unknown")
        client_name = client_info.get("clientName", "unknown")

        logger.info(
            "MCP client initialized: %s (protocol: %s)",
            client_name, protocol_version,
        )

        return {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "resources": {},
                "tools": {},
                "prompts": {},
                "logging": {},
            },
            "serverInfo": {
                "name": "crosswave-mcp",
                "version": "0.3.0",
            },
        }

    async def _handle_initialized_notification(self, params: Any, id: Any) -> None:
        """Handle the 'notifications/initialized' notification."""
        self._initialized = True
        logger.info("MCP client fully initialized")


    async def sse_events(self):
        """Async generator for SSE event stream.

        Yields formatted SSE strings for FastAPI's StreamingResponse.
        First event is the endpoint URL, followed by JSON-RPC responses
        and heartbeats.
        """
        async for event in self._transport.iter_events():
            yield event


# Singleton
mcp_service = MCPService()
