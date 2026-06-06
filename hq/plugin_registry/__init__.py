"""Plugin Registry — CrossWave product/service registry (Phase B).

Exports:
  - PluginRegistry      — in-memory registry with health check
  - get_registry()      — singleton factory
  - PluginInfo          — pydantic model
  - PluginStatus        — online / offline / degraded / unknown
"""

from .models import PluginInfo, PluginStatus
from .registry import PluginRegistry, get_registry

__all__ = ["PluginInfo", "PluginRegistry", "PluginStatus", "get_registry"]
