"""CrossDeploy — FastAPI deployment order management service."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr

from .models import (
    DeployOrder,
    OrderStatus,
    OrderTier,
    SessionLocal,
    TIER_PRICES,
    TIER_PRODUCTS,
    init_db,
)


# ── Pydantic Schemas ────────────────────────────────────────────

class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    company: str = ""
    tier: OrderTier
    notes: str = ""


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_email: str
    company: str
    tier: OrderTier
    status: OrderStatus
    price: int
    product_label: str
    notes: str
    stripe_session_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class CheckoutCreate(BaseModel):
    order_id: int
    success_url: str
    cancel_url: str


class CheckoutOut(BaseModel):
    url: str
    session_id: str


# ── FastAPI App ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CrossDeploy API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Routes ──────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "crossdeploy", "orders": get_order_count()}


def get_order_count() -> int:
    db = SessionLocal()
    try:
        return db.query(DeployOrder).count()
    finally:
        db.close()


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(status: Optional[OrderStatus] = None):
    db = SessionLocal()
    try:
        q = db.query(DeployOrder)
        if status:
            q = q.filter(DeployOrder.status == status)
        return q.order_by(DeployOrder.created_at.desc()).all()
    finally:
        db.close()


@app.post("/api/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate):
    db = SessionLocal()
    try:
        order = DeployOrder(
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            company=payload.company,
            tier=payload.tier,
            notes=payload.notes,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order
    finally:
        db.close()


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int):
    db = SessionLocal()
    try:
        order = db.query(DeployOrder).filter(DeployOrder.id == order_id).first()
        if not order:
            raise HTTPException(404, "Order not found")
        return order
    finally:
        db.close()


@app.patch("/api/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: int, payload: OrderStatusUpdate):
    db = SessionLocal()
    try:
        order = db.query(DeployOrder).filter(DeployOrder.id == order_id).first()
        if not order:
            raise HTTPException(404, "Order not found")
        order.status = payload.status
        db.commit()
        db.refresh(order)
        return order
    finally:
        db.close()


@app.get("/api/tiers")
def list_tiers():
    """Return available deployment tiers with pricing."""
    return {
        "tiers": [
            {
                "id": t.value,
                "name": t.name.capitalize(),
                "price": TIER_PRICES[t],
                "product": TIER_PRODUCTS[t],
                "description": TIER_DESCRIPTIONS[t],
            }
            for t in OrderTier
        ]
    }


TIER_DESCRIPTIONS = {
    OrderTier.basic: "Single product deployment — CrossBridge or CrossBlog with SSL + CI",
    OrderTier.standard: "Two product deployment — CrossBridge + CrossBlog with PostgreSQL + monitoring",
    OrderTier.enterprise: "Full Polsia Fork 10-agent platform deployment with dedicated infra",
}


# ── Entry ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
