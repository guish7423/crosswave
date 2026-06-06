"""CrossDeploy BFF — direct DB access to CrossDeploy service."""

from fastapi import APIRouter, Depends
from app.core.auth.middleware import require_jwt
from app.core.auth.models import AppID, UserClaims
from hq.crossdeploy_client import get_deployment_orders, get_deployment_tiers

router = APIRouter(prefix="/deploy", tags=["crossdeploy"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": "CrossDeploy BFF"}
