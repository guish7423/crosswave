"""NocoBase dashboard data routes — read path for NocoBase (PostgreSQL)."""

from fastapi import APIRouter
from hq.nocobase_client import get_stats, list_all

router = APIRouter(tags=["nocobase"])


@router.get("/api/hq/nocobase/stats")
async def nocobase_stats():
    """Get summary counts from NocoBase collections."""
    try:
        return await get_stats()
    except Exception as e:
        return {"status": "disconnected", "error": str(e)[:200]}


@router.get("/api/hq/nocobase/employees")
async def nocobase_employees():
    """List employees from NocoBase."""
    try:
        employees = await list_all("employees")
        return {"data": employees, "total": len(employees)}
    except Exception as e:
        return {"data": [], "total": 0, "error": str(e)[:200]}


@router.get("/api/hq/nocobase/orders")
async def nocobase_orders():
    """List external orders from NocoBase."""
    try:
        orders = await list_all("external_orders")
        return {"data": orders, "total": len(orders)}
    except Exception as e:
        return {"data": [], "total": 0, "error": str(e)[:200]}
