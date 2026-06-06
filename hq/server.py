"""CrossWave HQ Bridge Server.

Split into domain modules under hq/domains/:
  - data.py:         Shared state (CACHE), Polsia sync, service monitor
  - middleware.py:   require_token auth, app_lifespan
  - page_routes.py:  HTML page routes (/dashboard, /employees, etc.)
  - api_routes.py:   Data API routes (/api/hq/summary, /api/hq/orders, etc.)
  - monitor_routes.py: Health, monitor, evolution, portal routes
  - model_router_routes.py: Model Router API endpoints
"""

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.exceptions import register_exception_handlers
from hq.domains.api_routes import router as api_router
from hq.domains.auth_routes import router as auth_router
from hq.domains.data import CACHE  # noqa: F401 — imported by tests
from hq.domains.middleware import app_lifespan, require_token
from hq.domains.model_router_routes import router as model_router_router
from hq.domains.monitor_routes import router as monitor_router
from hq.domains.nocobase_routes import router as nocobase_router
from hq.domains.page_routes import router as page_router
from hq.domains.stripe_routes import router as stripe_router
from hq.plugin_registry.routes import router as plugin_router
from hq.event_bus.routes import router as event_bus_router


def create_app() -> FastAPI:
    """Create the HQ Bridge FastAPI application."""
    app = FastAPI(
        title="CrossWave HQ Bridge",
        dependencies=[Depends(require_token)],
        lifespan=app_lifespan,
        docs_url=None,
        redoc_url=None,
    )

    # Exception handlers
    register_exception_handlers(app)

    # Static files
    hq_dir = Path(__file__).resolve().parent
    app.mount("/static", StaticFiles(directory=str(hq_dir)), name="hq_static")

    # Register routers
    app.include_router(page_router)
    app.include_router(api_router)
    app.include_router(monitor_router)
    app.include_router(nocobase_router)
    app.include_router(model_router_router)
    app.include_router(stripe_router)
    app.include_router(plugin_router)
    app.include_router(event_bus_router)
    app.include_router(auth_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=13001)  # noqa: S104
