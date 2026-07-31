"""
Citizen assistant routes.
Provides guided complaint filing and status help without external LLM dependency.
"""

import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Complaint
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services.complaint_service import complaint_to_response
from app.services.localization_service import localized_status, normalize_language

router = APIRouter(prefix="/assistant", tags=["Assistant"])

TICKET_RE = re.compile(r"CB-\d{4}-\d{5}", re.IGNORECASE)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    language = normalize_language(data.language)
    message = data.message.strip()
    ticket_match = TICKET_RE.search(message)

    if ticket_match:
        ticket_id = ticket_match.group(0).upper()
        result = await db.execute(
            select(Complaint)
            .where(Complaint.ticket_id == ticket_id)
            .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        )
        complaint = result.scalar_one_or_none()
        if not complaint:
            return ChatResponse(
                reply=f"I could not find {ticket_id}. Please check the ticket ID.",
                intent="track_ticket",
                suggested_action="track",
                ticket_id=ticket_id,
                language=language,
            )

        response = complaint_to_response(complaint)
        status_text = localized_status(response.status, language)
        return ChatResponse(
            reply=(
                f"{response.ticket_id}: {status_text}. "
                f"Department: {response.department_name or 'Not assigned yet'}. "
                f"SLA: {response.sla_status or 'not available'}."
            ),
            intent="track_ticket",
            suggested_action="track",
            ticket_id=response.ticket_id,
            language=language,
        )

    lower = message.lower()
    if any(word in lower for word in ["status", "track", "ticket"]):
        return ChatResponse(
            reply="Send your ticket ID, for example CB-2026-00001, and I will check its status.",
            intent="status_help",
            suggested_action="track",
            language=language,
        )

    if any(word in lower for word in ["complaint", "issue", "problem", "report", "submit"]):
        return ChatResponse(
            reply=(
                "Describe the civic issue, location, and urgency in one message. "
                "You can mention multiple issues together; City Brain will create separate tickets."
            ),
            intent="filing_help",
            suggested_action="submit",
            language=language,
        )

    return ChatResponse(
        reply=(
            "I can help you file a complaint or track an existing ticket. "
            "Try: 'Report garbage near Jayanagar' or 'Track CB-2026-00001'."
        ),
        intent="general_help",
        suggested_action="submit",
        language=language,
    )
