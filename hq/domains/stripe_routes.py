"""Stripe Payment Infrastructure — Webhook + Checkout Session."""

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import AppError

router = APIRouter(prefix="/api/hq/payments", tags=["payments"])


class CreateCheckoutRequest(BaseModel):
    price_id: str
    success_url: str = "http://localhost:9999/"
    cancel_url: str = "http://localhost:9999/"


@router.post("/create-checkout-session")
async def create_checkout_session(data: CreateCheckoutRequest):
    """Create a Stripe Checkout Session."""
    if not settings.stripe_secret_key:
        raise AppError(message="Stripe not configured", code="STRIPE_NOT_CONFIGURED", status=503)
    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": data.price_id, "quantity": 1}],
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )
        return {"url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        raise AppError(message=str(e), code="STRIPE_ERROR", status=500)


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    if not settings.stripe_webhook_secret:
        raise AppError(message="Stripe webhook not configured", code="STRIPE_NOT_CONFIGURED", status=503)
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # TODO: handle order fulfillment — this will be product-specific in Phase 4+
        print(f"Payment completed: session={session.get('id')}, amount={session.get('amount_total')}")

    return {"received": True}
