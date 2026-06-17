"""
City Brain — Pydantic Schemas
Request/Response models for all API endpoints
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# ──────────────────────────────────────────────
# AUTH SCHEMAS
# ──────────────────────────────────────────────

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    email: Optional[str] = None
    password: str = Field(..., min_length=6)
    preferred_language: str = Field(default="en", pattern=r"^(en|kn|hi)$")


class UserLogin(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    role: str
    preferred_language: str

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# COMPLAINT SCHEMAS
# ──────────────────────────────────────────────

class ComplaintSubmit(BaseModel):
    """What the citizen sends — just their raw message + optional location."""
    text: str = Field(..., min_length=5, max_length=5000,
                      description="Citizen's complaint in any language")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: Optional[str] = Field(default=None, description="Language code: en, kn, hi (auto-detected if null)")


class ComplaintParsed(BaseModel):
    """Single parsed complaint from LLM output."""
    category: str
    department: str
    description: str
    location_text: Optional[str] = None
    severity: int = Field(ge=1, le=5, default=2)
    confidence: float = Field(ge=0, le=1, default=0.8)


class LLMParseResponse(BaseModel):
    """Full LLM response — may contain multiple complaints from one message."""
    original_text: str
    translated_text: Optional[str] = None
    detected_language: str
    complaints: List[ComplaintParsed]


class ComplaintResponse(BaseModel):
    id: int
    ticket_id: str
    original_text: str
    translated_text: Optional[str] = None
    original_language: str
    category: str
    description: str
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    department_name: Optional[str] = None
    ward_name: Optional[str] = None
    priority: int
    ai_confidence: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    sla_status: Optional[str] = None
    sla_hours_remaining: Optional[float] = None
    is_overdue: bool = False
    image_url: Optional[str] = None
    image_verification_status: Optional[str] = None
    image_verification_confidence: Optional[float] = None
    image_verification_notes: Optional[str] = None

    class Config:
        from_attributes = True


class ComplaintListResponse(BaseModel):
    complaints: List[ComplaintResponse]
    total: int
    page: int
    per_page: int


class ComplaintSubmitResponse(BaseModel):
    """Returned to citizen after submission."""
    message: str
    localized_message: Optional[str] = None
    tickets: List[ComplaintResponse]
    total_complaints_detected: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = Field(default="en", pattern=r"^(en|kn|hi)$")


class ChatResponse(BaseModel):
    reply: str
    intent: str
    suggested_action: Optional[str] = None
    ticket_id: Optional[str] = None
    language: str = "en"


# ──────────────────────────────────────────────
# OFFICER SCHEMAS
# ──────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str = Field(..., description="New status: assigned, in_progress, resolved, escalated")
    notes: Optional[str] = None


class OfficerStats(BaseModel):
    total_assigned: int
    pending: int
    in_progress: int
    resolved: int
    escalated: int
    overdue: int = 0
    due_soon: int = 0
    avg_resolution_hours: Optional[float] = None


# ──────────────────────────────────────────────
# ADMIN / ANALYTICS SCHEMAS
# ──────────────────────────────────────────────

class WardStats(BaseModel):
    ward_id: int
    ward_name: str
    total_complaints: int
    pending: int
    resolved: int
    avg_resolution_hours: Optional[float] = None
    most_common_category: Optional[str] = None


class DepartmentStats(BaseModel):
    department_id: int
    department_name: str
    total_complaints: int
    pending: int
    resolved: int
    resolution_rate: float


class DashboardOverview(BaseModel):
    total_complaints: int
    pending: int
    in_progress: int
    resolved: int
    escalated: int
    overdue: int = 0
    due_soon: int = 0
    avg_resolution_hours: Optional[float] = None
    complaints_today: int
    complaints_this_week: int
    ward_stats: List[WardStats]
    department_stats: List[DepartmentStats]


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: int  # complaint count or severity weight
    category: Optional[str] = None


# ──────────────────────────────────────────────
# DEPARTMENT SCHEMA
# ──────────────────────────────────────────────

class DepartmentResponse(BaseModel):
    id: int
    name: str
    full_name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# WARD SCHEMA
# ──────────────────────────────────────────────

class WardResponse(BaseModel):
    id: int
    ward_number: int
    name: str
    zone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


# Resolve forward references
TokenResponse.model_rebuild()
