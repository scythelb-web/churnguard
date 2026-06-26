"""SMS service - sends dunning SMS via Twilio."""
from twilio.rest import Client
from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
import logging

logger = logging.getLogger(__name__)

_twilio = None

def _get_twilio():
    global _twilio
    if _twilio is None and TWILIO_ACCOUNT_SID:
        _twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _twilio


def send_dunning_sms(to_phone: str, body: str) -> bool:
    """Send a dunning SMS. Returns True if sent successfully."""
    client = _get_twilio()
    if not client:
        logger.warning("Twilio not configured — skipping SMS to %s", to_phone)
        return False

    if not TWILIO_PHONE_NUMBER:
        logger.warning("No Twilio phone number configured")
        return False

    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
        logger.info("SMS sent to %s — SID %s", to_phone, message.sid)
        return True
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", to_phone, e)
        return False
