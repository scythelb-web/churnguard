"""Billing routes — for charging OUR customers."""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.routers.auth import get_current_user
from app.config import STRIPE_SECRET_KEY
from app.services.billing import create_checkout_session, create_customer

router = APIRouter(prefix="/billing", tags=["billing"])

# These would be actual Stripe Price IDs in production
PRICE_IDS = {
    "starter": "price_starter",
    "growth": "price_growth",
    "scale": "price_scale",
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

    price_id = PRICE_IDS.get(plan, PRICE_IDS["growth"])
    session = create_checkout_session(
        customer_id=user["stripe_customer_id"],
        price_id=price_id,
        success_url=f"{request.base_url}dashboard?subscribed=1",
        cancel_url=f"{request.base_url}billing/upgrade",
    )
    return RedirectResponse(session.url, status_code=303)
