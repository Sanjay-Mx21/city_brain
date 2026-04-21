"""
City Brain — Officer Routes
View complaint queue, update status, get personal stats
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import Complaint, ComplaintStatus, Officer
from app.schemas.schemas import (
    ComplaintListResponse, ComplaintResponse, StatusUpdate, OfficerStats
)
from app.services.complaint_service import (
    get_complaints_for_officer, update_complaint_status, complaint_to_response
)
from app.services.notification_service import notify_status_update

router = APIRouter(prefix="/officer", tags=["Officer Portal"])


@router.get("/queue", response_model=ComplaintListResponse)
async def get_complaint_queue(
    status_filter: str = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(["officer", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get complaints queue for the officer's department."""
    # Get officer's department
    result = await db.execute(
        select(Officer).where(Officer.user_id == current_user["user_id"])
    )
    officer = result.scalar_one_or_none()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer profile not found")

    complaints, total = await get_complaints_for_officer(
        db, current_user["user_id"], officer.department_id,
        status_filter=status_filter, page=page, per_page=per_page
    )

    return ComplaintListResponse(
        complaints=[complaint_to_response(c) for c in complaints],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.patch("/complaints/{complaint_id}/status")
async def update_status(
    complaint_id: int,
    update: StatusUpdate,
    current_user: dict = Depends(require_role(["officer", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update complaint status (officer action)."""
    valid_statuses = {
        ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED, ComplaintStatus.ESCALATED, ComplaintStatus.CLOSED,
    }
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    try:
        complaint = await update_complaint_status(
            db, complaint_id, update, current_user["user_id"]
        )

        # Notify citizen of status change
        # await notify_status_update(citizen_phone, complaint.ticket_id, update.status)

        return {
            "message": f"Complaint {complaint.ticket_id} updated to {update.status}",
            "ticket_id": complaint.ticket_id,
            "new_status": update.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=OfficerStats)
async def get_officer_stats(
    current_user: dict = Depends(require_role(["officer", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get personal performance stats for the logged-in officer."""
    officer_id = current_user["user_id"]

    result = await db.execute(
        select(Officer).where(Officer.user_id == officer_id)
    )
    officer = result.scalar_one_or_none()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer profile not found")

    dept_id = officer.department_id

    # Count by status
    status_counts = await db.execute(
        select(Complaint.status, func.count(Complaint.id))
        .where(Complaint.department_id == dept_id)
        .group_by(Complaint.status)
    )
    counts = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in status_counts}

    # Average resolution time
    avg_hours = (await db.execute(
        select(
            func.avg(func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600)
        ).where(
            and_(
                Complaint.department_id == dept_id,
                Complaint.resolved_at.isnot(None),
            )
        )
    )).scalar()

    total = sum(counts.values())

    return OfficerStats(
        total_assigned=total,
        pending=counts.get("pending", 0),
        in_progress=counts.get("in_progress", 0),
        resolved=counts.get("resolved", 0),
        escalated=counts.get("escalated", 0),
        avg_resolution_hours=round(avg_hours, 1) if avg_hours else None,
    )
