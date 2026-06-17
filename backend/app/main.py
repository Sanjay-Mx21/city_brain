"""
City Brain — Main Application
FastAPI entry point with all routes, middleware, and startup events.
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine, Base
from app.core.schema_updates import ensure_local_schema_updates
from app.api.routes import admin, assistant, auth, complaints, officer, whatsapp

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: Create tables if they don't exist
    logger.info("🧠 City Brain starting up...")
    os.makedirs("uploads", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_local_schema_updates(conn)
    logger.info("✅ Database tables ready")

    yield

    # Shutdown
    logger.info("🧠 City Brain shutting down...")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="City Brain API",
    description="AI-Powered Unified Civic Intelligence System for Bengaluru",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────

app.include_router(auth.router, prefix="/api/v1")
app.include_router(complaints.router, prefix="/api/v1")
app.include_router(officer.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(whatsapp.router, prefix="/api/v1")

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "City Brain API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
