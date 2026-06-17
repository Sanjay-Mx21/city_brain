"""
Lightweight schema updates for the local SQLite demo database.
Production deployments should use migrations.
"""

from app.core.config import settings


async def ensure_local_schema_updates(conn):
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    result = await conn.exec_driver_sql("PRAGMA table_info(complaints)")
    existing_columns = {row[1] for row in result.fetchall()}
    columns = {
        "image_verification_status": "VARCHAR(40)",
        "image_verification_confidence": "FLOAT",
        "image_verification_notes": "TEXT",
    }
    for name, column_type in columns.items():
        if name not in existing_columns:
            await conn.exec_driver_sql(f"ALTER TABLE complaints ADD COLUMN {name} {column_type}")
