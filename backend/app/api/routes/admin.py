"""
City Brain — Admin Dashboard Routes
City-wide analytics, heatmaps, ward/department stats
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import Complaint, ComplaintStatus, Department, Ward
from app.schemas.schemas import (
    DashboardOverview, WardStats, DepartmentStats, HeatmapPoint,
    DepartmentResponse, WardResponse
)
from app.services.complaint_service import get_dashboard_stats, get_heatmap_data

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get full admin dashboard overview."""
    stats = await get_dashboard_stats(db)

    # Ward-level stats
    ward_stats_raw = await db.execute(
        select(
            Ward.id,
            Ward.name,
            func.count(Complaint.id).label("total"),
            func.count(Complaint.id).filter(Complaint.status == ComplaintStatus.PENDING).label("pending"),
            func.count(Complaint.id).filter(Complaint.status == ComplaintStatus.RESOLVED).label("resolved"),
        )
        .outerjoin(Complaint, Complaint.ward_id == Ward.id)
        .group_by(Ward.id, Ward.name)
        .order_by(func.count(Complaint.id).desc())
    )

    ward_stats = [
        WardStats(
            ward_id=row[0],
            ward_name=row[1],
            total_complaints=row[2],
            pending=row[3],
            resolved=row[4],
        )
        for row in ward_stats_raw
    ]

    # Department-level stats
    dept_stats_raw = await db.execute(
        select(
            Department.id,
            Department.name,
            func.count(Complaint.id).label("total"),
            func.count(Complaint.id).filter(Complaint.status == ComplaintStatus.PENDING).label("pending"),
            func.count(Complaint.id).filter(Complaint.status == ComplaintStatus.RESOLVED).label("resolved"),
        )
        .outerjoin(Complaint, Complaint.department_id == Department.id)
        .group_by(Department.id, Department.name)
    )

    dept_stats = [
        DepartmentStats(
            department_id=row[0],
            department_name=row[1],
            total_complaints=row[2],
            pending=row[3],
            resolved=row[4],
            resolution_rate=round(row[4] / row[2] * 100, 1) if row[2] > 0 else 0,
        )
        for row in dept_stats_raw
    ]

    return DashboardOverview(
        **stats,
        ward_stats=ward_stats,
        department_stats=dept_stats,
    )


@router.get("/heatmap", response_model=list[HeatmapPoint])
async def get_heatmap(
    current_user: dict = Depends(require_role(["admin", "officer"])),
    db: AsyncSession = Depends(get_db),
):
    """Get complaint heatmap data points."""
    points = await get_heatmap_data(db)
    return [HeatmapPoint(**p) for p in points]


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(db: AsyncSession = Depends(get_db)):
    """List all departments (public)."""
    result = await db.execute(select(Department).where(Department.is_active == True))
    departments = result.scalars().all()
    return [DepartmentResponse.model_validate(d) for d in departments]


@router.get("/wards", response_model=list[WardResponse])
async def list_wards(db: AsyncSession = Depends(get_db)):
    """List all wards (public)."""
    result = await db.execute(select(Ward).order_by(Ward.ward_number))
    wards = result.scalars().all()
    return [WardResponse.model_validate(w) for w in wards]
