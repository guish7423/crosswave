"""Auth API — login, token refresh, verify."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .jwt import create_token, verify_token
from .middleware import require_jwt
from .models import AppID, Role, UserClaims

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    app_id: AppID


@router.post("/login")
async def login(req: LoginRequest) -> TokenResponse:
    if req.username == "admin" and req.password == "admin":
        token = create_token(user_id="admin")
        return TokenResponse(access_token=token, user_id="admin", app_id=AppID.HQ)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/verify")
async def verify(user: UserClaims = Depends(require_jwt)) -> UserClaims:
    return user
