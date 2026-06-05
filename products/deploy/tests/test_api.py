"""Tests for CrossDeploy API."""

import sys
from pathlib import Path

_test_root = Path(__file__).resolve().parent.parent
if str(_test_root) not in sys.path:
    sys.path.insert(0, str(_test_root))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import OrderStatus, OrderTier, init_db, SessionLocal, DeployOrder

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield
    db = SessionLocal()
    db.query(DeployOrder).delete()
    db.commit()
    db.close()


def seed_order(tier=OrderTier.basic, status=OrderStatus.pending):
    db = SessionLocal()
    order = DeployOrder(
        customer_name="Test User",
        customer_email="test@example.com",
        company="Test Corp",
        tier=tier,
        status=status,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    db.close()
    return order


class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestCreateOrder:
    def test_create_basic(self):
        resp = client.post("/api/orders", json={
            "customer_name": "Alice",
            "customer_email": "alice@example.com",
            "tier": "basic",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["customer_name"] == "Alice"
        assert data["tier"] == "basic"
        assert data["price"] == 2000
        assert data["status"] == "pending"

    def test_create_enterprise(self):
        resp = client.post("/api/orders", json={
            "customer_name": "Bob",
            "customer_email": "bob@example.com",
            "company": "Big Corp",
            "tier": "enterprise",
            "notes": "Need full setup",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["price"] == 5000
        assert data["product_label"] == "Polsia Fork"
        assert data["company"] == "Big Corp"

    def test_create_validation(self):
        resp = client.post("/api/orders", json={"customer_name": "", "customer_email": "bad", "tier": "invalid"})
        assert resp.status_code == 422


class TestListOrders:
    def test_list_orders(self):
        seed_order()
        resp = client.get("/api/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_list_filtered(self):
        seed_order(status=OrderStatus.pending)
        seed_order(tier=OrderTier.enterprise, status=OrderStatus.completed)
        resp = client.get("/api/orders?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert all(o["status"] == "completed" for o in data)


class TestGetOrder:
    def test_get_order(self):
        order = seed_order()
        resp = client.get(f"/api/orders/{order.id}")
        assert resp.status_code == 200
        assert resp.json()["customer_name"] == "Test User"

    def test_get_404(self):
        resp = client.get("/api/orders/999999")
        assert resp.status_code == 404


class TestUpdateStatus:
    def test_update_status(self):
        order = seed_order()
        resp = client.patch(f"/api/orders/{order.id}/status", json={"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_update_404(self):
        resp = client.patch("/api/orders/999999/status", json={"status": "completed"})
        assert resp.status_code == 404


class TestTiers:
    def test_list_tiers(self):
        resp = client.get("/api/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert "tiers" in data
        assert len(data["tiers"]) == 3
        tiers = {t["id"]: t for t in data["tiers"]}
        assert tiers["basic"]["price"] == 2000
        assert tiers["enterprise"]["price"] == 5000
