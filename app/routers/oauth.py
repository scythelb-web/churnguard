"""Stripe App OAuth handler — marketplace install flow."""

import logging
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from app.database import get_db
from app.config import BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe/oauth", tags=["stripe-oauth"])


@router.get("/callback")
async def oauth_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """Handle the Stripe App OAuth install callback.

    Stripe redirects here after a user clicks 'Install' on the marketplace.
    We exchange the authorization code for an access token, then set up
    the ChurnGuard account to receive webhooks and start dunning.
    """
    if error:
        logger.error("OAuth error: %s — %s", error, error_description)
        return HTMLResponse(
            f'<p style="color:red">Installation failed: {error}</p>'
            f'<p>{error_description}</p>'
            f'<a href="{BASE_URL}">Back to ChurnGuard</a>',
            status_code=400,
        )

    if not code:
        return HTMLResponse(
            '<p style="color:red">No authorization code received.</p>'
            f'<a href="{BASE_URL}">Back to ChurnGuard</a>',
            status_code=400,
        )

    import os

    client_id = os.getenv("STRIPE_CLIENT_ID", os.getenv("STRIPE_CONNECT_CLIENT_ID", ""))
    client_secret = os.getenv("STRIPE_CLIENT_SECRET", os.getenv("STRIPE_SECRET_KEY", ""))

    if not client_id or not client_secret:
        logger.error("Stripe OAuth not configured — missing client_id or secret")
        return HTMLResponse(
            '<p style="color:red">ChurnGuard is not fully configured for Stripe App installs yet.'
            ' Please contact support.</p>'
            f'<a href="{BASE_URL}">Back to ChurnGuard</a>',
            status_code=500,
        )

    # Exchange authorization code for access token
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://connect.stripe.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_secret": client_secret,
                },
                auth=(client_id, ""),
                timeout=15,
            )
            resp.raise_for_status()
            token_data = resp.json()
    except Exception as e:
        logger.error("Token exchange failed: %s", e)
        return HTMLResponse(
            f'<p style="color:red">Failed to connect your Stripe account. Please try again.</p>'
            f'<a href="{BASE_URL}">Back to ChurnGuard</a>',
            status_code=500,
        )

    stripe_user_id = token_data.get("stripe_user_id", "")
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    stripe_publishable_key = token_data.get("stripe_publishable_key", "")

    if not stripe_user_id or not access_token:
        logger.error("OAuth response missing required fields: %s", list(token_data.keys()))
        return HTMLResponse(
            '<p style="color:red">Unexpected response from Stripe. Please try again.</p>'
            f'<a href="{BASE_URL}">Back to ChurnGuard</a>',
            status_code=500,
        )

    # Retrieve account info
    try:
        async with httpx.AsyncClient() as client:
            acct_resp = await client.get(
                "https://api.stripe.com/v1/account",
                auth=(access_token, ""),
                timeout=10,
            )
            acct_resp.raise_for_status()
            account = acct_resp.json()
    except Exception as e:
        logger.error("Account lookup failed: %s", e)
        account = {"id": stripe_user_id}

    # Get the user's email from the Stripe account
    user_email = account.get("email", "")
    if not user_email:
        # Try to get it from the settings
        user_email = account.get("settings", {}).get("dashboard", {}).get("display_name", f"stripe-{stripe_user_id[:8]}")

    # Create or update the ChurnGuard user
    with get_db() as db:
        # Check if this Stripe account is already connected
        existing = db.execute(
            "SELECT * FROM customer_stripe_accounts WHERE stripe_account_id = ?",
            (stripe_user_id,),
        ).fetchone()

        if existing:
            user_id = existing["user_id"]
            # Update the token
            db.execute(
                """UPDATE customer_stripe_accounts
                   SET access_token = ?, refresh_token = ?, stripe_publishable_key = ?
                   WHERE stripe_account_id = ?""",
                (access_token, refresh_token, stripe_publishable_key, stripe_user_id),
            )
        else:
            # Create a new user account
            import secrets
            temp_password = secrets.token_urlsafe(16)

            cursor = db.execute(
                """INSERT INTO users (email, password_hash, stripe_account_id, stripe_connect_active)
                   VALUES (?, '', ?, 1)""",
                (user_email, stripe_user_id),
            )
            user_id = cursor.lastrowid

            db.execute(
                """INSERT INTO customer_stripe_accounts
                   (user_id, stripe_account_id, access_token, refresh_token, stripe_publishable_key)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, stripe_user_id, access_token, refresh_token, stripe_publishable_key),
            )

        db.execute(
            "UPDATE users SET stripe_account_id = ?, stripe_connect_active = 1 WHERE id = ?",
            (stripe_user_id, user_id),
        )

    # Auto-register webhook endpoint
    try:
        import stripe as stripe_lib
        stripe_lib.WebhookEndpoint.create(
            url=f"{BASE_URL}/stripe/webhook",
            enabled_events=["invoice.payment_failed", "invoice.payment_succeeded"],
            api_key=access_token,
        )
        logger.info("Webhook registered for Stripe account %s", stripe_user_id)
    except Exception as e:
        logger.warning("Webhook registration failed (may already exist): %s", e)

    logger.info("Stripe account %s connected via OAuth", stripe_user_id)

    # Redirect to dashboard with success flag
    return RedirectResponse(f"{BASE_URL}/dashboard?connected=1&stripe_id={stripe_user_id}", status_code=303)
