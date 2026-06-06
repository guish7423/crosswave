"""Test configuration for HQ Bridge API tests.

Provides proper pytest fixtures (not module-level singletons) for
clean test isolation.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("POLSIA_DB", "/tmp/crosswave-test-polsia.db")
os.environ.setdefault("HQ_AUTH_TOKEN", "test-hq-token")
# Disable NocoBase in tests → API routes return empty data
os.environ["NB_DISABLED"] = "true"

_root_dir = str(Path(__file__).resolve().parent.parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

_hq_dir = str(Path(__file__).resolve().parent.parent)
if _hq_dir not in sys.path:
    sys.path.insert(0, _hq_dir)


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from server import create_app  # noqa: E402


@pytest.fixture
def app():
    """Fresh app instance per test (no lifecycle or shared state leaks)."""
    return create_app()


@pytest.fixture
def client(app):
    """TestClient wrapping a fresh app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Auth headers for HQ API endpoints."""
    return {"X-HQ-Token": os.environ["HQ_AUTH_TOKEN"]}


@pytest.fixture
def auth_client(client, auth_headers):
    """TestClient subclass that auto-adds X-HQ-Token."""
    orig_get = client.get
    orig_post = client.post
    orig_put = client.put

    def _get(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_get(url, **kw)

    def _post(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_post(url, **kw)

    def _put(url, **kw):
        kw.setdefault("headers", {}).update(auth_headers)
        return orig_put(url, **kw)

    client.get = _get
    client.post = _post
    client.put = _put
    return client


# NB_DISABLED=true means all tests run with NocoBase unavailable,
# testing the empty-data path.


