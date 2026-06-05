"""Tests for Stripe infrastructure."""

import os

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")
os.environ.setdefault("HQ_AUTH_TOKEN", "test-hq-token")

import pytest
from fastapi.testclient import TestClient
from server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-HQ-Token": os.environ["HQ_AUTH_TOKEN"]}


def test_create_checkout_without_config_returns_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.config.settings.stripe_secret_key", "")
    resp = client.post("/api/hq/payments/create-checkout-session", json={
        "price_id": "price_test",
    }, headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["error"] == "STRIPE_NOT_CONFIGURED"


def test_webhook_without_config_returns_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.config.settings.stripe_webhook_secret", "")
    resp = client.post("/api/hq/payments/webhook", content=b"{}", headers={
        **auth_headers, "Stripe-Signature": "test",
    })
    assert resp.status_code == 503
    assert resp.json()["error"] == "STRIPE_NOT_CONFIGURED"
