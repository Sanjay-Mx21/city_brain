"""
City Brain — Notification Service
Sends WhatsApp / SMS notifications via Twilio.
"""

import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Twilio client (lazy init)
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
    """Send a WhatsApp message via Twilio Sandbox."""
    client = get_twilio_client()
    if not client:
        logger.info(f"[MOCK WhatsApp → {to_phone}]: {message}")
        return True

    try:
        msg = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_phone}",
            body=message,
        )
        logger.info(f"WhatsApp sent to {to_phone}: SID={msg.sid}")
        return True
    except Exception as e:
        logger.error(f"WhatsApp failed to {to_phone}: {e}")
        return False


async def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS via Twilio (fallback for non-WhatsApp users)."""
    client = get_twilio_client()
    if not client:
        logger.info(f"[MOCK SMS → {to_phone}]: {message}")
        return True

    try:
        msg = client.messages.create(
            from_=settings.TWILIO_SMS_FROM,
            to=to_phone,
            body=message,
        )
        logger.info(f"SMS sent to {to_phone}: SID={msg.sid}")
        return True
    except Exception as e:
        logger.error(f"SMS failed to {to_phone}: {e}")
        return False


async def notify_complaint_created(
    phone: str, ticket_ids: list[str], language: str = "en"
) -> bool:
    """Notify citizen that their complaint(s) have been registered."""
    if language == "kn":
        message = (
            f"🏛️ ಸಿಟಿ ಬ್ರೇನ್: ನಿಮ್ಮ ದೂರು ನೋಂದಾಯಿಸಲಾಗಿದೆ!\n"
            f"ಟಿಕೆಟ್ ID: {', '.join(ticket_ids)}\n"
            f"ನಾವು ಇದನ್ನು ಸರಿಯಾದ ಇಲಾಖೆಗೆ ಕಳುಹಿಸಿದ್ದೇವೆ.\n"
            f"ನೀವು ನಮ್ಮ ಪೋರ್ಟಲ್‌ನಲ್ಲಿ ಸ್ಥಿತಿಯನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಬಹುದು."
        )
    elif language == "hi":
        message = (
            f"🏛️ सिटी ब्रेन: आपकी शिकायत दर्ज हो गई है!\n"
            f"टिकट ID: {', '.join(ticket_ids)}\n"
            f"हमने इसे सही विभाग को भेज दिया है।\n"
            f"आप हमारे पोर्टल पर स्थिति ट्रैक कर सकते हैं।"
        )
    else:
        message = (
            f"🏛️ City Brain: Your complaint has been registered!\n"
            f"Ticket ID(s): {', '.join(ticket_ids)}\n"
            f"We've routed it to the correct department.\n"
            f"Track status on our portal."
        )

    return await send_whatsapp(phone, message)


async def notify_status_update(
    phone: str, ticket_id: str, new_status: str, language: str = "en"
) -> bool:
    """Notify citizen of complaint status change."""
    status_labels = {
        "en": {
            "assigned": "Assigned to an officer",
            "in_progress": "Being worked on",
            "resolved": "✅ Resolved!",
            "escalated": "⚠️ Escalated to senior officer",
        },
        "kn": {
            "assigned": "ಅಧಿಕಾರಿಗೆ ನಿಯೋಜಿಸಲಾಗಿದೆ",
            "in_progress": "ಕೆಲಸ ನಡೆಯುತ್ತಿದೆ",
            "resolved": "✅ ಪರಿಹರಿಸಲಾಗಿದೆ!",
            "escalated": "⚠️ ಹಿರಿಯ ಅಧಿಕಾರಿಗೆ ಹೆಚ್ಚಿಸಲಾಗಿದೆ",
        },
        "hi": {
            "assigned": "अधिकारी को सौंपा गया",
            "in_progress": "काम जारी है",
            "resolved": "✅ समाधान हो गया!",
            "escalated": "⚠️ वरिष्ठ अधिकारी को भेजा गया",
        },
    }

    labels = status_labels.get(language, status_labels["en"])
    status_text = labels.get(new_status, new_status)

    message = f"🏛️ City Brain Update\nTicket: {ticket_id}\nStatus: {status_text}"
    return await send_whatsapp(phone, message)
