import stripe
from app.config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY

def create_customer(email: str, name: str | None = None) -> stripe.Customer:
    return stripe.Customer.create(email=email, name=name or email)

def create_checkout_session(customer_id: str, price_id: str, success_url: str, cancel_url: str):
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )

def get_subscription(subscription_id: str):
    return stripe.Subscription.retrieve(subscription_id)

def cancel_subscription(subscription_id: str):
    return stripe.Subscription.delete(subscription_id)
