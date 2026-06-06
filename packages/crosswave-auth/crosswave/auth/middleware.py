"""Shared JWT auth middleware — injects UserClaims into request state."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt import verify_token
from .models import UserClaims

bearer = HTTPBearer(auto_error=False)


async def require_jwt(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UserClaims:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        claims = verify_token(credentials.credentials)
        request.state.user = claims
        return claims
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


async def optional_jwt(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UserClaims | None:
    if credentials is None:
        return None
    try:
        claims = verify_token(credentials.credentials)
        request.state.user = claims
        return claims
    except Exception:
        return None
