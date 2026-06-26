"""Stripe integration — direct API key management and connected account operations."""
import stripe
from app.config import STRIPE_SECRET_KEY, BASE_URL

stripe.api_key = STRIPE_SECRET_KEY


def validate_stripe_key(api_key: str) -> bool:
    """Test whether a given Stripe secret key is valid."""
    try:
        stripe.Account.retrieve(api_key=api_key)
        return True
    except Exception:
        return False


def get_connected_stripe(api_key: str):
    """Get a Stripe client scoped to a customer's account using their API key."""
    return stripe.StripeClient(api_key=api_key)


def create_customer_portal_session(stripe_customer_id: str, return_url: str):
    """Create a Stripe customer portal session for updating payment method."""
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
