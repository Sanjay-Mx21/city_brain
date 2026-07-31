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
from app.services.llm_pipeline import normalize_location_text, parse_complaint

logger = logging.getLogger(__name__)

SLA_HOURS = {1: 720, 2: 168, 3: 72, 4: 24, 5: 4}
ACTIVE_STATUSES = {
    ComplaintStatus.PENDING.value,
    ComplaintStatus.ASSIGNED.value,
    ComplaintStatus.IN_PROGRESS.value,
    ComplaintStatus.ESCALATED.value,
}


def get_sla_state(c: Complaint) -> tuple[Optional[str], Optional[float], bool]:
    if not c.sla_deadline:
        return None, None, False

    end_time = c.resolved_at if c.resolved_at else datetime.utcnow()
    hours_remaining = round((c.sla_deadline - end_time).total_seconds() / 3600, 1)

    if c.status in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value):
        return ("met" if hours_remaining >= 0 else "missed"), hours_remaining, False
    if hours_remaining < 0:
        return "overdue", hours_remaining, True
    if hours_remaining <= 24:
        return "due_soon", hours_remaining, False
    return "on_track", hours_remaining, False


def complaint_to_response(c: Complaint) -> ComplaintResponse:
    sla_status, sla_hours_remaining, is_overdue = get_sla_state(c)
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
        image_url=c.image_url,
        image_verification_status=c.image_verification_status,
        image_verification_confidence=c.image_verification_confidence,
        image_verification_notes=c.image_verification_notes,
        created_at=c.created_at,
        updated_at=c.updated_at,
        resolved_at=c.resolved_at,
        sla_deadline=c.sla_deadline,
        sla_status=sla_status,
        sla_hours_remaining=sla_hours_remaining,
        is_overdue=is_overdue,
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
    returned_complaint_ids = set()

    for complaint_data in parsed.complaints:
        department = await get_department_by_code(db, complaint_data.department)

        ward = None
        if latitude and longitude:
            ward = await find_nearest_ward(db, latitude, longitude)

        sla_hours = SLA_HOURS.get(complaint_data.severity, 72)
        sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

        duplicate = await find_active_duplicate_complaint(
            db=db,
            category=complaint_data.category,
            department_id=department.id if department else None,
            location_text=complaint_data.location_text,
            latitude=latitude,
            longitude=longitude,
        )
        if duplicate and duplicate.id not in returned_complaint_ids:
            logger.info(
                "Reusing existing ticket %s for duplicate %s at %s",
                duplicate.ticket_id,
                complaint_data.category,
                complaint_data.location_text,
            )
            created_complaints.append(duplicate)
            returned_complaint_ids.add(duplicate.id)
            continue

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
            status=ComplaintStatus.PENDING.value,
            sla_deadline=sla_deadline,
        )

        db.add(complaint)
        await db.flush()

        # Use DB-assigned ID for a collision-free ticket ID
        complaint.ticket_id = f"CB-2026-{complaint.id:05d}"

        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=None,
            new_status=ComplaintStatus.PENDING.value,
            changed_by_id=citizen_id,
            notes="Complaint auto-created by City Brain AI",
        )
        db.add(history)

        created_complaints.append(complaint)
        returned_complaint_ids.add(complaint.id)

    await db.commit()

    for c in created_complaints:
        await db.refresh(c, ["department", "ward"])

    return created_complaints


async def split_legacy_mixed_complaint(
    db: AsyncSession,
    complaint: Complaint,
) -> list[Complaint]:
    """
    Upgrade old demo tickets that were created before multi-issue splitting.
    The old generic ticket is closed and the real department tickets are reused
    or created, so officer portals receive one ticket per department.
    """
    status = complaint.status.value if hasattr(complaint.status, "value") else complaint.status
    if status == ComplaintStatus.CLOSED.value:
        return []
    if complaint.category != "other" and complaint.ai_confidence and complaint.ai_confidence >= 0.5:
        return []

    parsed = await parse_complaint(complaint.original_text, language=complaint.original_language or "en")
    actionable = [
        item for item in parsed.complaints
        if item.category != "other" and item.department != "GENERAL"
    ]
    unique_categories = {item.category for item in actionable}
    if len(actionable) < 2 or len(unique_categories) < 2:
        return []

    replacement_tickets = []
    replacement_ids = set()

    for item in actionable:
        department = await get_department_by_code(db, item.department)
        sla_hours = SLA_HOURS.get(item.severity, 72)

        duplicate = await find_active_duplicate_complaint(
            db=db,
            category=item.category,
            department_id=department.id if department else None,
            location_text=item.location_text or complaint.location_text,
            latitude=complaint.latitude,
            longitude=complaint.longitude,
        )
        if duplicate:
            if duplicate.id not in replacement_ids:
                replacement_tickets.append(duplicate)
                replacement_ids.add(duplicate.id)
            continue

        new_complaint = Complaint(
            ticket_id="PENDING",
            citizen_id=complaint.citizen_id,
            original_text=complaint.original_text,
            original_language=parsed.detected_language,
            translated_text=parsed.translated_text or complaint.translated_text,
            category=item.category,
            description=item.description,
            location_text=item.location_text or complaint.location_text,
            latitude=complaint.latitude,
            longitude=complaint.longitude,
            department_id=department.id if department else complaint.department_id,
            ward_id=complaint.ward_id,
            priority=item.severity,
            ai_confidence=item.confidence,
            status=ComplaintStatus.PENDING.value,
            sla_deadline=datetime.utcnow() + timedelta(hours=sla_hours),
        )
        db.add(new_complaint)
        await db.flush()
        new_complaint.ticket_id = f"CB-2026-{new_complaint.id:05d}"
        db.add(ComplaintStatusHistory(
            complaint_id=new_complaint.id,
            old_status=None,
            new_status=ComplaintStatus.PENDING.value,
            changed_by_id=complaint.citizen_id,
            notes=f"Split from legacy mixed ticket {complaint.ticket_id}",
        ))
        replacement_tickets.append(new_complaint)
        replacement_ids.add(new_complaint.id)

    if len(replacement_tickets) >= 2:
        old_status = complaint.status
        complaint.status = ComplaintStatus.CLOSED.value
        complaint.resolved_at = datetime.utcnow()
        complaint.resolution_notes = (
            "Superseded by split tickets: "
            + ", ".join(ticket.ticket_id for ticket in replacement_tickets)
        )
        db.add(ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=old_status,
            new_status=ComplaintStatus.CLOSED.value,
            changed_by_id=complaint.citizen_id,
            notes=complaint.resolution_notes,
        ))
        await db.commit()
        for ticket in replacement_tickets:
            await db.refresh(ticket, ["department", "ward"])
        return replacement_tickets

    return []


async def find_active_duplicate_complaint(
    db: AsyncSession,
    category: str,
    department_id: Optional[int],
    location_text: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
) -> Optional[Complaint]:
    """Return an active existing ticket for the same issue and location."""
    location_key = normalize_location_text(location_text)
    has_gps = latitude is not None and longitude is not None
    if not location_key and not has_gps:
        return None

    conditions = [
        Complaint.category == category,
        Complaint.status.in_(ACTIVE_STATUSES),
    ]
    if department_id is not None:
        conditions.append(Complaint.department_id == department_id)

    result = await db.execute(
        select(Complaint)
        .where(and_(*conditions))
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        .order_by(Complaint.created_at.asc())
        .limit(200)
    )

    for complaint in result.scalars().all():
        existing_key = normalize_location_text(complaint.location_text)
        if location_key and existing_key and location_key == existing_key:
            return complaint

        if (
            has_gps
            and complaint.latitude is not None
            and complaint.longitude is not None
            and abs(complaint.latitude - latitude) <= 0.0008
            and abs(complaint.longitude - longitude) <= 0.0008
        ):
            return complaint

    return None


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
    legacy_query = (
        select(Complaint)
        .where(
            and_(
                Complaint.citizen_id == citizen_id,
                Complaint.status != ComplaintStatus.CLOSED.value,
                Complaint.category == "other",
            )
        )
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        .order_by(Complaint.created_at.desc())
        .limit(20)
    )
    legacy_result = await db.execute(legacy_query)
    for legacy_complaint in legacy_result.scalars().all():
        await split_legacy_mixed_complaint(db, legacy_complaint)

    active_condition = and_(
        Complaint.citizen_id == citizen_id,
        Complaint.status != ComplaintStatus.CLOSED.value,
    )
    count_q = select(func.count(Complaint.id)).where(active_condition)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Complaint)
        .where(active_condition)
        .options(selectinload(Complaint.department), selectinload(Complaint.ward))
        .order_by(Complaint.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    complaints = result.scalars().all()

    return complaints, total


async def get_complaints_for_officer(
    db: AsyncSession, officer_user_id: int, department_id: Optional[int],
    status_filter: Optional[str] = None,
    sort_by: str = "priority",
    page: int = 1, per_page: int = 20
) -> tuple[list[Complaint], int]:
    """Get complaints assigned to a department (for officer view)."""
    conditions = []
    if status_filter != ComplaintStatus.CLOSED.value:
        conditions.append(Complaint.status != ComplaintStatus.CLOSED.value)
    if department_id is not None:
        conditions.append(Complaint.department_id == department_id)
    if status_filter:
        conditions.append(Complaint.status == status_filter)

    count_q = select(func.count(Complaint.id))
    if conditions:
        count_q = count_q.where(and_(*conditions))
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Complaint)
        .options(
            selectinload(Complaint.department),
            selectinload(Complaint.ward),
            selectinload(Complaint.citizen),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if sort_by == "latest":
        query = query.order_by(Complaint.created_at.desc())
    else:
        query = query.order_by(Complaint.priority.desc(), Complaint.created_at.asc())
    if conditions:
        query = query.where(and_(*conditions))
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
        .options(
            selectinload(Complaint.department),
            selectinload(Complaint.ward),
            selectinload(Complaint.citizen),
        )
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise ValueError(f"Complaint {complaint_id} not found")

    old_status = complaint.status

    complaint.status = update.status
    if update.status == ComplaintStatus.RESOLVED.value:
        complaint.resolved_at = datetime.utcnow()
    if update.status == ComplaintStatus.ESCALATED.value:
        complaint.escalated_at = datetime.utcnow()
    if update.status in (ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value):
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
    status_map = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1]
        for row in status_counts
    }

    today_count = (await db.execute(
        select(func.count(Complaint.id)).where(Complaint.created_at >= today_start)
    )).scalar() or 0

    week_count = (await db.execute(
        select(func.count(Complaint.id)).where(Complaint.created_at >= week_start)
    )).scalar() or 0

    resolved_rows = await db.execute(
        select(Complaint.created_at, Complaint.resolved_at)
        .where(Complaint.resolved_at.isnot(None))
    )
    durations = [
        (resolved_at - created_at).total_seconds() / 3600
        for created_at, resolved_at in resolved_rows
        if created_at and resolved_at
    ]
    avg_resolution = sum(durations) / len(durations) if durations else None

    total = sum(status_map.values())
    active_rows = await db.execute(
        select(Complaint.status, Complaint.sla_deadline).where(
            Complaint.sla_deadline.isnot(None)
        )
    )
    overdue = 0
    due_soon = 0
    for status, sla_deadline in active_rows:
        status_value = status.value if hasattr(status, "value") else status
        if status_value in (ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value):
            continue
        if sla_deadline < now:
            overdue += 1
        elif sla_deadline <= now + timedelta(hours=24):
            due_soon += 1

    return {
        "total_complaints": total,
        "pending": status_map.get("pending", 0),
        "in_progress": status_map.get("in_progress", 0),
        "resolved": status_map.get("resolved", 0),
        "escalated": status_map.get("escalated", 0),
        "overdue": overdue,
        "due_soon": due_soon,
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
            "category": row[2].value if hasattr(row[2], "value") else row[2],
            "intensity": row[3] or 2,
        }
        for row in result
    ]
