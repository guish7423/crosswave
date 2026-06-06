# CrossWave Plugin SDK

## Overview

The Plugin SDK allows any product to integrate with CrossWave's AI OS.

## Quick Start

```python
from crosswave_plugin import CrossWavePlugin

class MyPlugin(CrossWavePlugin):
    name = "my-product"
    description = "My cool product"
    capabilities = ["ai", "api"]

    async def on_register(self):
        print(f"{self.name} registered!")

    async def health_check(self):
        return PluginStatus.ONLINE
```

## Lifecycle Hooks

| Hook | When | Purpose |
|------|------|---------|
| `on_register()` | After registration | Init connections |
| `on_unregister()` | Before removal | Cleanup resources |
| `on_heartbeat()` | Every 60s | Custom health logic |
| `health_check()` | On demand | Return status |

## MCP Tools

Plugins can expose MCP tools automatically via their capabilities list.
