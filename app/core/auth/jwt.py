"""JWT token creation and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from app.config import settings

from .models import AppID, Role, TokenPayload, UserClaims

ALGORITHM = "HS256"


def create_token(
    user_id: str,
    org_id: str = "default",
    app_id: AppID = AppID.HQ,
    role: Role = Role.ADMIN,
    expire_minutes: int = 60,
) -> str:
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "app_id": app_id.value,
        "role": role.value,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> UserClaims:
    data = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    return UserClaims(
        user_id=data["sub"],
        org_id=data["org_id"],
        app_id=AppID(data["app_id"]),
        role=Role(data.get("role", "member")),
    )
