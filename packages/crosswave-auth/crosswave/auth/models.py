"""Shared auth models — JWT payload, user claims."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AppID(str, Enum):
    CROSSBRIDGE = "crossbridge"
    CROSSBLOG = "crossblog"
    CROSSDEPLOY = "crossdeploy"
    HQ = "hq"
    POLSIA = "polsia"


class Role(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TokenPayload(BaseModel):
    sub: str
    org_id: str
    app_id: AppID
    role: Role = Role.MEMBER
    exp: datetime


class UserClaims(BaseModel):
    user_id: str
    org_id: str
    app_id: AppID
    role: Role
