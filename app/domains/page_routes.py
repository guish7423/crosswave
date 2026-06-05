"""Page routes for CrossWave main site."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.polsia_client import polsia_client

router = APIRouter(tags=["pages"])

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates_root = Jinja2Templates(directory=str(PROJECT_ROOT))


@router.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    return """User-agent: *
Allow: /

Sitemap: https://crosswave.app/sitemap.xml
"""


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates_root.TemplateResponse(request, "index.html", {"request": request})


@router.get("/deploy", response_class=HTMLResponse)
async def deploy_service(request: Request):
    return templates.TemplateResponse(request, "deploy-service.html")


@router.get("/request-quote", response_class=HTMLResponse)
async def request_quote(request: Request):
    return templates.TemplateResponse(
        request, "request-quote.html", {"request": request}
    )


@router.get("/quote/{view_token}", response_class=HTMLResponse)
async def quote_view(request: Request, view_token: str):
    proposal = await polsia_client.get_proposal_by_token(view_token)
    if isinstance(proposal, dict) and proposal.get("id") is not None:
        return templates.TemplateResponse(
            request,
            "quote-view.html",
            {"request": request, "proposal": proposal},
        )
    return templates.TemplateResponse(
        request,
        "quote-view.html",
        {
            "request": request,
            "proposal": None,
            "error": "Proposal not found or expired.",
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    summary = await polsia_client.get_dashboard_summary()
    agents = await polsia_client.get_agents_status()
    activity = await polsia_client.get_activity(limit=15)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "summary": summary if isinstance(summary, dict) else {},
            "agents": agents if isinstance(agents, list) else [],
            "activity": activity if isinstance(activity, list) else [],
        },
    )


@router.get("/agents", response_class=HTMLResponse)
async def agent_status(request: Request):
    agents = await polsia_client.get_agents_status()
    activity = await polsia_client.get_activity(limit=30)
    return templates.TemplateResponse(
        request,
        "agents.html",
        {
            "request": request,
            "agents": agents if isinstance(agents, list) else [],
            "activity": activity if isinstance(activity, list) else [],
        },
    )
