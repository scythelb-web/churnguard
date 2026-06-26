# ChurnGuard

Recover 20-30% more failed subscription payments with intelligent multi-channel dunning on top of Stripe.

**~9% of MRR is lost to failed payments.** ChurnGuard layers email + SMS recovery sequences on top of Stripe's Smart Retries to turn that leak into recovered revenue.

## How it works

1. **Connect Stripe** — one-click OAuth
2. **Smart Dunning** — automated email + SMS sequences proven to recover 25%+ more than Stripe alone
3. **Dashboard** — watch revenue recover in real-time

## Stack

- Python / FastAPI
- SQLite
- Stripe Connect API
- SendGrid (email) + Twilio (SMS)
- Jinja2 templates

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install 'bcrypt<5'
python3 init_db.py
uvicorn app.main:app --reload
```

## Env vars

Copy `.env.example` to `.env` and fill in:
- `SECRET_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_CONNECT_CLIENT_ID`
- `SENDGRID_API_KEY`
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`
