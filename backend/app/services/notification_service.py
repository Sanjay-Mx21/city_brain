"""
City Brain notification service.
Sends WhatsApp / SMS notifications via Twilio when credentials are configured,
otherwise logs mock messages for demos.
"""

import logging

from app.core.config import settings
from app.services.localization_service import localize, localized_status

logger = logging.getLogger(__name__)

_twilio_client = None


def get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            from twilio.rest import Client

            _twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        else:
            logger.warning("Twilio credentials not configured. Notifications will be logged only.")
    return _twilio_client


async def send_whatsapp(to_phone: str, message: str) -> bool:
    client = get_twilio_client()
    if not client:
        logger.info("[MOCK WhatsApp -> %s]: %s", to_phone, message)
        return True

    try:
        msg = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_phone}",
            body=message,
        )
        logger.info("WhatsApp sent to %s: SID=%s", to_phone, msg.sid)
        return True
    except Exception as exc:
        logger.error("WhatsApp failed to %s: %s", to_phone, exc)
        return False


async def send_sms(to_phone: str, message: str) -> bool:
    client = get_twilio_client()
    if not client:
        logger.info("[MOCK SMS -> %s]: %s", to_phone, message)
        return True

    try:
        msg = client.messages.create(
            from_=settings.TWILIO_SMS_FROM,
            to=to_phone,
            body=message,
        )
        logger.info("SMS sent to %s: SID=%s", to_phone, msg.sid)
        return True
    except Exception as exc:
        logger.error("SMS failed to %s: %s", to_phone, exc)
        return False


async def notify_complaint_created(
    phone: str, ticket_ids: list[str], language: str = "en"
) -> bool:
    message = localize("complaint_created", language, tickets=", ".join(ticket_ids))
    return await send_whatsapp(phone, f"City Brain\n{message}")


async def notify_status_update(
    phone: str, ticket_id: str, new_status: str, language: str = "en"
) -> bool:
    status_text = localized_status(new_status, language)
    messages = {
        "en": f"City Brain Update\nTicket: {ticket_id}\nStatus: {status_text}",
        "hi": f"सिटी ब्रेन अपडेट\nटिकट: {ticket_id}\nस्थिति: {status_text}",
        "kn": f"ಸಿಟಿ ಬ್ರೇನ್ ನವೀಕರಣ\nಟಿಕೆಟ್: {ticket_id}\nಸ್ಥಿತಿ: {status_text}",
    }
    return await send_whatsapp(phone, messages.get(language, messages["en"]))
