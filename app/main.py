"""CrossWave — Unified Management Platform"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="CrossWave", version="0.2.0")

try:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
except RuntimeError:
    pass

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request})

@app.get("/agents", response_class=HTMLResponse)
async def agent_status(request: Request):
    return templates.TemplateResponse(request, "agents.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok", "app": "CrossWave", "version": "0.2.0"}
