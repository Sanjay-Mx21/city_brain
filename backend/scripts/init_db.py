"""
City Brain database initialization.
Creates all tables. Run this before seed_data.py.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, engine
from app.models.models import *  # noqa: F403 - register all models with SQLAlchemy


async def init_db():
    print("Initializing City Brain database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
