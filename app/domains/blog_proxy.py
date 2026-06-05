"""CrossBlog proxy routes — proxying blog data from CrossBlog API."""

from urllib.parse import quote

import httpx
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/v1/_proxy/blog", tags=["blog"])


async def _fetch_blog(path: str) -> dict | list:
    """Fetch from CrossBlog JSON API with timeout + fallback."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.crossblog_url}{path}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"posts": []} if "posts" in path else []


@router.get("/latest")
async def proxy_blog_latest():
    """Proxy popular blog posts from CrossBlog API."""
    result = await _fetch_blog("/api/posts/popular")
    return {"posts": result if isinstance(result, list) else []}


@router.get("/recent")
async def proxy_blog_recent(limit: int = 6):
    """Proxy recent blog posts."""
    result = await _fetch_blog(f"/api/posts/recent?limit={limit}")
    return {"posts": result if isinstance(result, list) else []}


@router.get("/by-tag/{tag}")
async def proxy_blog_by_tag(tag: str):
    """Proxy blog posts filtered by tag."""
    result = await _fetch_blog(f"/api/posts/by-tag/{quote(tag)}")
    return {"posts": result if isinstance(result, list) else []}


@router.get("/tags")
async def proxy_blog_tags():
    """Proxy all blog tags."""
    result = await _fetch_blog("/api/tags")
    if isinstance(result, dict):
        return {"tags": result.get("tags", []), "total": result.get("total", 0)}
    return {"tags": result if isinstance(result, list) else [], "total": 0}
