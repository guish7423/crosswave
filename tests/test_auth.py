"""Tests for shared auth (app/core/auth/)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestAuth:
    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_verify_valid_token(self, client):
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = login.json()["access_token"]
        resp = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "admin"

    def test_verify_no_token(self, client):
        resp = client.get("/api/auth/verify")
        assert resp.status_code == 401
