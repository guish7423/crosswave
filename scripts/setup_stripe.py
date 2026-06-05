#!/usr/bin/env python3
"""Stripe Product & Price Setup Script.

Creates products and price IDs in Stripe, then outputs .env configuration.

Usage:
    STRIPE_SECRET_KEY=sk_test_xxx python scripts/setup_stripe.py
"""

import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
if not stripe.api_key:
    raise SystemExit("Error: STRIPE_SECRET_KEY environment variable is required.")

PRODUCTS = [
    {
        "name": "CrossBridge — Starter",
        "description": "AI translation service, starter tier",
        "prices": [{"unit_amount": 1900, "currency": "usd", "interval": "month"}],
    },
    {
        "name": "CrossBridge — Pro",
        "description": "AI translation service, pro tier",
        "prices": [{"unit_amount": 4900, "currency": "usd", "interval": "month"}],
    },
    {
        "name": "CrossDeploy — Basic",
        "description": "One-time deployment service",
        "prices": [{"unit_amount": 19900, "currency": "usd", "interval": None}],
    },
    {
        "name": "CrossDeploy — Standard",
        "description": "Standard deployment package",
        "prices": [{"unit_amount": 49900, "currency": "usd", "interval": None}],
    },
    {
        "name": "CrossDeploy — Enterprise",
        "description": "Enterprise deployment package",
        "prices": [{"unit_amount": 99900, "currency": "usd", "interval": None}],
    },
]

print("# Stripe Setup — Generated Product & Price IDs")
print("# Add these to your .env file:\n")

for p in PRODUCTS:
    product = stripe.Product.create(name=p["name"], description=p["description"])
    for price_data in p["prices"]:
        kwargs: dict = {
            "unit_amount": price_data["unit_amount"],
            "currency": price_data["currency"],
            "product": product.id,
        }
        if price_data["interval"]:
            kwargs["recurring"] = {"interval": price_data["interval"]}
        price = stripe.Price.create(**kwargs)
        env_key = p["name"].upper().replace(" ", "_").replace("—", "").replace("__", "_") + "_PRICE"
        print(f"{env_key}={price.id}")
