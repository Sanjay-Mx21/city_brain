"""
City Brain — Officer Routes
View complaint queue, update status, get personal stats
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
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
    department_id: int | None = Query(None, description="0 for all departments, or a department id"),
    sort_by: str = Query("priority", pattern="^(priority|latest)$"),
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
    if not officer and current_user["role"] != "admin":
        raise HTTPException(status_code=404, detail="Officer profile not found")

    if department_id == 0:
        effective_department_id = None
    elif department_id is not None:
        effective_department_id = department_id
    else:
        effective_department_id = officer.department_id if officer else None

    complaints, total = await get_complaints_for_officer(
        db, current_user["user_id"], effective_department_id,
        status_filter=status_filter, sort_by=sort_by, page=page, per_page=per_page
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
        ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value,
        ComplaintStatus.RESOLVED.value, ComplaintStatus.ESCALATED.value,
        ComplaintStatus.CLOSED.value,
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

        if complaint.citizen:
            await notify_status_update(
                complaint.citizen.phone,
                complaint.ticket_id,
                update.status,
                complaint.citizen.preferred_language or "en",
            )

        return {
            "message": f"Complaint {complaint.ticket_id} updated to {update.status}",
            "ticket_id": complaint.ticket_id,
            "new_status": update.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=OfficerStats)
async def get_officer_stats(
    department_id: int | None = Query(None, description="0 for all departments, or a department id"),
    current_user: dict = Depends(require_role(["officer", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get personal performance stats for the logged-in officer."""
    officer_id = current_user["user_id"]

    result = await db.execute(
        select(Officer).where(Officer.user_id == officer_id)
    )
    officer = result.scalar_one_or_none()
    if not officer and current_user["role"] != "admin":
        raise HTTPException(status_code=404, detail="Officer profile not found")

    if department_id == 0:
        dept_id = None
    elif department_id is not None:
        dept_id = department_id
    else:
        dept_id = officer.department_id if officer else None

    # Count by status
    status_query = select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)
    if dept_id is not None:
        status_query = status_query.where(Complaint.department_id == dept_id)
    status_counts = await db.execute(status_query)
    counts = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in status_counts}

    resolved_query = select(Complaint.created_at, Complaint.resolved_at).where(
        Complaint.resolved_at.isnot(None)
    )
    if dept_id is not None:
        resolved_query = resolved_query.where(Complaint.department_id == dept_id)
    resolved_rows = await db.execute(resolved_query)
    durations = [
        (resolved_at - created_at).total_seconds() / 3600
        for created_at, resolved_at in resolved_rows
        if created_at and resolved_at
    ]
    avg_hours = sum(durations) / len(durations) if durations else None

    total = sum(counts.values())
    now = datetime.utcnow()
    sla_query = select(Complaint.status, Complaint.sla_deadline).where(
        Complaint.sla_deadline.isnot(None)
    )
    if dept_id is not None:
        sla_query = sla_query.where(Complaint.department_id == dept_id)
    sla_rows = await db.execute(sla_query)
    overdue = 0
    due_soon = 0
    for status, sla_deadline in sla_rows:
        status_value = status.value if hasattr(status, "value") else status
        if status_value in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value):
            continue
        if sla_deadline < now:
            overdue += 1
        elif sla_deadline <= now + timedelta(hours=24):
            due_soon += 1

    return OfficerStats(
        total_assigned=total,
        pending=counts.get("pending", 0),
        in_progress=counts.get("in_progress", 0),
        resolved=counts.get("resolved", 0),
        escalated=counts.get("escalated", 0),
        overdue=overdue,
        due_soon=due_soon,
        avg_resolution_hours=round(avg_hours, 1) if avg_hours else None,
    )
