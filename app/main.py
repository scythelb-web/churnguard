"""ChurnGuard — Recover failed subscription payments with smart dunning."""
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import SENDGRID_API_KEY, ADMIN_EMAIL
from app.database import init_db
from app.routers import auth, webhooks, dashboard, billing, oauth
from app.services.emailer import send_dunning_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ChurnGuard", version="0.1.0")

# Templates
templates_dir = Path(__file__).parent / "templates"
app.state.templates = Jinja2Templates(directory=str(templates_dir))

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(auth.router)
app.include_router(webhooks.router)
app.include_router(dashboard.router)
app.include_router(billing.router)
app.include_router(oauth.router)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("ChurnGuard started")


@app.get("/")
async def landing(request: Request):
    return app.state.templates.TemplateResponse("landing.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ChurnGuard"}


@app.get("/debug/db")
async def debug_db():
    from app.database import _use_turso, _turso_available, TURSO_URL
    return {
        "turso_enabled": _use_turso,
        "turso_module": _turso_available,
        "turso_url": TURSO_URL[:50] + "..." if TURSO_URL else "not set",
    }


@app.post("/test-email")
async def test_email(to_email: str | None = None):
    """Send a test email to verify SendGrid is configured."""
    import os
    key_present = bool(os.getenv("SENDGRID_API_KEY", ""))
    if not SENDGRID_API_KEY:
        return {"status": "error", "message": "SendGrid API key not configured",
                "debug": {"env_var_set": key_present, "config_read": bool(SENDGRID_API_KEY)}}
    
    target = to_email or "scythelb@gmail.com"
    result = send_dunning_email(
        to_email=target,
        to_name="ChurnGuard User",
        subject="ChurnGuard Email Test — It Works!",
        body_html="""
        <h2>Your ChurnGuard dunning emails are configured!</h2>
        <p>This confirms that SendGrid is wired up and sending correctly.</p>
        <p>Your customers will now receive dunning emails when their payments fail.</p>
        <br>
        <p style="color: #888; font-size: 12px;">
            Sent from ChurnGuard — subscription payment recovery
        </p>
        """
    )
    return {"status": "ok" if result else "error", "sent": result, "to": target}
