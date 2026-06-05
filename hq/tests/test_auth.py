"""Tests for admin login / logout and session auth."""

import os

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from hq.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class TestLoginPage:
    def test_login_page_returns_html(self, client):
        """GET /login should render the login page."""
        resp = client.get("/login")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert b"Login" in resp.content

    def test_login_page_is_public(self, client):
        """Login page should be accessible without X-HQ-Token."""
        resp = client.get("/login", headers={})
        assert resp.status_code == 200


class TestLogin:
    def test_wrong_username_returns_401(self, client):
        """POST /login with bad username should return 401."""
        resp = client.post("/login", json={"username": "bad", "password": "bad"})
        assert resp.status_code == 401

    def test_wrong_password_returns_401(self, client):
        """POST /login with bad password should return 401."""
        with patch("app.config.settings.admin_username", "admin"), \
             patch("app.config.settings.admin_password_hash", "a_non_empty_hash_str"), \
             patch("bcrypt.checkpw", return_value=False):
            resp = client.post("/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_success_redirects_and_sets_cookie(self, client):
        """POST /login with valid creds should redirect and set session cookie."""
        with patch("app.config.settings.admin_username", "admin"), \
             patch("app.config.settings.admin_password_hash", "a_non_empty_hash_str"), \
             patch("bcrypt.checkpw", return_value=True):
            resp = client.post("/login", json={"username": "admin", "password": "correct"},
                               follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"
        assert "session" in resp.cookies

    def test_login_empty_hash_returns_401(self, client):
        """POST /login when no password hash is configured should return 401."""
        with patch("app.config.settings.admin_username", "admin"), \
             patch("app.config.settings.admin_password_hash", ""):
            resp = client.post("/login", json={"username": "admin", "password": "any"})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_cookie(self, client):
        """POST /logout should clear session cookie and redirect."""
        resp = client.post("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/login"
        set_cookie = resp.headers.get("set-cookie", "")
        assert "session=" in set_cookie
        assert "Max-Age=0" in set_cookie or "expires" in set_cookie.lower()
