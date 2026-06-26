"""Stripe Connect integration - manages customer Stripe account connections."""
import stripe
from app.config import STRIPE_SECRET_KEY, STRIPE_CONNECT_CLIENT_ID, BASE_URL

stripe.api_key = STRIPE_SECRET_KEY

def get_connect_oauth_url(user_id: int) -> str:
    """Generate Stripe Connect OAuth URL for a customer to connect their account."""
    return stripe.OAuth.authorize_url(
        client_id=STRIPE_CONNECT_CLIENT_ID,
        response_type="code",
        scope="read_write",
        redirect_uri=f"{BASE_URL}/stripe/connect/callback",
        state=str(user_id),
    )

def handle_connect_callback(code: str) -> dict:
    """Exchange OAuth code for access token."""
    response = stripe.OAuth.token(
        grant_type="authorization_code",
        code=code,
    )
    return {
        "stripe_account_id": response["stripe_user_id"],
        "access_token": response["access_token"],
        "refresh_token": response.get("refresh_token"),
    }

def get_connected_stripe(access_token: str):
    """Get a Stripe client scoped to a connected account."""
    return stripe.StripeClient(api_key=STRIPE_SECRET_KEY, stripe_account=access_token)

def create_customer_portal_session(stripe_customer_id: str, return_url: str):
    """Create a Stripe customer portal session for update payment method."""
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
        configuration=stripe.billing_portal.Configuration.create(
            business_profile=stripe.billing_portal.Configuration.CreateParamsBusinessProfile(
                headline="Update your payment method to keep your service active."
            ),
            features=stripe.billing_portal.Configuration.CreateParamsFeatures(
                customer_update=stripe.billing_portal.Configuration.CreateParamsFeaturesCustomerUpdate(
                    allowed_updates=["payment_method"],
                    enabled=True,
                ),
                invoice_history={"enabled": False},
                payment_method_update={"enabled": True},
                subscription_cancel={"enabled": False},
                subscription_update={"enabled": False},
            ),
        ),
    )
    return session.url
