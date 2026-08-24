from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from tests.conftest import register


def _elevate(email, role):
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == email).values(role=role))
        db.commit()


def _user_id(email):
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def test_resident_blocked_from_admin_users(client):
    headers, _ = register(client)

    r = client.get("/api/admin/users", headers=headers)
    assert r.status_code == 403


def test_committee_cannot_change_roles(client):
    committee_headers, committee_email = register(client)
    _elevate(committee_email, UserRole.COMMITTEE)

    victim_headers, victim_email = register(client)
    victim_id = _user_id(victim_email)

    r = client.patch(
        f"/api/admin/users/{victim_id}/role",
        json={"role": "ADMIN"},
        headers=committee_headers,
    )
    assert r.status_code == 403


def test_accountant_blocked_from_complaint_admin(client):
    acc_headers, acc_email = register(client)
    _elevate(acc_email, UserRole.ACCOUNTANT)

    r = client.get("/api/admin/complaints", headers=acc_headers)
    assert r.status_code == 403


def test_admin_changes_role_and_audits(client):
    from app.models.audit_log import AuditLog

    admin_headers, admin_email = register(client)
    _elevate(admin_email, UserRole.ADMIN)

    victim_headers, victim_email = register(client)
    victim_id = _user_id(victim_email)

    with SessionLocal() as db:
        before = db.scalar(
            select(AuditLog.id).where(AuditLog.action == "USER_ROLE_CHANGED")
        )

    r = client.patch(
        f"/api/admin/users/{victim_id}/role",
        json={"role": "ACCOUNTANT"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "ACCOUNTANT"

    with SessionLocal() as db:
        audit_count = len(
            db.scalars(select(AuditLog.id).where(AuditLog.action == "USER_ROLE_CHANGED")).all()
        )
        new_role = db.scalar(select(User.role).where(User.email == victim_email))

    assert audit_count >= (1 if before is None else 2)
    assert new_role == UserRole.ACCOUNTANT


def test_admin_cannot_demote_self(client):
    admin_headers, admin_email = register(client)
    _elevate(admin_email, UserRole.ADMIN)

    uid = _user_id(admin_email)

    r = client.patch(
        f"/api/admin/users/{uid}/role",
        json={"role": "RESIDENT"},
        headers=admin_headers,
    )
    assert r.status_code == 400
