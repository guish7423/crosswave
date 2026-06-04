"""Tests for SSE transport layer."""

import asyncio
import json

import pytest

from app.core.mcp.transport_sse import SSETransport, SSETransportError


class TestSSETransport:
    async def test_send_event(self):
        """Send an SSE-formatted event."""
        transport = SSETransport()
        events = []

        async def collector(event):
            events.append(event)

        transport.on_event = collector
        await transport.send_event("message", json.dumps({"hello": "world"}))

        # Give the event loop a chance to process
        await asyncio.sleep(0.01)
        assert len(events) == 1
        assert events[0]["event"] == "message"
        assert json.loads(events[0]["data"]) == {"hello": "world"}

    async def test_send_jsonrpc_response(self):
        """Send a JSON-RPC response as an SSE event."""
        transport = SSETransport()
        events = []

        async def collector(event):
            events.append(event)

        transport.on_event = collector
        response_data = {"jsonrpc": "2.0", "result": "pong", "id": 1}
        await transport.send_jsonrpc_response(response_data)

        await asyncio.sleep(0.01)
        assert len(events) == 1
        assert events[0]["event"] == "message"
        assert json.loads(events[0]["data"]) == response_data

    async def test_send_error_event(self):
        """Send an error as an SSE event."""
        transport = SSETransport()
        events = []

        async def collector(event):
            events.append(event)

        transport.on_event = collector
        await transport.send_error(-32603, "Internal error")

        await asyncio.sleep(0.01)
        assert len(events) == 1
        data = json.loads(events[0]["data"])
        assert data["error"]["code"] == -32603
        assert data["error"]["message"] == "Internal error"

    async def test_send_endpoint_event(self):
        """Send a JSON-RPC endpoint URL notification."""
        transport = SSETransport()
        events = []

        async def collector(event):
            events.append(event)

        transport.on_event = collector
        await transport.send_endpoint("http://localhost:9999/mcp/message")

        await asyncio.sleep(0.01)
        assert len(events) == 1
        assert events[0]["event"] == "endpoint"
        assert events[0]["data"] == "http://localhost:9999/mcp/message"

    async def test_send_heartbeat(self):
        """Send a keepalive heartbeat event."""
        transport = SSETransport()
        events = []

        async def collector(event):
            events.append(event)

        transport.on_event = collector
        await transport.send_heartbeat()

        await asyncio.sleep(0.01)
        assert len(events) >= 1
        assert events[0]["event"] == "heartbeat"

    async def test_format_sse_event(self):
        """Verify SSE event formatting."""
        transport = SSETransport()
        formatted = transport._format_sse("message", '{"key": "value"}')
        assert "event: message\n" in formatted
        assert 'data: {"key": "value"}\n' in formatted
        assert formatted.endswith("\n\n")

    async def test_multiline_data(self):
        """SSE events with multiline data should use data: for each line."""
        transport = SSETransport()
        formatted = transport._format_sse("message", "line1\nline2\nline3")
        lines = formatted.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data:")]
        assert len(data_lines) == 3
