"""SSE (Server-Sent Events) transport for MCP — JSON-RPC 2.0 over HTTP SSE.

The SSE transport uses:
- GET /sse → SSE stream for receiving events from the server
- POST /message → HTTP endpoint for sending requests to the server

Per the MCP spec, the first event in the SSE stream contains the endpoint URL
that the client should POST messages to.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class SSETransportError(Exception):
    """Base error for SSE transport issues."""
    pass


class SSETransport:
    """SSE transport for MCP server.

    Manages SSE connections and event formatting.
    Uses a callback-based approach for dispatching events.
    """

    def __init__(self):
        self._connected = False
        self.on_event: EventHandler | None = None
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Mark the transport as connected."""
        self._connected = True

    async def disconnect(self) -> None:
        """Mark the transport as disconnected."""
        self._connected = False

    async def send_event(self, event: str, data: str) -> None:
        """Send an SSE event with the given type and data.

        The event is dispatched via the on_event callback if set,
        or queued for later retrieval.
        """
        formatted = self._format_sse(event, data)
        entry = {"event": event, "data": data, "formatted": formatted}

        if self.on_event:
            await self.on_event(entry)
        else:
            await self._queue.put(entry)

    async def send_jsonrpc_response(self, response_data: dict[str, Any]) -> None:
        """Send a JSON-RPC response as an SSE message event."""
        await self.send_event("message", json.dumps(response_data, ensure_ascii=False))

    async def send_error(self, code: int, message: str, data: Any = None, id: Any = None) -> None:
        """Send a JSON-RPC error as an SSE message event."""
        error_obj: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error_obj["data"] = data
        response = {
            "jsonrpc": "2.0",
            "error": error_obj,
        }
        if id is not None:
            response["id"] = id
        await self.send_event("message", json.dumps(response, ensure_ascii=False))

    async def send_endpoint(self, url: str) -> None:
        """Send the endpoint URL notification to the client.

        This is the first event sent after connecting, telling the client
        where to POST JSON-RPC requests.
        """
        await self.send_event("endpoint", url)

    async def send_heartbeat(self) -> None:
        """Send a keepalive heartbeat event."""
        await self.send_event("heartbeat", "")

    async def event_stream(self) -> str:
        """Generate the SSE response body.

        Returns formatted SSE text that can be used as an HTTP response body
        or streamed to the client.
        """
        # Send initial endpoint notification
        parts = []

        while self._connected:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                parts.append(entry["formatted"])
            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                parts.append(self._format_sse("heartbeat", ""))

        return "".join(parts)

    @staticmethod
    def _format_sse(event: str, data: str) -> str:
        """Format an SSE event string.

        Per the SSE spec (text/event-stream):
        - Each event has "event:" and "data:" fields
        - Multiple "data:" lines for multi-line data
        - Events are separated by double newlines
        """
        lines = [f"event: {event}"]
        for data_line in data.split("\n"):
            lines.append(f"data: {data_line}")
        lines.append("")  # Empty line to terminate the event
        lines.append("")  # Second empty line per SSE spec
        return "\n".join(lines)

    @staticmethod
    def parse_sse_line(line: str) -> tuple[str, str] | None:
        """Parse a single SSE line into (field, value).

        Returns None for comments or empty lines.
        """
        if not line or line.startswith(":"):
            return None
        if ":" in line:
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            return field.strip(), value
        return line.strip(), ""
