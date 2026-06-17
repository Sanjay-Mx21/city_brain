"""
WhatsApp-native complaint intake via Twilio webhook.
Configure Twilio Sandbox webhook to POST here:
/api/v1/whatsapp/webhook
"""

import re

from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_password
from app.models.models import Complaint, User, UserRole
from app.services.complaint_service import complaint_to_response, process_citizen_complaint
from app.services.localization_service import localized_status

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
TICKET_RE = re.compile(r"CB-\d{4}-\d{5}", re.IGNORECASE)


def twiml(message: str) -> Response:
    escaped = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escaped}</Message></Response>',
        media_type="application/xml",
    )


def clean_phone(raw_phone: str) -> str:
    return raw_phone.replace("whatsapp:", "").strip()


@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    phone = clean_phone(From)
    text = Body.strip()

    ticket_match = TICKET_RE.search(text)
    if ticket_match:
        ticket_id = ticket_match.group(0).upper()
        result = await db.execute(
            select(Complaint)
            .where(Complaint.ticket_id == ticket_id)
            .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        )
        complaint = result.scalar_one_or_none()
        if not complaint:
            return twiml(f"Ticket {ticket_id} was not found.")
        response = complaint_to_response(complaint)
        return twiml(
            f"{response.ticket_id}: {localized_status(response.status, 'en')}. "
            f"Department: {response.department_name or 'Not assigned yet'}."
        )

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            full_name=f"WhatsApp Citizen {phone[-4:]}",
            phone=phone,
            password_hash=hash_password("whatsapp123"),
            role=UserRole.CITIZEN.value,
            preferred_language="en",
        )
        db.add(user)
        await db.flush()

    complaints = await process_citizen_complaint(
        db=db,
        citizen_id=user.id,
        text=text,
        language=user.preferred_language or "en",
    )
    ticket_ids = ", ".join(c.ticket_id for c in complaints)
    return twiml(f"Your complaint has been registered. Ticket IDs: {ticket_ids}.")
