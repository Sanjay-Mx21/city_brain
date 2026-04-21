"""
City Brain — Database Initialization
Creates all tables. Run this before seed_data.py.
"""

import asyncio
from app.core.database import engine, Base
from app.models.models import *  # noqa: Import all models so they register


async def init_db():
    print("🧠 Initializing City Brain database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
