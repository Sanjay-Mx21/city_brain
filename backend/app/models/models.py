"""
City Brain ORM models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, Enum):
    CITIZEN = "citizen"
    OFFICER = "officer"
    ADMIN = "admin"


class ComplaintStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ComplaintCategory(str, Enum):
    ROAD_DAMAGE = "road_damage"
    POTHOLE = "pothole"
    STREETLIGHT = "streetlight"
    WATER_SUPPLY = "water_supply"
    WATER_LEAKAGE = "water_leakage"
    SEWAGE = "sewage"
    GARBAGE = "garbage"
    DRAINAGE = "drainage"
    ELECTRICITY = "electricity"
    POWER_OUTAGE = "power_outage"
    TREE_FALL = "tree_fall"
    ILLEGAL_CONSTRUCTION = "illegal_construction"
    NOISE_POLLUTION = "noise_pollution"
    PUBLIC_TRANSPORT = "public_transport"
    TRAFFIC_SIGNAL = "traffic_signal"
    PARK_MAINTENANCE = "park_maintenance"
    STRAY_ANIMALS = "stray_animals"
    ENCROACHMENT = "encroachment"
    OTHER = "other"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.CITIZEN.value, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)

    ward: Mapped[Optional["Ward"]] = relationship(back_populates="citizens")
    officer_profile: Mapped[Optional["Officer"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="citizen", foreign_keys="Complaint.citizen_id"
    )


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    officers: Mapped[list["Officer"]] = relationship(back_populates="department")
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="department")


class Ward(TimestampMixin, Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ward_number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    zone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    citizens: Mapped[list["User"]] = relationship(back_populates="ward")
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="ward")


class Officer(TimestampMixin, Base):
    __tablename__ = "officers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="officer_profile")
    department: Mapped["Department"] = relationship(back_populates="officers")


class Complaint(TimestampMixin, Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default=ComplaintCategory.OTHER.value, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=ComplaintStatus.PENDING.value, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    citizen: Mapped["User"] = relationship(back_populates="complaints", foreign_keys=[citizen_id])
    assigned_officer: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_officer_id])
    department: Mapped[Optional["Department"]] = relationship(back_populates="complaints")
    ward: Mapped[Optional["Ward"]] = relationship(back_populates="complaints")
    status_history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan"
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    complaint: Mapped["Complaint"] = relationship(back_populates="status_history")
    changed_by: Mapped[Optional["User"]] = relationship()
