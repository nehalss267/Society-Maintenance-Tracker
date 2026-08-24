"""Pytest fixtures - isolated test database + in-process ASGI client."""
import os
import uuid

# Must be set BEFORE app imports read Settings
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5433/society_test_db"
)
os.environ["JOB_EXECUTION_MODE"] = "inline"
os.environ["CRON_SECRET"] = "test-cron"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec_test"

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB_URL = os.environ["DATABASE_URL"]
ADMIN_URL = TEST_DB_URL.rsplit("/", 1)[0] + "/society_db"

admin_engine = create_engine(
    ADMIN_URL, isolation_level="AUTOCOMMIT"
)


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Create a fresh schema in the test DB once per run."""
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS society_test_db WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE society_test_db"))

    from sqlalchemy import create_engine

    test_engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    test_engine.dispose()

    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS society_test_db WITH (FORCE)"))


@pytest.fixture()
def db_session(_test_database):
    from app.core.database import SessionLocal

    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_session):
    """In-process HTTP client wired to a test-DB-backed dependency override."""
    def _override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _override

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def register(client, email=None, password="Test@12345", name="Test User"):
    email = email or f"u{uuid.uuid4().hex[:8]}@t.dev"

    r = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text

    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text

    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def login_as(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text

    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def resident(client):
    return register(client)
