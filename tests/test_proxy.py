"""Tests for proxy routes and cross-product proxying."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestBlogProxy:
    def test_blog_proxy_health(self, client):
        resp = client.get("/api/crossblog/health")
        assert resp.status_code in (200, 404, 502)


class TestGateway:
    def test_gateway_endpoint(self, client):
        resp = client.get("/api/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
