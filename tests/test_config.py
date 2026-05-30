"""Tests for CrossWave configuration."""

from app.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.polsia_base_url is not None
    assert s.polsia_api_key is not None
    assert s.proxy_timeout == 5
    assert s.polsia_mock is True


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("POLSIA_BASE_URL", "https://test.example.com")
    monkeypatch.setenv("POLSIA_API_KEY", "test-key-123")
    monkeypatch.setenv("POLSIA_MOCK", "false")
    s = Settings()
    assert s.polsia_base_url == "https://test.example.com"
    assert s.polsia_api_key == "test-key-123"
    assert s.polsia_mock is False
