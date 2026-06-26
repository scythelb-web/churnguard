import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./churnguard.db")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CONNECT_CLIENT_ID = os.getenv("STRIPE_CONNECT_CLIENT_ID", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@churnguard.io")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Pricing tiers
PRICING = {
    "starter": {"price": 49, "mrr_limit": 5000, "label": "Starter"},
    "growth": {"price": 99, "mrr_limit": 25000, "label": "Growth"},
    "scale": {"price": 249, "mrr_limit": 100000, "label": "Scale"},
}
