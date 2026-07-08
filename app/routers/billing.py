"""Billing routes — Stripe Checkout for subscriptions."""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.routers.auth import get_current_user
from app.config import STRIPE_SECRET_KEY
from app.database import get_db

router = APIRouter(prefix="/billing", tags=["billing"])

# These get replaced with real Stripe Price IDs from your dashboard
# Create them at: https://dashboard.stripe.com/products
PRICE_IDS = {
    "starter": "price_1Tqiv6Ih3bqeW0wSm6qAaNtD",
    "growth": "price_1TqivSIh3bqeW0wSvhLAfKet",
    "scale": "price_1TqivjIh3bqeW0wSHsmQjXAp",
}


@router.get("/upgrade")
async def upgrade_page(request: Request, plan: str = "growth"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "pricing.html",
        {"request": request, "user": user, "selected": plan},
    )


@router.post("/subscribe/{plan}")
async def subscribe(request: Request, plan: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)

    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured"}

    price_id = PRICE_IDS.get(plan)
    if not price_id or "REPLACE" in price_id:
        return {"error": f"Price ID not configured for plan: {plan}. Create it in your Stripe dashboard."}

    # Ensure user has a Stripe customer ID
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        try:
            import stripe as _stripe
            _stripe.api_key = STRIPE_SECRET_KEY
            customer = _stripe.Customer.create(email=user["email"])
            customer_id = customer["id"]
            with get_db() as db:
                db.execute(
                    "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                    (customer_id, user["id"]),
                )
        except Exception as e:
            return {"error": f"Failed to create Stripe customer: {str(e)}"}

    import stripe as _stripe
    _stripe.api_key = STRIPE_SECRET_KEY

    try:
        session = _stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{request.base_url}dashboard?subscribed=1",
            cancel_url=f"{request.base_url}billing/upgrade",
        )
        return RedirectResponse(session.url, status_code=303)
    except Exception as e:
        return {"error": f"Checkout failed: {str(e)}"}
