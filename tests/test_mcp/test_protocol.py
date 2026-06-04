"""Tests for JSON-RPC 2.0 protocol message types."""

import json

import pytest

from app.core.mcp.protocol import (
    JSONRPCError,
    JSONRPCErrorCode,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    parse_message,
    serialize_message,
)


class TestJSONRPCRequest:
    def test_request_with_positional_params(self):
        req = JSONRPCRequest(method="resources/list", params=[], id=1)
        assert req.jsonrpc == "2.0"
        assert req.method == "resources/list"
        assert req.params == []
        assert req.id == 1

    def test_request_with_named_params(self):
        req = JSONRPCRequest(method="tools/call", params={"name": "get_weather", "arguments": {"city": "Beijing"}}, id=2)
        assert req.params["name"] == "get_weather"

    def test_request_without_params(self):
        req = JSONRPCRequest(method="ping", id=3)
        assert req.params is None

    def test_request_serialization(self):
        req = JSONRPCRequest(method="resources/list", params=[], id=1)
        raw = serialize_message(req)
        data = json.loads(raw)
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "resources/list"
        assert data["params"] == []
        assert data["id"] == 1

    def test_request_deserialization(self):
        raw = json.dumps({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "test"}, "id": 5})
        msg = parse_message(raw)
        assert isinstance(msg, JSONRPCRequest)
        assert msg.method == "tools/call"
        assert msg.params == {"name": "test"}
        assert msg.id == 5


class TestJSONRPCResponse:
    def test_success_response(self):
        resp = JSONRPCResponse(result={"status": "ok"}, id=1)
        assert resp.jsonrpc == "2.0"
        assert resp.result == {"status": "ok"}
        assert resp.error is None
        assert resp.id == 1

    def test_serialization(self):
        resp = JSONRPCResponse(result=[1, 2, 3], id=1)
        raw = serialize_message(resp)
        data = json.loads(raw)
        assert data["jsonrpc"] == "2.0"
        assert data["result"] == [1, 2, 3]
        assert "error" not in data
        assert data["id"] == 1

    def test_deserialization(self):
        raw = json.dumps({"jsonrpc": "2.0", "result": {"message": "hello"}, "id": 1})
        msg = parse_message(raw)
        assert isinstance(msg, JSONRPCResponse)
        assert msg.result == {"message": "hello"}
        assert msg.error is None

    def test_null_id_response(self):
        """A response can have null id for notifications."""
        resp = JSONRPCResponse(result=True, id=None)
        raw = serialize_message(resp)
        data = json.loads(raw)
        assert data["id"] is None


class TestJSONRPCError:
    def test_error_with_standard_code(self):
        err = JSONRPCError(code=JSONRPCErrorCode.METHOD_NOT_FOUND, message="Method not found", id=1)
        assert err.code == -32601
        assert err.message == "Method not found"
        assert err.id == 1

    def test_error_with_data(self):
        err = JSONRPCError(
            code=JSONRPCErrorCode.INVALID_PARAMS,
            message="Invalid params",
            data={"details": "missing field 'name'"},
            id=2,
        )
        assert err.data == {"details": "missing field 'name'"}

    def test_error_serialization(self):
        err = JSONRPCError(code=JSONRPCErrorCode.PARSE_ERROR, message="Parse error", id=None)
        raw = serialize_message(err)
        data = json.loads(raw)
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32700
        assert data["error"]["message"] == "Parse error"
        assert "result" not in data
        assert data["id"] is None

    def test_error_deserialization(self):
        raw = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": "Internal error", "data": {"trace": "abc"}},
            "id": 1,
        })
        msg = parse_message(raw)
        assert isinstance(msg, JSONRPCError)
        assert msg.code == -32603
        assert msg.message == "Internal error"
        assert msg.data == {"trace": "abc"}

    def test_to_response_conversion(self):
        err = JSONRPCError(code=JSONRPCErrorCode.INTERNAL_ERROR, message="Something broke", id=5)
        raw = serialize_message(err)
        data = json.loads(raw)
        assert data["error"]["code"] == -32603
        assert data["id"] == 5


class TestJSONRPCNotification:
    def test_notification_no_id(self):
        notif = JSONRPCNotification(method="$/progress", params={"progress": 50, "total": 100})
        assert notif.jsonrpc == "2.0"
        assert notif.method == "$/progress"
        assert notif.id is None

    def test_notification_serialization(self):
        notif = JSONRPCNotification(method="notify", params={"msg": "hello"})
        raw = serialize_message(notif)
        data = json.loads(raw)
        assert "id" not in data
        assert data["method"] == "notify"

    def test_notification_deserialization(self):
        raw = json.dumps({"jsonrpc": "2.0", "method": "$/cancelled", "params": {"id": 3}})
        msg = parse_message(raw)
        assert isinstance(msg, JSONRPCNotification)
        assert msg.method == "$/cancelled"


class TestParseErrors:
    def test_invalid_json(self):
        with pytest.raises(JSONRPCError) as exc_info:
            parse_message("not-json")
        assert exc_info.value.code == JSONRPCErrorCode.PARSE_ERROR

    def test_missing_jsonrpc_field(self):
        with pytest.raises(JSONRPCError) as exc_info:
            parse_message(json.dumps({"method": "test", "id": 1}))
        assert exc_info.value.code == JSONRPCErrorCode.INVALID_REQUEST

    def test_wrong_version(self):
        with pytest.raises(JSONRPCError) as exc_info:
            parse_message(json.dumps({"jsonrpc": "1.0", "method": "test", "id": 1}))
        assert exc_info.value.code == JSONRPCErrorCode.INVALID_REQUEST

    def test_missing_method(self):
        with pytest.raises(JSONRPCError) as exc_info:
            parse_message(json.dumps({"jsonrpc": "2.0", "id": 1}))
        assert exc_info.value.code == JSONRPCErrorCode.INVALID_REQUEST

    def test_both_result_and_error(self):
        """A valid message has either result or error, not both."""
        with pytest.raises(JSONRPCError) as exc_info:
            parse_message(json.dumps({
                "jsonrpc": "2.0",
                "result": "ok",
                "error": {"code": -1, "message": "err"},
                "id": 1,
            }))
        assert exc_info.value.code == JSONRPCErrorCode.INVALID_REQUEST


class TestErrorCodes:
    def test_parse_error_code(self):
        assert JSONRPCErrorCode.PARSE_ERROR == -32700

    def test_invalid_request_code(self):
        assert JSONRPCErrorCode.INVALID_REQUEST == -32600

    def test_method_not_found_code(self):
        assert JSONRPCErrorCode.METHOD_NOT_FOUND == -32601

    def test_invalid_params_code(self):
        assert JSONRPCErrorCode.INVALID_PARAMS == -32602

    def test_internal_error_code(self):
        assert JSONRPCErrorCode.INTERNAL_ERROR == -32603
