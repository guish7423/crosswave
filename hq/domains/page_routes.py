"""HQ page routes — serve HTML pages."""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

_HQ_DIR = Path(__file__).resolve().parent.parent

router = APIRouter(tags=["pages"])


@router.get("/", response_class=FileResponse)
async def dashboard():
    return FileResponse(os.path.join(_HQ_DIR, "dashboard.html"))

@router.get("/dashboard")
async def dashboard_alias():
    return FileResponse(os.path.join(_HQ_DIR, "dashboard.html"))


@router.get("/employees")
async def employees_page():
    return FileResponse(os.path.join(_HQ_DIR, "employees.html"))


@router.get("/orders")
async def orders_page():
    return FileResponse(os.path.join(_HQ_DIR, "orders.html"))


@router.get("/finance")
async def finance_page():
    return FileResponse(os.path.join(_HQ_DIR, "finances.html"))


@router.get("/reports")
async def reports_page():
    return FileResponse(os.path.join(_HQ_DIR, "reports.html"))


@router.get("/leads")
async def leads_page():
    return FileResponse(os.path.join(_HQ_DIR, "leads.html"))


@router.get("/deploy")
async def deploy_page():
    return FileResponse(os.path.join(_HQ_DIR, "deploy.html"))


@router.get("/monitor")
async def monitor_page():
    return FileResponse(os.path.join(_HQ_DIR, "monitor.html"))


@router.get("/evolution")
async def evolution_page():
    return FileResponse(os.path.join(_HQ_DIR, "evolution.html"))


@router.get("/model-router")
async def model_router_page():
    return FileResponse(os.path.join(_HQ_DIR, "model_router.html"))


@router.get("/portal/{order_id}")
async def portal_page(order_id: int):
    return FileResponse(os.path.join(_HQ_DIR, "portal.html"))
