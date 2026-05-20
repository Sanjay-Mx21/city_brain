"""
City Brain — Complaint Routes
Submit complaints, view status, get history
"""

import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Complaint
from app.schemas.schemas import (
    ComplaintSubmit, ComplaintSubmitResponse, ComplaintResponse,
    ComplaintListResponse
)
from app.services.complaint_service import (
    process_citizen_complaint, get_citizen_complaints, complaint_to_response
)
from app.services.notification_service import notify_complaint_created
from app.services.transcription_service import transcribe_audio

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
UPLOAD_DIR = "uploads"

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("/submit", response_model=ComplaintSubmitResponse)
async def submit_complaint(
    data: ComplaintSubmit,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a citizen complaint.
    The AI pipeline will:
    1. Detect/translate language
    2. Parse and extract individual complaints
    3. Classify department + priority
    4. Create tickets
    5. Send WhatsApp confirmation
    """
    try:
        complaints = await process_citizen_complaint(
            db=db,
            citizen_id=current_user["user_id"],
            text=data.text,
            language=data.language,
            latitude=data.latitude,
            longitude=data.longitude,
        )

        ticket_responses = []
        ticket_ids = []
        for c in complaints:
            ticket_ids.append(c.ticket_id)
            ticket_responses.append(complaint_to_response(c))

        # Send notification (async, don't block response)
        # In production, this would be a background task
        # await notify_complaint_created(phone, ticket_ids)

        return ComplaintSubmitResponse(
            message=f"Successfully registered {len(complaints)} complaint(s)!",
            tickets=ticket_responses,
            total_complaints_detected=len(complaints),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process complaint: {str(e)}")


@router.get("/my", response_model=ComplaintListResponse)
async def get_my_complaints(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current citizen's complaints."""
    complaints, total = await get_citizen_complaints(
        db, current_user["user_id"], page, per_page
    )

    return ComplaintListResponse(
        complaints=[complaint_to_response(c) for c in complaints],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/track/{ticket_id}", response_model=ComplaintResponse)
async def track_complaint(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Track a complaint by ticket ID (public — no auth required)."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Complaint)
        .where(Complaint.ticket_id == ticket_id)
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
    )
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    return complaint_to_response(complaint)


@router.post("/{complaint_id}/image", response_model=ComplaintResponse)
async def upload_complaint_image(
    complaint_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attach an image to an existing complaint."""
    from sqlalchemy.orm import selectinload

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, or GIF images allowed")

    result = await db.execute(
        select(Complaint)
        .where(Complaint.id == complaint_id)
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.citizen_id != current_user["user_id"] and current_user["role"] not in ("officer", "admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    complaint.image_url = f"/uploads/{filename}"
    await db.commit()
    await db.refresh(complaint)

    return complaint_to_response(complaint)


@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
    language: str = Query(default=""),
    translate: bool = Query(default=True),
    current_user: dict = Depends(get_current_user),
):
    """
    Transcribe audio with local Whisper and translate speech to English by default.
    Accepts any audio format the browser's MediaRecorder produces (webm, ogg, mp4).
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        # Run blocking Whisper inference in a thread pool so it doesn't block the event loop
        result = await loop.run_in_executor(
            None, transcribe_audio, audio_bytes, language or None, translate
        )
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
