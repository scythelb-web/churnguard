"""ChurnGuard — Recover failed subscription payments with smart dunning."""
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import SENDGRID_API_KEY, ADMIN_EMAIL
from app.database import init_db
from app.routers import auth, webhooks, dashboard, billing
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


@app.post("/test-email")
async def test_email(to_email: str | None = None):
    """Send a test email to verify SendGrid is configured."""
    if not SENDGRID_API_KEY:
        return {"status": "error", "message": "SendGrid API key not configured"}
    
    target = to_email or ADMIN_EMAIL
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
