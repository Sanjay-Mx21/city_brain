"""
Test setup: isolated SQLite database + upload dir, LLM pointed at a closed port
so the rule-based fallback parser is exercised.
"""

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="citybrain-test-")
os.environ.update({
    "APP_ENV": "test",
    "DEBUG": "false",
    "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db".replace("\\", "/"),
    "UPLOAD_DIR": os.path.join(_TMP, "uploads"),
    "OPEN_SOURCE_LLM_URL": "http://127.0.0.1:9/api/generate",
    "BHASHINI_API_KEY": "",
    "WHATSAPP_ENABLED": "false",
    "MAX_IMAGE_UPLOAD_MB": "1",
})

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.core.rate_limit import auth_rate_limit  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Department, Officer, User, UserRole  # noqa: E402


@pytest_asyncio.fixture
async def db_setup():
    os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        bbmp = Department(name="BBMP", full_name="Bruhat Bengaluru Mahanagara Palike")
        bescom = Department(name="BESCOM", full_name="Bangalore Electricity Supply Company")
        db.add_all([bbmp, bescom])
        await db.flush()

        admin = User(full_name="Admin", phone="+910000000001", password_hash=hash_password("adminpass1"),
                     role=UserRole.ADMIN.value)
        bbmp_officer = User(full_name="BBMP Officer", phone="+910000000002",
                            password_hash=hash_password("officerpass1"), role=UserRole.OFFICER.value)
        bescom_officer = User(full_name="BESCOM Officer", phone="+910000000003",
                              password_hash=hash_password("officerpass1"), role=UserRole.OFFICER.value)
        db.add_all([admin, bbmp_officer, bescom_officer])
        await db.flush()
        db.add_all([
            Officer(user_id=bbmp_officer.id, department_id=bbmp.id),
            Officer(user_id=bescom_officer.id, department_id=bescom.id),
        ])
        await db.commit()
        ids = {"admin": admin.id, "bbmp_officer": bbmp_officer.id, "bescom_officer": bescom_officer.id}

    auth_rate_limit._hits.clear()
    yield ids


@pytest_asyncio.fixture
async def client(db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def auth_header(user_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id), 'role': role})}"}


@pytest.fixture
def staff(db_setup):
    return {
        "admin": auth_header(db_setup["admin"], "admin"),
        "bbmp_officer": auth_header(db_setup["bbmp_officer"], "officer"),
        "bescom_officer": auth_header(db_setup["bescom_officer"], "officer"),
    }


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)
