"""Tests for stdio transport layer."""

import asyncio
import json
from io import StringIO

import pytest

from app.core.mcp import JSONRPCError, JSONRPCErrorCode
from app.core.mcp.transport_stdio import StdioTransport


class _TestWriter:
    """A simple write-only stream for testing."""
    def __init__(self):
        self.buffer = StringIO()

    def write(self, data: bytes | str) -> int | None:
        if isinstance(data, bytes):
            data = data.decode()
        self.buffer.write(data)
        return len(data)

    async def drain(self):
        pass

    def getvalue(self) -> str:
        return self.buffer.getvalue()


class TestStdioTransport:
    async def test_send_and_receive_roundtrip(self):
        """Simulate a full stdio request/response cycle."""
        reader = asyncio.StreamReader()
        writer = _TestWriter()

        # Feed a JSON-RPC request into the reader
        request = {"jsonrpc": "2.0", "method": "ping", "id": 1}
        reader.feed_data((json.dumps(request) + "\n").encode())
        reader.feed_eof()

        transport = StdioTransport(reader=reader, writer=writer)  # type: ignore[arg-type]

        # Read the incoming message
        msg = await transport.receive()
        assert msg is not None
        data = json.loads(msg)
        assert data["method"] == "ping"
        assert data["id"] == 1

        # Send a response back
        response = {"jsonrpc": "2.0", "result": "pong", "id": 1}
        await transport.send(json.dumps(response))

        # Verify it was written
        written = writer.getvalue()
        assert json.loads(written.strip()) == response

    async def test_receive_malformed_json(self):
        """Malformed JSON should raise ParseError."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"not valid json\n")
        reader.feed_eof()

        transport = StdioTransport(reader=reader)

        with pytest.raises(JSONRPCError) as exc_info:
            await transport.receive()
        assert exc_info.value.code == JSONRPCErrorCode.PARSE_ERROR

    async def test_receive_empty_line(self):
        """Empty lines should be skipped."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"\n\n")
        reader.feed_data(b'{"jsonrpc":"2.0","method":"test","id":1}\n')
        reader.feed_eof()

        transport = StdioTransport(reader=reader)
        msg = await transport.receive()
        assert msg is not None
        data = json.loads(msg)
        assert data["method"] == "test"

    async def test_send_to_stderr(self):
        """Log/debug messages go to stderr, not stdout."""
        transport = StdioTransport()
        await transport.log("info", "Server started")
        # log writes to stderr — we just verify no crash

    async def test_concurrent_messages(self):
        """Handle multiple messages in the stream."""
        reader = asyncio.StreamReader()
        lines = "\n".join([
            json.dumps({"jsonrpc": "2.0", "method": "a", "id": 1}),
            json.dumps({"jsonrpc": "2.0", "method": "b", "id": 2}),
            json.dumps({"jsonrpc": "2.0", "method": "c", "id": 3}),
            "",
        ])
        reader.feed_data(lines.encode())
        reader.feed_eof()

        transport = StdioTransport(reader=reader)
        msgs = []
        while True:
            msg = await transport.receive()
            if msg is None:
                break
            msgs.append(json.loads(msg)["method"])

        assert msgs == ["a", "b", "c"]
