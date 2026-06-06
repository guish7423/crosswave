"""CrossBridge BFF — proxies to CrossBridge API service."""

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth.middleware import require_jwt
from app.core.auth.models import AppID, UserClaims

router = APIRouter(prefix="/bridge", tags=["crossbridge"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": "CrossBridge BFF"}


@router.get("/status")
async def status(user: UserClaims = Depends(require_jwt)):
    return {"app": "CrossBridge", "version": "0.1.0", "status": "operational"}
