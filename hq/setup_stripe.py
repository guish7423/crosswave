"""
CrossWave Stripe Product Setup
Usage: STRIPE_SECRET_KEY=sk_live_xxx python setup_stripe.py

Creates all products and prices in Stripe for:
  - CrossBridge SaaS (Free/Starter/Pro)
  - CrossDeploy Services (Basic/Standard/Enterprise)
  - CrossBlog Pro (optional)

Output: Environment variables to paste into production .env
"""
import os
import sys

try:
    import stripe
except ImportError:
    os.system(f"{sys.executable} -m pip install stripe")
    import stripe


PRODUCTS = {
    "crossbridge_free": {"name": "CrossBridge - Free", "description": "AI content bridge — 10 translations/month", "type": "service"},
    "crossbridge_starter": {"name": "CrossBridge - Starter", "description": "100 translations/month + multi-platform", "type": "service"},
    "crossbridge_pro": {"name": "CrossBridge - Pro", "description": "Unlimited translations + priority support", "type": "service"},
    "crossdeploy_basic": {"name": "CrossDeploy - Basic", "description": "Single-service deployment + monitoring", "type": "service"},
    "crossdeploy_standard": {"name": "CrossDeploy - Standard", "description": "Multi-service + CI/CD + 30d support", "type": "service"},
    "crossdeploy_enterprise": {"name": "CrossDeploy - Enterprise", "description": "K8s + auto-scaling + SLA", "type": "service"},
}

PRICES = {
    "crossbridge_starter": {"currency": "cny", "unit_amount": 14900, "recurring": {"interval": "month"}},
    "crossbridge_pro": {"currency": "cny", "unit_amount": 49900, "recurring": {"interval": "month"}},
    "crossdeploy_basic": {"currency": "cny", "unit_amount": 200000, "recurring": None},
    "crossdeploy_standard": {"currency": "cny", "unit_amount": 300000, "recurring": None},
    "crossdeploy_enterprise": {"currency": "cny", "unit_amount": 500000, "recurring": None},
}


def main():
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key or key == "sk_test_..." or "placeholder" in key:
        print("ERROR: Set STRIPE_SECRET_KEY environment variable")
        print("  export STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx")
        sys.exit(1)

    stripe.api_key = key
    print(f"Stripe mode: {'LIVE' if key.startswith('sk_live') else 'TEST'}")
    print()

    output = {}
    for slug, info in PRODUCTS.items():
        print(f"Creating product: {info['name']}...")
        prod = stripe.Product.create(name=info["name"], description=info["description"])
        output[slug] = {"product_id": prod.id, "price_id": None}

        if slug in PRICES:
            pdata = PRICES[slug]
            price = stripe.Price.create(
                product=prod.id,
                currency=pdata["currency"],
                unit_amount=pdata["unit_amount"],
                recurring=pdata.get("recurring"),
            )
            output[slug]["price_id"] = price.id
            print(f"  → {prod.id} | {price.id} ({pdata['currency']} {pdata['unit_amount']/100})")
        else:
            print(f"  → {prod.id} (free tier, no price)")

    print()
    print("=" * 60)
    print("STRIPE PRODUCTS CREATED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Add these to your production .env:")
    print()

    env_map = {
        "crossbridge_starter": "CROSSBRIDGE_STARTER_PRICE",
        "crossbridge_pro": "CROSSBRIDGE_PRO_PRICE",
        "crossdeploy_basic": "CROSSDEPLOY_BASIC_PRICE",
        "crossdeploy_standard": "CROSSDEPLOY_STANDARD_PRICE",
        "crossdeploy_enterprise": "CROSSDEPLOY_ENTERPRISE_PRICE",
    }
    for slug, env_var in env_map.items():
        if slug in output and output[slug]["price_id"]:
            print(f"{env_var}={output[slug]['price_id']}")

    print()
    print("Stripe Payment Links (shareable checkout URLs):")
    print("  Create at: https://dashboard.stripe.com/payment-links/create")
    print()
    for slug, info in PRODUCTS.items():
        if slug in PRICES and slug in output:
            pid = output[slug]["price_id"]
            if pid:
                print(f"  {info['name']}: price_{pid}")


if __name__ == "__main__":
    main()
