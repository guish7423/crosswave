"""Tests for Plugin Registry."""

from hq.plugin_registry import get_registry
from hq.plugin_registry.models import PluginRegisterRequest, PluginStatus


class TestPluginRegistry:
    def setup_method(self):
        self.registry = get_registry()

    def test_register_plugin(self):
        req = PluginRegisterRequest(name="TestService", description="A test", capabilities=["test"])
        info = self.registry.register(req)
        assert info.name == "TestService"
        assert info.id in self.registry._plugins

    def test_get_plugin(self):
        req = PluginRegisterRequest(name="GetTest", capabilities=["test"])
        info = self.registry.register(req)
        got = self.registry.get(info.id)
        assert got is not None
        assert got.name == "GetTest"

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_list_plugins(self):
        plugins = self.registry.list()
        assert isinstance(plugins, list)

    def test_heartbeat(self):
        req = PluginRegisterRequest(name="HeartbeatTest", capabilities=["test"])
        info = self.registry.register(req)
        assert info.status == PluginStatus.UNKNOWN
        updated = self.registry.heartbeat(info.id)
        assert updated is not None
        assert updated.status == PluginStatus.ONLINE
        assert updated.last_heartbeat is not None

    def test_heartbeat_nonexistent(self):
        assert self.registry.heartbeat("nope") is None

    def test_unregister(self):
        req = PluginRegisterRequest(name="RemoveMe", capabilities=["test"])
        info = self.registry.register(req)
        assert self.registry.unregister(info.id) is True
        assert self.registry.get(info.id) is None

    def test_unregister_nonexistent(self):
        assert self.registry.unregister("nope") is False

    def test_get_by_capability(self):
        req = PluginRegisterRequest(name="CapTest", capabilities=["abc", "xyz"])
        info = self.registry.register(req)
        matches = self.registry.get_by_capability("abc")
        assert any(p.id == info.id for p in matches)
        assert self.registry.get_by_capability("nonexistent") == []
