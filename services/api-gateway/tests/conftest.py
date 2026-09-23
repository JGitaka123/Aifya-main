# ruff: noqa: E402,I001
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.elements import TextClause

# Use SQLite for tests.
TEST_DATABASE_PATH = Path("test.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///./{TEST_DATABASE_PATH}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = (
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
# Test client source IPs are not Safaricom ranges — disable callback IP
# enforcement here (individual tests re-enable it to assert the guard).
os.environ["MPESA_CALLBACK_IP_ENFORCE"] = "false"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    """Render PostgreSQL JSONB columns as JSON for SQLite-only tests."""
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID columns as text for SQLite-only tests."""
    return "CHAR(32)"


@compiles(TextClause, "sqlite")
def compile_text_sqlite(element, compiler, **kw):
    """Strip PostgreSQL JSONB casts from SQLite DDL defaults."""
    return compiler.visit_textclause(element, **kw).replace("::jsonb", "")


# PostgreSQL returns tz-aware datetimes for TIMESTAMPTZ columns; SQLite has no
# timezone support and returns naive values. Attach UTC on read for columns
# declared DateTime(timezone=True) so services can do tz-aware arithmetic,
# matching production behaviour.
from datetime import datetime as _datetime, UTC

from sqlalchemy.dialects.sqlite.base import DATETIME as SQLITE_DATETIME

_orig_datetime_result_processor = SQLITE_DATETIME.result_processor


def _tz_aware_result_processor(self, dialect, coltype):
    """Wrap SQLite datetime parsing to restore UTC tzinfo on timezone=True columns."""
    proc = _orig_datetime_result_processor(self, dialect, coltype)

    def process(value):
        dt = proc(value) if proc else value
        if self.timezone and isinstance(dt, _datetime) and dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    return process


SQLITE_DATETIME.result_processor = _tz_aware_result_processor


from app.auth import license_check
from app.auth.dependencies import CurrentUser, get_current_user
from app.database import Base, get_db
from app.schemas.licensing import TIER_ENTITLEMENTS


async def _get_test_redis() -> None:
    return None


async def _get_test_entitlements(
    facility_id: str, db: AsyncSession
) -> dict[str, object]:
    entitlements = TIER_ENTITLEMENTS["enterprise"]
    return {
        "tier": "enterprise",
        "enabled_modules": entitlements["enabled_modules"],
        "feature_flags": entitlements["feature_flags"],
        "max_users": entitlements["max_users"],
        "max_patients": entitlements["max_patients"],
        "is_valid": True,
        "in_grace_period": False,
    }


license_check._get_redis = _get_test_redis
license_check._get_entitlements = _get_test_entitlements

from app.main import app

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
_schema_ready = False

FACILITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DB_SESSION_TEST_MODULES = {
    "test_finance_engine.py",
    "test_finance_reports.py",
    "test_finance_backfill.py",
    "test_lab_billing.py",
    "test_payroll_engine.py",
    "test_employee_encryption.py",
    "test_theatre_seed.py",
    "test_inventory_guard.py",
    "test_service_billing.py",
}


@pytest.fixture(scope="session", autouse=True)
def dispose_test_engine() -> Generator[None, None, None]:
    """Close the SQLite async engine so pytest can exit cleanly."""
    yield
    asyncio.run(engine.dispose())
    TEST_DATABASE_PATH.unlink(missing_ok=True)
    Path("test.db-journal").unlink(missing_ok=True)


def _test_needs_database(request) -> bool:
    """Return whether the test needs the SQLite schema fixture."""
    module_name = request.node.path.name
    return "client" in request.fixturenames or module_name in DB_SESSION_TEST_MODULES


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Test DB session override."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def override_get_current_user() -> CurrentUser:
    """Mock auth for tests — returns a test user."""
    return CurrentUser(
        user_id=USER_ID,
        facility_id=FACILITY_ID,
        email="test@aifya.health",
        roles=["admin", "doctor"],
        name="Test User",
    )


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture(autouse=True)
async def setup_database(request) -> AsyncGenerator[None, None]:
    """Create and drop tables for each test."""
    if not _test_needs_database(request):
        yield
        return

    global _schema_ready

    async with engine.begin() as conn:
        if not _schema_ready:
            await conn.run_sync(Base.metadata.create_all)
            _schema_ready = True
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_patient_data() -> dict:
    """Sample patient registration payload."""
    return {
        "first_name": "Wanjiku",
        "middle_name": "Njeri",
        "last_name": "Kamau",
        "date_of_birth": "1990-05-15",
        "gender": "female",
        "national_id": "29384756",
        "phone_number": "0712345678",
        "county": "Nairobi",
        "sub_county": "Westlands",
        "ward": "Parklands",
        "next_of_kin_name": "John Kamau",
        "next_of_kin_phone": "0723456789",
        "next_of_kin_relationship": "Spouse",
        "sha_number": "SHA-1234567",
        "blood_group": "O+",
        "allergies": ["Penicillin"],
        "chronic_conditions": ["Hypertension"],
    }
