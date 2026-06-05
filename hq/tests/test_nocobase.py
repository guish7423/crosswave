"""Tests for NocoBase dashboard data routes."""




class TestNocoBaseEndpoints:
    """Verify NocoBase endpoints gracefully handle missing/offline NocoBase."""

    def test_nocobase_stats_disconnected(self, auth_client):
        """When NocoBase is unreachable, returns status: disconnected."""
        resp = auth_client.get("/api/hq/nocobase/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("disconnected", "connected")

    def test_nocobase_employees_disconnected(self, auth_client):
        """When NocoBase is unreachable, returns empty data."""
        resp = auth_client.get("/api/hq/nocobase/employees")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("data"), list)

    def test_nocobase_orders_disconnected(self, auth_client):
        """When NocoBase is unreachable, returns empty data."""
        resp = auth_client.get("/api/hq/nocobase/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("data"), list)
