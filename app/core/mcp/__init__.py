"""MCP (Model Context Protocol) implementation — JSON-RPC 2.0 + stdio/SSE transport.

This module provides a complete MCP protocol implementation for CrossWave,
following the JSON-RPC 2.0 specification with dual transport support.
"""

from app.core.mcp.protocol import (
    JSONRPCError,
    JSONRPCErrorCode,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    parse_message,
    serialize_message,
)

__all__ = [
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCErrorCode",
    "JSONRPCNotification",
    "parse_message",
    "serialize_message",
]
