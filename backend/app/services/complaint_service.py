"""
City Brain — Complaint Service
Business logic for complaint creation, retrieval, status updates, and analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Complaint, ComplaintStatus, ComplaintStatusHistory,
    Department, Ward
)
from app.schemas.schemas import ComplaintResponse, StatusUpdate
from app.services.llm_pipeline import parse_complaint

logger = logging.getLogger(__name__)

SLA_HOURS = {1: 168, 2: 120, 3: 72, 4: 24, 5: 6}


def complaint_to_response(c: Complaint) -> ComplaintResponse:
    return ComplaintResponse(
        id=c.id,
        ticket_id=c.ticket_id,
        original_text=c.original_text,
        translated_text=c.translated_text,
        original_language=c.original_language,
        category=c.category.value if hasattr(c.category, 'value') else c.category,
        description=c.description,
        location_text=c.location_text,
        latitude=c.latitude,
        longitude=c.longitude,
        department_name=c.department.name if c.department else None,
        ward_name=c.ward.name if c.ward else None,
        priority=c.priority,
        ai_confidence=c.ai_confidence,
        status=c.status.value if hasattr(c.status, 'value') else c.status,
        created_at=c.created_at,
        updated_at=c.updated_at,
        resolved_at=c.resolved_at,
        sla_deadline=c.sla_deadline,
    )


async def process_citizen_complaint(
    db: AsyncSession,
    citizen_id: int,
    text: str,
    language: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> list[Complaint]:
    """
    Full pipeline: Take citizen's raw input → create complaint tickets.
    Returns list of created Complaint objects.
    """
    parsed = await parse_complaint(text, language=language or "en")

    created_complaints = []

    for complaint_data in parsed.complaints:
        department = await get_department_by_code(db, complaint_data.department)

        ward = None
        if latitude and longitude:
            ward = await find_nearest_ward(db, latitude, longitude)

        sla_hours = SLA_HOURS.get(complaint_data.severity, 72)
        sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

        complaint = Complaint(
            ticket_id="PENDING",  # placeholder — replaced after flush
            citizen_id=citizen_id,
            original_text=parsed.original_text,
            original_language=parsed.detected_language,
            translated_text=parsed.translated_text,
            category=complaint_data.category,
            description=complaint_data.description,
            location_text=complaint_data.location_text,
            latitude=latitude,
            longitude=longitude,
            department_id=department.id if department else 1,
            ward_id=ward.id if ward else None,
            priority=complaint_data.severity,
            ai_confidence=complaint_data.confidence,
            status=ComplaintStatus.PENDING,
            sla_deadline=sla_deadline,
        )

        db.add(complaint)
        await db.flush()

        # Use DB-assigned ID for a collision-free ticket ID
        complaint.ticket_id = f"CB-2026-{complaint.id:05d}"

        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=None,
            new_status=ComplaintStatus.PENDING,
            changed_by_id=citizen_id,
            notes="Complaint auto-created by City Brain AI",
        )
        db.add(history)

        created_complaints.append(complaint)

    await db.commit()

    for c in created_complaints:
        await db.refresh(c, ["department", "ward"])

    return created_complaints


async def get_department_by_code(db: AsyncSession, code: str) -> Optional[Department]:
    """Look up department by short code (BBMP, BESCOM, etc.)."""
    result = await db.execute(
        select(Department).where(Department.name == code)
    )
    dept = result.scalar_one_or_none()
    if not dept:
        result = await db.execute(
            select(Department).where(Department.name == "BBMP")
        )
        dept = result.scalar_one_or_none()
    return dept


async def find_nearest_ward(
    db: AsyncSession, lat: float, lon: float
) -> Optional[Ward]:
    """Find the nearest ward based on lat/lon (simple distance calc)."""
    result = await db.execute(
        select(Ward)
        .where(Ward.latitude.isnot(None))
        .order_by(
            func.abs(Ward.latitude - lat) + func.abs(Ward.longitude - lon)
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_citizen_complaints(
    db: AsyncSession, citizen_id: int, page: int = 1, per_page: int = 20
) -> tuple[list[Complaint], int]:
    """Get paginated complaints for a citizen."""
    count_q = select(func.count(Complaint.id)).where(Complaint.citizen_id == citizen_id)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Complaint)
        .where(Complaint.citizen_id == citizen_id)
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        .order_by(Complaint.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    complaints = result.scalars().all()

    return complaints, total


async def get_complaints_for_officer(
    db: AsyncSession, officer_user_id: int, department_id: int,
    status_filter: Optional[str] = None,
    page: int = 1, per_page: int = 20
) -> tuple[list[Complaint], int]:
    """Get complaints assigned to a department (for officer view)."""
    conditions = [Complaint.department_id == department_id]
    if status_filter:
        conditions.append(Complaint.status == status_filter)

    count_q = select(func.count(Complaint.id)).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Complaint)
        .where(and_(*conditions))
        .options(
            selectinload(Complaint.department),
            selectinload(Complaint.ward),
            selectinload(Complaint.citizen),
        )
        .order_by(Complaint.priority.desc(), Complaint.created_at.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    complaints = result.scalars().all()

    return complaints, total


async def update_complaint_status(
    db: AsyncSession, complaint_id: int, update: StatusUpdate, officer_id: int
) -> Complaint:
    """Update complaint status (officer action)."""
    result = await db.execute(
        select(Complaint)
        .where(Complaint.id == complaint_id)
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise ValueError(f"Complaint {complaint_id} not found")

    old_status = complaint.status

    complaint.status = update.status
    if update.status == ComplaintStatus.RESOLVED:
        complaint.resolved_at = datetime.utcnow()
    if update.status == ComplaintStatus.ESCALATED:
        complaint.escalated_at = datetime.utcnow()
    if update.status in (ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS):
        complaint.assigned_officer_id = officer_id
    if update.notes:
        complaint.resolution_notes = update.notes

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=old_status,
        new_status=update.status,
        changed_by_id=officer_id,
        notes=update.notes,
    )
    db.add(history)
    await db.commit()
    await db.refresh(complaint)

    return complaint


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """Get admin dashboard overview statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    status_counts = await db.execute(
        select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)
    )
    status_map = {row[0].value: row[1] for row in status_counts}

    today_count = (await db.execute(
        select(func.count(Complaint.id)).where(Complaint.created_at >= today_start)
    )).scalar() or 0

    week_count = (await db.execute(
        select(func.count(Complaint.id)).where(Complaint.created_at >= week_start)
    )).scalar() or 0

    avg_resolution = (await db.execute(
        select(
            func.avg(
                func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600
            )
        ).where(Complaint.resolved_at.isnot(None))
    )).scalar()

    total = sum(status_map.values())

    return {
        "total_complaints": total,
        "pending": status_map.get("pending", 0),
        "in_progress": status_map.get("in_progress", 0),
        "resolved": status_map.get("resolved", 0),
        "escalated": status_map.get("escalated", 0),
        "avg_resolution_hours": round(avg_resolution, 1) if avg_resolution else None,
        "complaints_today": today_count,
        "complaints_this_week": week_count,
    }


async def get_heatmap_data(db: AsyncSession) -> list[dict]:
    """Get complaint locations for heatmap visualization."""
    result = await db.execute(
        select(
            Complaint.latitude,
            Complaint.longitude,
            Complaint.category,
            Complaint.priority,
        ).where(
            and_(
                Complaint.latitude.isnot(None),
                Complaint.longitude.isnot(None),
            )
        )
    )

    return [
        {
            "latitude": row[0],
            "longitude": row[1],
            "category": row[2].value,
            "intensity": row[3] or 2,
        }
        for row in result
    ]
