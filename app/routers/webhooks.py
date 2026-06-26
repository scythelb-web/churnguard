"""Stripe webhook handler — the core of ChurnGuard."""

import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from jinja2 import Template

from app.database import get_db
from app.services.dunning import (
    get_sequence_for_failure,
    DEFAULT_EMAIL_TEMPLATES,
    DEFAULT_SMS_TEMPLATES,
)
from app.services.emailer import send_dunning_email
from app.services.sms import send_dunning_sms
from app.services.stripe import create_customer_portal_session
from app.config import BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["stripe"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events from connected accounts."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    event_type = request.headers.get("stripe-event-type", "")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid payload")

    event_type = event.get("type", event_type)
    logger.info("Webhook received: %s", event_type)

    if event_type == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"])

    elif event_type == "invoice.payment_succeeded":
        await handle_payment_succeeded(event["data"]["object"])

    elif event_type == "invoice.paid":
        # Some setups fire 'invoice.paid' instead of 'invoice.payment_succeeded'
        await handle_payment_succeeded(event["data"]["object"])

    return {"status": "ok"}


async def handle_payment_failed(invoice: dict):
    """A payment failed — log it and start the dunning sequence."""
    stripe_customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    amount = invoice.get("amount_due", 0)
    currency = invoice.get("currency", "usd")
    attempt_count = invoice.get("attempt_count", 1)
    payment_intent_id = None

    # Get decline info from the payment intent if available
    pi = invoice.get("payment_intent")
    if isinstance(pi, dict):
        payment_intent_id = pi.get("id")
        decline_code = pi.get("last_payment_error", {}).get("decline_code", "")
        failure_message = pi.get("last_payment_error", {}).get("message", "")
    elif isinstance(pi, str):
        payment_intent_id = pi
        decline_code = ""
        failure_message = ""
    else:
        decline_code = ""
        failure_message = ""

    logger.info(
        "Payment failed: customer=%s invoice=%s amount=%d decline=%s attempt=%d",
        stripe_customer_id, invoice_id, amount, decline_code, attempt_count,
    )

    # Find which of our users this Stripe customer belongs to
    with get_db() as db:
        # Look up by connected Stripe account
        stripe_account_id = invoice.get("account_id") or invoice.get("metadata", {}).get("stripe_account")
        user_row = None

        if stripe_account_id:
            user_row = db.execute(
                """SELECT u.* FROM users u
                   JOIN customer_stripe_accounts csa ON csa.user_id = u.id
                   WHERE csa.stripe_account_id = ?""",
                (stripe_account_id,),
            ).fetchone()

        if not user_row:
            logger.warning("No ChurnGuard user found for Stripe customer %s", stripe_customer_id)
            return

        user = dict(user_row)

        # Check if we already have this failed payment (dedup by invoice_id)
        existing = db.execute(
            "SELECT id FROM failed_payments WHERE stripe_invoice_id = ?",
            (invoice_id,),
        ).fetchone()

        if existing:
            # Update attempt count
            db.execute(
                "UPDATE failed_payments SET attempt_count = ?, status = 'pending' WHERE id = ?",
                (attempt_count, existing["id"]),
            )
            failed_payment_id = existing["id"]
        else:
            cursor = db.execute(
                """INSERT INTO failed_payments
                   (user_id, stripe_customer_id, stripe_invoice_id, stripe_payment_intent_id,
                    amount, currency, decline_code, failure_message, attempt_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user["id"], stripe_customer_id, invoice_id, payment_intent_id,
                 amount, currency, decline_code, failure_message, attempt_count),
            )
            failed_payment_id = cursor.lastrowid

        # Log this attempt in dunning_log if it corresponds to our sequence steps
        # (Step 1 = attempt_count 1, etc. — simplified mapping)
        sequence = get_sequence_for_failure({"decline_code": decline_code})
        step_index = min(attempt_count - 1, len(sequence) - 1)

        if step_index >= 0:
            step = sequence[step_index]
            await send_dunning_message(
                db=db,
                user=user,
                customer_id=stripe_customer_id,
                invoice=invoice,
                failed_payment_id=failed_payment_id,
                step=step,
                amount=amount / 100,
                currency=currency,
            )


async def send_dunning_message(
    db,
    user: dict,
    customer_id: str,
    invoice: dict,
    failed_payment_id: int,
    step: dict,
    amount: float,
    currency: str,
):
    """Send a dunning message (email or SMS) for a failed payment."""
    step_num = step["step"]
    channel = step["channel"]

    # Get customer info from the invoice
    customer_email = invoice.get("customer_email", "")
    customer_name = invoice.get("customer_name", customer_email)
    customer_phone = invoice.get("customer_phone", "")

    # Build the update link
    update_link = f"{BASE_URL}/stripe/update-card?customer={customer_id}"

    # Template variables
    vars = {
        "customer_name": customer_name or "there",
        "amount": f"{amount:.2f}",
        "plan_name": "subscription",
        "update_link": update_link,
        "app_name": "your service",
        "plan_benefits": ["Your saved data and settings", "Premium features", "Priority support"],
        "reactivate_link": update_link,
    }

    sent = False
    if channel == "email":
        templates = DEFAULT_EMAIL_TEMPLATES
        template = templates.get(step_num, templates.get(1, {}))
        if template and customer_email:
            subject_tmpl = Template(template["subject"])
            body_tmpl = Template(template["body"])
            try:
                subject = subject_tmpl.render(**vars)
                body = body_tmpl.render(**vars)
                sent = send_dunning_email(customer_email, customer_name, subject, body)
            except Exception as e:
                logger.error("Template render error: %s", e)

    elif channel == "sms":
        templates = DEFAULT_SMS_TEMPLATES
        template = templates.get(step_num)
        if template and customer_phone:
            tmpl = Template(template)
            try:
                body = tmpl.render(**vars)
                sent = send_dunning_sms(customer_phone, body)
            except Exception as e:
                logger.error("SMS template render error: %s", e)

    # Log the attempt
    db.execute(
        """INSERT INTO dunning_log (failed_payment_id, step_number, channel)
           VALUES (?, ?, ?)""",
        (failed_payment_id, step_num, channel),
    )


async def handle_payment_succeeded(invoice: dict):
    """A previously failed payment succeeded — mark it recovered."""
    invoice_id = invoice.get("id")
    amount = invoice.get("amount_paid", 0)

    logger.info("Payment recovered: invoice=%s amount=%d", invoice_id, amount)

    with get_db() as db:
        fp = db.execute(
            "SELECT * FROM failed_payments WHERE stripe_invoice_id = ? AND status = 'pending'",
            (invoice_id,),
        ).fetchone()

        if not fp:
            return

        db.execute(
            """UPDATE failed_payments
               SET status = 'recovered', resolved_at = CURRENT_TIMESTAMP, resolved_status = 'recovered'
               WHERE id = ?""",
            (fp["id"],),
        )

        # Update recovery stats
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        db.execute(
            """INSERT INTO recovery_stats (user_id, month, total_failed, total_recovered,
               total_amount_failed, total_amount_recovered)
               VALUES (?, ?, 0, 1, 0, ?)
               ON CONFLICT(user_id, month) DO UPDATE SET
               total_recovered = total_recovered + 1,
               total_amount_recovered = total_amount_recovered + ?""",
            (fp["user_id"], month, amount, amount),
        )


@router.get("/connect")
async def stripe_connect(request: Request):
    """Initiate Stripe Connect OAuth flow."""
    from app.routers.auth import get_current_user
    from app.services.stripe import get_connect_oauth_url

    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/auth/login", status_code=303)

    url = get_connect_oauth_url(user["id"])
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url, status_code=303)


@router.get("/connect/callback")
async def stripe_connect_callback(request: Request, code: str, state: str):
    """Handle Stripe Connect OAuth callback."""
    from app.services.stripe import handle_connect_callback

    user_id = int(state)
    data = handle_connect_callback(code)

    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO customer_stripe_accounts
               (user_id, stripe_account_id, access_token, refresh_token)
               VALUES (?, ?, ?, ?)""",
            (user_id, data["stripe_account_id"], data["access_token"],
             data.get("refresh_token")),
        )
        db.execute(
            "UPDATE users SET stripe_account_id = ?, stripe_connect_active = 1 WHERE id = ?",
            (data["stripe_account_id"], user_id),
        )

    from fastapi.responses import RedirectResponse
    return RedirectResponse("/dashboard?connected=1", status_code=303)


@router.get("/update-card")
async def update_card(request: Request, customer: str):
    """Redirect customer to Stripe Customer Portal to update payment method."""
    url = create_customer_portal_session(
        customer,
        return_url=f"{BASE_URL}/stripe/card-updated",
    )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url, status_code=303)


@router.get("/card-updated")
async def card_updated(request: Request):
    from fastapi.responses import HTMLResponse
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;text-align:center;padding-top:80px">
      <h2>Payment method updated!</h2>
      <p>Your payment has been processed. You can close this page.</p>
    </body></html>
    """)
