"""Email service - sends dunning emails via SendGrid."""
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, Content, HtmlContent
from app.config import SENDGRID_API_KEY, BASE_URL
import logging

logger = logging.getLogger(__name__)

_sg = None

def _get_sg():
    global _sg
    if _sg is None and SENDGRID_API_KEY:
        _sg = SendGridAPIClient(SENDGRID_API_KEY)
    return _sg


def send_dunning_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    customer_stripe_account: str | None = None,
) -> bool:
    """Send a dunning email. Returns True if sent successfully."""
    sg = _get_sg()
    if not sg:
        logger.warning("SendGrid not configured — skipping email to %s", to_email)
        return False

    message = Mail(
        from_email=From("scythelb@gmail.com", "ChurnGuard Billing"),
        to_emails=To(to_email, to_name),
        subject=Subject(subject),
        html_content=HtmlContent(body_html),
    )

    try:
        response = sg.send(message)
        ok = 200 <= response.status_code < 300
        if ok:
            logger.info("Dunning email sent to %s — status %d", to_email, response.status_code)
        else:
            logger.error("SendGrid error %d: %s", response.status_code, response.body)
        return ok
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_recovery_report(to_email: str, stats: dict) -> bool:
    """Send a monthly recovery report to the customer."""
    subject = f"ChurnGuard: You recovered ${stats['amount_recovered']:.2f} this month"
    body = f"""
    <h2>Monthly Recovery Report</h2>
    <table style="border-collapse:collapse;width:100%">
      <tr><td>Failed payments</td><td>{stats['total_failed']}</td></tr>
      <tr><td>Recovered payments</td><td>{stats['total_recovered']}</td></tr>
      <tr><td>Revenue at risk</td><td>${stats['amount_failed']:.2f}</td></tr>
      <tr><td>Revenue recovered</td><td style="color:green;font-weight:bold">${stats['amount_recovered']:.2f}</td></tr>
      <tr><td>Recovery rate</td><td>{stats['recovery_rate']:.1f}%</td></tr>
    </table>
    <p><a href="{BASE_URL}/dashboard">View full dashboard</a></p>
    """
    return send_dunning_email(to_email, to_email, subject, body)
