"""Tests for MCP service integration."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestMCPServiceRoutes:
    def test_mcp_message_endpoint(self):
        """Message endpoint accepts JSON-RPC requests, returns 202 (SSE)."""
        resp = client.post(
            "/mcp/message",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
        # Per MCP spec, responses are delivered via SSE stream, HTTP returns 202
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"

    def test_mcp_invalid_request(self):
        """Invalid JSON-RPC request returns error."""
        resp = client.post(
            "/mcp/message",
            json={"method": "ping", "id": 1},  # missing jsonrpc field
        )
        assert resp.status_code == 200  # JSON-RPC error response, not HTTP error
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32600  # Invalid Request

    def test_mcp_parse_error(self):
        """Malformed JSON returns parse error."""
        resp = client.post(
            "/mcp/message",
            content=b"not-json-at-all",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32700  # Parse Error

    def test_mcp_unknown_method(self):
        """Unknown method returns 202 (error sent via SSE)."""
        resp = client.post(
            "/mcp/message",
            json={"jsonrpc": "2.0", "method": "unknown/method", "id": 1},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"

    def test_mcp_notification_no_response(self):
        """Notifications should return 202."""
        resp = client.post(
            "/mcp/message",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        # Notifications return 202 with accepted status
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"

    def test_mcp_health(self):
        """Health endpoint works."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
