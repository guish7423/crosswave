"""JSON-RPC 2.0 message types for MCP (Model Context Protocol).

Defines the core message structures per the JSON-RPC 2.0 specification:
- Request:  {jsonrpc: "2.0", id, method, params?}
- Response: {jsonrpc: "2.0", id, result}
- Error:    {jsonrpc: "2.0", id, error: {code, message, data?}}
- Notification: {jsonrpc: "2.0", method, params?}  (no id)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class JSONRPCErrorCode:
    """Standard JSON-RPC 2.0 error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Server error range: -32000 to -32099
    SERVER_ERROR_START = -32099
    SERVER_ERROR_END = -32000

    # MCP-specific error codes (from MCP spec)
    CONNECTION_CLOSED = -32000
    REQUEST_TIMEOUT = -32001


_ERROR_MESSAGES: dict[int, str] = {
    JSONRPCErrorCode.PARSE_ERROR: "Parse error",
    JSONRPCErrorCode.INVALID_REQUEST: "Invalid Request",
    JSONRPCErrorCode.METHOD_NOT_FOUND: "Method not found",
    JSONRPCErrorCode.INVALID_PARAMS: "Invalid params",
    JSONRPCErrorCode.INTERNAL_ERROR: "Internal error",
}


def _default_error_message(code: int) -> str:
    return _ERROR_MESSAGES.get(code, "Server error")


@dataclass
class JSONRPCRequest:
    """A JSON-RPC 2.0 Request object."""
    method: str
    id: int | str | float | None = None
    params: Any = None
    jsonrpc: str = "2.0"


@dataclass
class JSONRPCResponse:
    """A JSON-RPC 2.0 Response object (success)."""
    result: Any = None
    id: int | str | float | None = None
    jsonrpc: str = "2.0"
    error: None = None  # Never set on success responses


@dataclass
class JSONRPCError(Exception):
    """A JSON-RPC 2.0 Response object (error)."""
    code: int
    message: str = ""
    id: int | str | float | None = None
    data: Any = None
    jsonrpc: str = "2.0"

    def __post_init__(self):
        if not self.message:
            self.message = _default_error_message(self.code)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


@dataclass
class JSONRPCNotification:
    """A JSON-RPC 2.0 Notification (Request without id)."""
    method: str
    params: Any = None
    id: None = None
    jsonrpc: str = "2.0"


MessageType = JSONRPCRequest | JSONRPCResponse | JSONRPCError | JSONRPCNotification


def serialize_message(msg: MessageType) -> str:
    """Serialize a JSON-RPC message to a JSON string.

    Uses strict serialization that omits None-valued fields
    where appropriate per the spec.
    """
    obj: dict[str, Any] = {"jsonrpc": msg.jsonrpc}

    if isinstance(msg, JSONRPCRequest):
        obj["method"] = msg.method
        if msg.params is not None:
            obj["params"] = msg.params
        if msg.id is not None:
            obj["id"] = msg.id

    elif isinstance(msg, JSONRPCResponse):
        obj["result"] = msg.result
        obj["id"] = msg.id  # Include id even when null (spec allows null id)

    elif isinstance(msg, JSONRPCError):
        error_obj: dict[str, Any] = {"code": msg.code, "message": msg.message}
        if msg.data is not None:
            error_obj["data"] = msg.data
        obj["error"] = error_obj
        obj["id"] = msg.id  # Include id even when null

    elif isinstance(msg, JSONRPCNotification):
        obj["method"] = msg.method
        if msg.params is not None:
            obj["params"] = msg.params

    return json.dumps(obj, ensure_ascii=False)


def parse_message(raw: str) -> MessageType:
    """Parse a JSON string into a JSON-RPC message object.

    Raises JSONRPCError for protocol-level failures (parse error, invalid request).
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise JSONRPCError(
            code=JSONRPCErrorCode.PARSE_ERROR,
            message="Parse error: invalid JSON",
        ) from None

    if not isinstance(data, dict):
        raise JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Invalid Request: body must be a JSON object",
        )

    # Validate jsonrpc field
    if "jsonrpc" not in data:
        raise JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Invalid Request: missing 'jsonrpc' field",
        )
    if data["jsonrpc"] != "2.0":
        raise JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message=f"Invalid Request: jsonrpc must be '2.0', got '{data['jsonrpc']}'",
        )

    # Detect message type
    has_id = "id" in data
    has_method = "method" in data
    has_result = "result" in data
    has_error = "error" in data

    # Response/Error must have id
    if not has_method and (has_result or has_error):
        # Response
        if has_result and has_error:
            raise JSONRPCError(
                code=JSONRPCErrorCode.INVALID_REQUEST,
                message="Invalid Response: must not contain both 'result' and 'error'",
            )
        if has_error:
            err = data["error"]
            if not isinstance(err, dict) or "code" not in err or "message" not in err:
                raise JSONRPCError(
                    code=JSONRPCErrorCode.INVALID_REQUEST,
                    message="Invalid Error: 'error' must contain 'code' and 'message'",
                )
            return JSONRPCError(
                code=err["code"],
                message=err["message"],
                data=err.get("data"),
                id=data.get("id"),
            )
        return JSONRPCResponse(
            result=data["result"],
            id=data.get("id"),
        )

    # Request or Notification
    if not has_method:
        raise JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Invalid Request: missing 'method'",
        )

    if not isinstance(data["method"], str) or not data["method"]:
        raise JSONRPCError(
            code=JSONRPCErrorCode.INVALID_REQUEST,
            message="Invalid Request: 'method' must be a non-empty string",
        )

    if has_id:
        return JSONRPCRequest(
            method=data["method"],
            params=data.get("params"),
            id=data["id"],
        )
    else:
        return JSONRPCNotification(
            method=data["method"],
            params=data.get("params"),
        )
