"""HQ Auth Routes — Admin Login Page + Session Management."""

import os

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel

from app.config import settings

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render admin login page."""
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login")
async def login(data: LoginRequest):
    """Authenticate admin and set session cookie."""
    if data.username != settings.admin_username:
        raise HTTPException(401, "Invalid credentials")
    if not settings.admin_password_hash:
        raise HTTPException(401, "Invalid credentials")
    if not bcrypt.checkpw(data.password.encode(), settings.admin_password_hash.encode()):
        raise HTTPException(401, "Invalid credentials")
    session_token = serializer.dumps({"username": data.username})
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(key="session", value=session_token, max_age=86400, httponly=True, samesite="lax")
    return resp


@router.post("/logout")
async def logout():
    """Clear session cookie."""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(key="session")
    return resp
