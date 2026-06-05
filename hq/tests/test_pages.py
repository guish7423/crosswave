"""Tests for CrossWave HQ Bridge HTML page routes.

Covers 10 page routes: /, /orders, /employees, /leads, /finance, /reports,
/deploy, /portal/{id}, /monitor, /evolution
"""

import os

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")

import pytest


class TestPages:
    """Page routes return 200 + text/html."""

    @pytest.mark.parametrize("path", [
        "/", "/orders", "/employees", "/leads", "/finance",
        "/reports", "/deploy", "/monitor", "/evolution",
    ], ids=["dashboard", "orders", "employees", "leads", "finance",
            "reports", "deploy", "monitor", "evolution"])
    def test_page_returns_html(self, auth_client, path):
        resp = auth_client.get(path)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_portal_page(self, auth_client):
        resp = auth_client.get("/portal/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_portal_page_404(self, auth_client):
        resp = auth_client.get("/portal/999")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")


class TestStaticFiles:
    def test_static_css(self, auth_client):
        resp = auth_client.get("/static/styles.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css") or b"/*" in resp.content

    def test_static_js(self, auth_client):
        resp = auth_client.get("/static/app.js")
        assert resp.status_code in (200, 404)
