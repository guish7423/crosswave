"""stdio transport for MCP — JSON-RPC 2.0 over stdin/stdout.

Message framing: newline-delimited JSON (one JSON object per line).
Stderr is used for logging/debug output.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import AsyncIterator

from app.core.mcp.protocol import JSONRPCError, JSONRPCErrorCode


class StdioTransport:
    """Bidirectional JSON-RPC communication over stdio.

    Reads JSON-RPC messages from stdin (or a custom reader) as
    newline-delimited JSON, and writes responses to stdout (or a
    custom writer). Diagnostic output goes to stderr.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader | None = None,
        writer: asyncio.StreamWriter | None = None,
    ):
        self._reader = reader or asyncio.StreamReader()
        self._writer = writer
        self._buffer = b""
        self._closed = False

    async def receive(self) -> str | None:
        """Read one JSON-RPC message from the input stream.

        Returns the raw JSON string, or None on EOF.
        Raises JSONRPCError for protocol-level issues.
        """
        if self._closed:
            return None

        while True:
            line = await self._reader.readline()
            if not line:
                self._closed = True
                return None

            line = line.strip()
            if not line:
                # Skip empty lines (keepalive/noise)
                continue

            try:
                # Validate it's parseable JSON
                json.loads(line)
                return line.decode() if isinstance(line, bytes) else line
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise JSONRPCError(
                    code=JSONRPCErrorCode.PARSE_ERROR,
                    message="Parse error: invalid JSON in input stream",
                )

    async def send(self, message: str) -> None:
        """Write a JSON-RPC message to the output stream."""
        if self._closed:
            return

        data = (message + "\n").encode() if not message.endswith("\n") else message.encode()
        if self._writer:
            self._writer.write(data)
            await self._writer.drain()
        else:
            sys.stdout.write(data.decode())
            sys.stdout.flush()

    async def log(self, level: str, message: str) -> None:
        """Write a diagnostic message to stderr."""
        entry = json.dumps({"type": "log", "level": level, "message": message})
        print(entry, file=sys.stderr, flush=True)

    async def receive_loop(self) -> AsyncIterator[str]:
        """Async generator yielding messages until EOF."""
        while True:
            msg = await self.receive()
            if msg is None:
                break
            yield msg

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True
