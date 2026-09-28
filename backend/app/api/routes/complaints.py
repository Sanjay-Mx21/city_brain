"""
City Brain — Complaint Routes
Submit complaints, view status, get history
"""

import asyncio
import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_optional_user
from app.models.models import Complaint, User
from app.schemas.schemas import (
    ComplaintSubmit, ComplaintSubmitResponse, ComplaintResponse,
    ComplaintListResponse
)
from app.services.complaint_service import (
    process_citizen_complaint, get_citizen_complaints, complaint_to_response
)
from app.services.image_verification_service import verify_image_evidence
from app.services.localization_service import localize
from app.services.notification_service import notify_complaint_created
from app.services.transcription_service import transcribe_audio

logger = logging.getLogger(__name__)

# The stored file extension is derived from the detected file signature,
# never from the client-supplied filename or content type.
IMAGE_SIGNATURES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def detect_image_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return None


async def read_limited(file: UploadFile, max_mb: int) -> bytes:
    max_bytes = max_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {max_mb} MB)")
    return data

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

        user_result = await db.execute(select(User).where(User.id == current_user["user_id"]))
        citizen = user_result.scalar_one_or_none()
        response_language = (citizen.preferred_language if citizen else None) or data.language or "en"
        if citizen:
            await notify_complaint_created(
                citizen.phone,
                ticket_ids,
                response_language,
            )

        localized_message = localize(
            "complaint_created",
            response_language,
            tickets=", ".join(ticket_ids),
        )
        return ComplaintSubmitResponse(
            message=f"Successfully registered {len(complaints)} complaint(s)!",
            localized_message=localized_message,
            tickets=ticket_responses,
            total_complaints_detected=len(complaints),
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process complaint")
        raise HTTPException(status_code=500, detail="Failed to process complaint. Please try again.")


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
    current_user: Optional[dict] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Track a complaint by ticket ID (public — no auth required).
    Anonymous callers get status only; the citizen's own text, exact GPS
    location and photo are shown only to the owner and to officers/admins.
    """
    result = await db.execute(
        select(Complaint)
        .where(Complaint.ticket_id == ticket_id.strip().upper())
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
    )
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    response = complaint_to_response(complaint)
    is_privileged = current_user is not None and (
        current_user["user_id"] == complaint.citizen_id
        or current_user["role"] in ("officer", "admin")
    )
    if is_privileged:
        return response
    return response.model_copy(update={
        "original_text": "",
        "translated_text": None,
        "latitude": None,
        "longitude": None,
        "image_url": None,
        "image_verification_notes": None,
    })


@router.post("/{complaint_id}/image", response_model=ComplaintResponse)
async def upload_complaint_image(
    complaint_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attach an image to an existing complaint."""
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

    contents = await read_limited(file, settings.MAX_IMAGE_UPLOAD_MB)
    image_type = detect_image_type(contents)
    if image_type is None:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, or GIF images allowed")

    filename = f"{uuid.uuid4().hex}.{IMAGE_SIGNATURES[image_type]}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    verification = verify_image_evidence(
        contents,
        image_type,
        file.filename,
        complaint.category.value if hasattr(complaint.category, "value") else complaint.category,
    )
    with open(filepath, "wb") as f:
        f.write(contents)

    complaint.image_url = f"/uploads/{filename}"
    complaint.image_verification_status = verification.status
    complaint.image_verification_confidence = verification.confidence
    complaint.image_verification_notes = verification.notes
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
    audio_bytes = await read_limited(file, settings.MAX_AUDIO_UPLOAD_MB)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        # Run blocking Whisper inference in a thread pool so it doesn't block the event loop
        return await asyncio.to_thread(transcribe_audio, audio_bytes, language or None, translate)
    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed. Please try again or type your complaint.")
