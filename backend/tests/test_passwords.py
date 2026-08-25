"""Password management: forgot / reset / change flows."""
import re

from app.models.user import User
from sqlalchemy import select

from tests.conftest import register


def _latest_reset_token(caplog):
    """Extract the raw reset token from log-only email fallback output."""
    bodies = [r.getMessage() for r in caplog.records if "email:fallback" in r.getMessage()]
    assert bodies, "reset email was not logged"
    match = re.search(r"/reset-password\?token=([A-Za-z0-9_\-]+)", bodies[-1])
    assert match, f"no token in logged email: {bodies[-1]}"
    return match.group(1)


def test_forgot_password_never_reveals_account_existence(client, caplog):
    r = client.post("/api/auth/forgot-password", json={"email": "ghost@t.dev"})
    assert r.status_code == 202
    assert "reset link" in r.json()["message"]

    r = client.post("/api/auth/forgot-password", json={"email": "someone@t.dev"})
    assert r.status_code == 202
    assert r.json()["message"].startswith("If that email is registered")


def test_full_reset_flow(client, db_session, caplog):
    with caplog.at_level("INFO"):
        _, email = register(client)
        client.post(
            "/api/auth/forgot-password",
            json={"email": email},
        )
        token = _latest_reset_token(caplog)

    # weak new password rejected
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "nodigitshere"},
    )
    assert r.status_code == 422

    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "BrandNew1"},
    )
    assert r.status_code == 200

    # old password no longer works, new one does
    r = client.post("/api/auth/login", json={"email": email, "password": "Test@12345"})
    assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": email, "password": "BrandNew1"})
    assert r.status_code == 200

    # token is single-use
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "AnotherOne2"},
    )
    assert r.status_code == 400


def test_reset_token_invalid_and_expired(client, db_session):
    from datetime import datetime, timedelta

    import hashlib

    from app.models.password_reset import PasswordResetToken

    _, email = register(client)
    user = db_session.scalar(select(User).where(User.email == email))

    raw = "raw-token-for-expiry-test-abcdef"
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        created_at=datetime.utcnow(),
    )
    db_session.add(row)
    db_session.commit()

    r = client.post(
        "/api/auth/reset-password",
        json={"token": raw, "new_password": "FreshPass1"},
    )
    assert r.status_code == 400

    r = client.post(
        "/api/auth/reset-password",
        json={"token": "totally-bogus-token-value", "new_password": "FreshPass1"},
    )
    assert r.status_code == 400


def test_change_password_flow(client):
    headers, email = register(client)

    r = client.patch(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "WrongOld1", "new_password": "Changed123"},
    )
    assert r.status_code == 400

    r = client.patch(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Test@12345", "new_password": "nodigits"},
    )
    assert r.status_code == 422

    r = client.patch(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Test@12345", "new_password": "Changed123"},
    )
    assert r.status_code == 200

    r = client.post("/api/auth/login", json={"email": email, "password": "Changed123"})
    assert r.status_code == 200


def test_change_password_requires_auth(client):
    r = client.patch(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert r.status_code in (401, 403)
