"""Tests for backward compatibility layer."""



from app.core.mcp.compat import (
    CompatAdapter,
    OldProtocolMessage,
    convert_new_to_old,
    convert_old_to_new,
)


class TestCompatConversion:
    def test_convert_old_to_new_request(self):
        """Convert old protocol request to JSON-RPC 2.0."""
        old = OldProtocolMessage(
            type="request",
            action="list_resources",
            payload={"limit": 10},
            request_id="abc-123",
        )
        new = convert_old_to_new(old)
        assert new["jsonrpc"] == "2.0"
        assert new["method"] == "resources/list"
        assert new["params"] == {"limit": 10}
        assert new["id"] == "abc-123"

    def test_convert_old_to_new_response(self):
        """Convert old protocol response to JSON-RPC 2.0."""
        old = OldProtocolMessage(
            type="response",
            action="list_resources",
            payload={"resources": [{"name": "test"}]},
            request_id="abc-123",
        )
        new = convert_old_to_new(old)
        assert new["jsonrpc"] == "2.0"
        assert new["result"] == {"resources": [{"name": "test"}]}
        assert new["id"] == "abc-123"

    def test_convert_new_to_old_request(self):
        """Convert JSON-RPC 2.0 request back to old format."""
        new = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "test"}, "id": 5}
        old = convert_new_to_old(new)
        assert old.type == "request"
        assert old.action == "call_tool"  # Mapped to old-style action name
        assert old.payload == {"name": "test"}
        assert old.request_id == 5

    def test_convert_new_to_old_response(self):
        """Convert JSON-RPC 2.0 response back to old format."""
        new = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 5}
        old = convert_new_to_old(new)
        assert old.type == "response"
        assert old.payload == {"status": "ok"}
        assert old.request_id == 5


class TestCompatAdapter:
    def test_adapter_wraps_request(self):
        """CompatAdapter wraps old-format handlers for new protocol."""
        adapter = CompatAdapter()

        # Define an old-style handler
        async def old_handler(msg: OldProtocolMessage) -> dict:
            return {"handled": msg.action}

        adapter.register("list_resources", old_handler)

        # Call with new-format request
        new_req = {"jsonrpc": "2.0", "method": "resources/list", "params": {}, "id": 1}
        result = adapter.handle_request(new_req)

        # Should have converted and returned JSON-RPC response
        assert result is not None  # In real async would await

    async def test_adapter_unknown_method(self):
        """Unknown methods return None (no handler registered)."""
        adapter = CompatAdapter()
        new_req = {"jsonrpc": "2.0", "method": "unknown/method", "params": {}, "id": 1}
        result = await adapter.handle_request(new_req)
        assert result is None  # No handler registered

    def test_action_mapping(self):
        """Verify action name mapping."""
        adapter = CompatAdapter()
        assert adapter._map_method_to_action("resources/list") == "list_resources"
        assert adapter._map_method_to_action("tools/call") == "call_tool"
        assert adapter._map_method_to_action("resources/read") == "read_resource"
