"""
MedScope DCMS — Automated Test Configuration & Safety Guard (Prompt 08 Part B & Prompt 09)

Guarantees:
1. Hard Guard: Test session REFUSES to start if test DB URL points to development/main DB.
2. Complete Isolation: Tests execute strictly against an isolated PostgreSQL database (e.g., medscope_test).
3. Migration Verification: Runs the full Alembic migration chain from base to head at session start.
4. Deterministic Baseline Seed: Seeds tenant 'center-seba-01', staff, tests catalog, components, and baseline data.
5. In-Process Execution: Tests run purely in-process via FastAPI TestClient (no live server on port 8000).
6. Real Session Authentication (Prompt 09): Pre-seeds Argon2id credentials and deterministic test sessions.
"""

import os
import sys
import hashlib
from datetime import timedelta
from uuid import uuid4
from pathlib import Path
import pytest
from sqlalchemy.engine.url import make_url

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ---------------------------------------------------------------------------
# 1. Resolve & Validate Database URLs before any ORM or settings are loaded
# ---------------------------------------------------------------------------
def _load_main_db_url() -> str:
    """Reads main database URL from environment or backend/.env file."""
    if os.environ.get("MAIN_DATABASE_URL"):
        return os.environ["MAIN_DATABASE_URL"].strip()
    env_file = BASE_DIR / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return "postgresql+psycopg://medscope_app:1234@127.0.0.1:5432/medscope_dcms"


MAIN_DB_URL = _load_main_db_url()
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    parsed_main = make_url(MAIN_DB_URL)
    main_dbname = parsed_main.database or "medscope_dcms"
    TEST_DB_URL = MAIN_DB_URL.replace(f"/{main_dbname}", "/medscope_test")
    os.environ["TEST_DATABASE_URL"] = TEST_DB_URL


# ---------------------------------------------------------------------------
# 2. Hard Guard Enforcement
# ---------------------------------------------------------------------------
def enforce_safety_guard(main_url_str: str, test_url_str: str) -> None:
    """Refuses to start if test database URL points to or resolves to the main/production database."""
    u_main = make_url(main_url_str)
    u_test = make_url(test_url_str)

    main_host = (u_main.host or "127.0.0.1").replace("localhost", "127.0.0.1")
    test_host = (u_test.host or "127.0.0.1").replace("localhost", "127.0.0.1")
    main_port = u_main.port or 5432
    test_port = u_test.port or 5432
    main_db = (u_main.database or "").strip().lower()
    test_db = (u_test.database or "").strip().lower()

    if (main_host == test_host and main_port == test_port and main_db == test_db) or (test_db in ["medscope_dcms", "medscope_prod", "medscope"]):
        raise pytest.UsageError(
            f"\n"
            f"{'=' * 78}\n"
            f"FATAL SAFETY GUARD VIOLATION (Prompt 08 Part B):\n"
            f"Automated test session refused to start.\n"
            f"TEST_DATABASE_URL resolves to the primary QA / production database:\n"
            f"  Host: {test_host}:{test_port} | Database: '{test_db}'\n"
            f"Tests must NEVER run against or write fake records to the primary database.\n"
            f"Please configure a distinct TEST_DATABASE_URL (e.g., .../medscope_test).\n"
            f"{'=' * 78}\n"
        )


# Run the guard immediately upon module load
enforce_safety_guard(MAIN_DB_URL, TEST_DB_URL)

# Force environment variables so all backend modules and Alembic connect to TEST_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ALEMBIC_DATABASE_URL"] = TEST_DB_URL


# ---------------------------------------------------------------------------
# Test Credentials & Deterministic Session Tokens (Prompt 09)
# ---------------------------------------------------------------------------
TEST_PASSWORD_DEFAULT = "test_pass_secure_2026"
RECEPTIONIST_AUTH_TOKEN = "test_token_receptionist_fatima_2026"
CASHIER_AUTH_TOKEN = "test_token_cashier_fatima_2026"
ADMIN_AUTH_TOKEN = "test_token_admin_tariq_2026"
TECH_KAMAL_AUTH_TOKEN = "test_token_tech_kamal_2026"
TECH_NASRIN_AUTH_TOKEN = "test_token_tech_nasrin_2026"

RECEPTIONIST_HEADERS = {
    "Authorization": f"Bearer {RECEPTIONIST_AUTH_TOKEN}",
    "X-Requested-With": "XMLHttpRequest",
    "X-Tenant-Id": "center-seba-01",
}

CASHIER_HEADERS = {
    "Authorization": f"Bearer {CASHIER_AUTH_TOKEN}",
    "X-Requested-With": "XMLHttpRequest",
    "X-Tenant-Id": "center-seba-01",
}

ADMIN_HEADERS = {
    "Authorization": f"Bearer {ADMIN_AUTH_TOKEN}",
    "X-Requested-With": "XMLHttpRequest",
    "X-Tenant-Id": "center-seba-01",
}

TECH_KAMAL_HEADERS = {
    "Authorization": f"Bearer {TECH_KAMAL_AUTH_TOKEN}",
    "X-Requested-With": "XMLHttpRequest",
    "X-Tenant-Id": "center-seba-01",
}


# ---------------------------------------------------------------------------
# 3. Test Session Setup (Alembic Chain, Deterministic Seed, & Auth Sessions)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Session-scoped fixture: runs Alembic migrations from base to head and seeds baseline test data."""
    # 1. Run Alembic upgrade head against test DB
    from alembic import command
    from alembic.config import Config

    alembic_ini_path = str(BASE_DIR / "backend" / "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")

    # 2. Redirect core database engine and SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import backend.app.core.database as core_db

    test_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    core_db.engine = test_engine
    core_db.SessionLocal = TestSession

    # 3. Deterministic Seed into test DB
    from backend.scripts.seed import seed_development_data
    from backend.app.models.test import Test, TestComponent
    from backend.app.models.user import Staff, StaffRole, AuthSession
    from backend.app.services.auth_service import hash_password
    from backend.app.core.timezone import utc_now
    from sqlalchemy import select

    # Run base seed
    seed_development_data()

    db = TestSession()
    try:
        # 3a. Ensure CBC components exist for Result Entry / flags testing
        cbc = db.execute(select(Test).where(Test.code == "CBC")).scalar_one_or_none()
        if cbc:
            existing_comps = db.execute(
                select(TestComponent).where(TestComponent.test_id == cbc.id)
            ).scalars().all()
            if not existing_comps:
                comps = [
                    TestComponent(
                        tenant_id=cbc.tenant_id,
                        test_id=cbc.id,
                        code="HGB",
                        name="Hemoglobin",
                        unit="g/dL",
                        ref_min=12.0,
                        ref_max=16.0,
                        critical_min=7.0,
                        critical_max=20.0,
                        impossible_min=2.0,
                        impossible_max=25.0,
                        sort_order=1,
                        active=True,
                    ),
                    TestComponent(
                        tenant_id=cbc.tenant_id,
                        test_id=cbc.id,
                        code="WBC",
                        name="Total WBC Count",
                        unit="x10^3/uL",
                        ref_min=4.0,
                        ref_max=11.0,
                        critical_min=2.0,
                        critical_max=30.0,
                        impossible_min=0.5,
                        impossible_max=100.0,
                        sort_order=2,
                        active=True,
                    ),
                    TestComponent(
                        tenant_id=cbc.tenant_id,
                        test_id=cbc.id,
                        code="PLT",
                        name="Platelet Count",
                        unit="x10^3/uL",
                        ref_min=150.0,
                        ref_max=450.0,
                        critical_min=50.0,
                        critical_max=1000.0,
                        impossible_min=10.0,
                        impossible_max=2000.0,
                        sort_order=3,
                        active=True,
                    ),
                ]
                db.add_all(comps)

        # 3b. Seed Argon2id passwords for existing staff
        hashed_pwd = hash_password(TEST_PASSWORD_DEFAULT)
        all_staff = db.execute(select(Staff)).scalars().all()
        for s in all_staff:
            s.password_hash = hashed_pwd
            s.failed_attempts = 0
            s.locked_at = None

        # 3c. Seed Staff Roles
        role_assignments = [
            (1, "RECEPTIONIST", True),
            (1, "CASHIER", False),
            (2, "ADMIN", True),
            (2, "OWNER", False),
            (3, "LAB_TECH", True),
            (4, "LAB_TECH", True),
        ]
        for staff_id, r_name, is_pri in role_assignments:
            existing_role = db.execute(
                select(StaffRole).where(StaffRole.staff_id == staff_id, StaffRole.role == r_name)
            ).scalar_one_or_none()
            if not existing_role:
                db.add(StaffRole(
                    staff_id=staff_id,
                    role=r_name,
                    is_primary=is_pri,
                    created_at=utc_now(),
                ))

        # 3d. Seed Deterministic Active Test Sessions
        test_sessions_data = [
            (1, RECEPTIONIST_AUTH_TOKEN, "RECEPTIONIST"),
            (1, CASHIER_AUTH_TOKEN, "CASHIER"),
            (2, ADMIN_AUTH_TOKEN, "ADMIN"),
            (3, TECH_KAMAL_AUTH_TOKEN, "LAB_TECH"),
            (4, TECH_NASRIN_AUTH_TOKEN, "LAB_TECH"),
        ]
        for staff_id, raw_tok, acting_r in test_sessions_data:
            tok_hash = hashlib.sha256(raw_tok.encode("utf-8")).hexdigest()
            existing_session = db.execute(
                select(AuthSession).where(AuthSession.session_token_hash == tok_hash)
            ).scalar_one_or_none()
            if existing_session:
                existing_session.revoked_at = None
                existing_session.expires_at = utc_now() + timedelta(days=7)
                existing_session.acting_role = acting_r
                existing_session.last_seen_at = utc_now()
            else:
                db.add(AuthSession(
                    id=uuid4().hex,
                    session_token_hash=tok_hash,
                    staff_id=staff_id,
                    tenant_id="center-seba-01",
                    acting_role=acting_r,
                    created_at=utc_now(),
                    expires_at=utc_now() + timedelta(days=7),
                    last_seen_at=utc_now(),
                    revoked_at=None,
                    user_agent="pytest-testclient",
                    ip_address="127.0.0.1",
                ))

        # 3e. Synchronize sequences to prevent duplicate key errors on inserts
        from sqlalchemy import text
        db.execute(text("SELECT setval('staff_id_seq', COALESCE((SELECT MAX(id) FROM staff), 1))"))
        db.execute(text("SELECT setval('staff_roles_id_seq', COALESCE((SELECT MAX(id) FROM staff_roles), 1))"))
        db.commit()
    finally:
        db.close()

    yield test_engine


# ---------------------------------------------------------------------------
# 4. Centralized Fixtures: in-process client and db_session
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client(setup_test_database):
    """
    Session-scoped in-process FastAPI TestClient.
    Binds strictly to isolated test database.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.database import get_db, SessionLocal

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://testserver/api/v1") as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session(setup_test_database):
    """Function-scoped database session bound to the isolated test database."""
    from backend.app.core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
