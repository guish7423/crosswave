"""CrossWave — Application Factory."""

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import setup_middleware
from app.services.polsia_client import polsia_client

BASE_DIR = Path(__file__).resolve().parent

# ── Sentry init (early) ─────────────────────────────────────────────────
if settings.sentry_dsn:
    import sentry_sdk  # type: ignore[import-untyped]

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.25,
        enable_tracing=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await polsia_client.start()
    yield
    await polsia_client.stop()


def create_app() -> FastAPI:
    """Create and configure the CrossWave FastAPI application."""
    app = FastAPI(
        title="CrossWave",
        version="0.6.1",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url=None,
    )

    # ── Static files ───────────────────────────────────────────────────
    static_dir = BASE_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ── CORS ───────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers (must be before routes) ─────────────────────
    register_exception_handlers(app)

    # ── Middleware ─────────────────────────────────────────────────────
    setup_middleware(app)

    # ── Register routes from domains ───────────────────────────────────
    from app.domains.page_routes import router as page_router
    from app.domains.proxy_routes import router as proxy_router
    from app.domains.blog_proxy import router as blog_router
    from app.domains.mcp_routes import router as mcp_router

    app.include_router(page_router)
    app.include_router(proxy_router)
    app.include_router(blog_router)
    app.include_router(mcp_router)

    return app


app = create_app()
