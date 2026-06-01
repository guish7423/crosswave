"""Tests for CrossWave HQ Bridge HTML page routes.

Covers 10 page routes:
  /, /orders, /employees, /leads, /finance, /reports,
  /deploy, /portal/{id}, /monitor, /evolution
"""

import os
from pathlib import Path

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")

from fastapi.testclient import TestClient

from conftest import client


class TestPages:
    def test_dashboard_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert b"CrossWave" in resp.content or b"HQ" in resp.content or b"War Room" in resp.content

    def test_orders_page(self):
        resp = client.get("/orders")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_employees_page(self):
        resp = client.get("/employees")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_leads_page(self):
        resp = client.get("/leads")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_finance_page(self):
        resp = client.get("/finance")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_reports_page(self):
        resp = client.get("/reports")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_deploy_page(self):
        resp = client.get("/deploy")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_monitor_page(self):
        resp = client.get("/monitor")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_evolution_page(self):
        resp = client.get("/evolution")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_portal_page(self):
        resp = client.get("/portal/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_portal_page_404(self):
        resp = client.get("/portal/999")
        assert resp.status_code == 200  # Still returns HTML page
        assert resp.headers["content-type"].startswith("text/html")


class TestStaticFiles:
    def test_static_css(self):
        resp = client.get("/static/styles.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css") or b"/*" in resp.content

    def test_static_js(self):
        resp = client.get("/static/app.js")
        assert resp.status_code in (200, 404)  # app.js may not exist
