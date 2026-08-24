import uuid

from tests.conftest import register


def _create(client, headers, category="PLUMBING", description="Kitchen tap leaking badly"):
    r = client.post(
        "/api/complaints",
        headers=headers,
        data={"category": category, "description": description},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_resident_creates_complaint_with_sla(client):
    headers, _ = register(client)
    c = _create(client, headers)

    assert c["status"] == "OPEN"
    assert c["priority"] == "MEDIUM"
    assert c["is_overdue"] is False
    assert len(c["history"]) == 1


def test_resident_sees_only_own_complaints(client):
    a_headers, _ = register(client)
    b_headers, _ = register(client)

    mine = _create(client, a_headers)
    theirs = _create(client, b_headers)

    ids = [c["id"] for c in client.get("/api/complaints", headers=a_headers).json()]
    assert mine["id"] in ids
    assert theirs["id"] not in ids

    # detail access hidden as 404
    r = client.get(f"/api/complaints/{theirs['id']}", headers=a_headers)
    assert r.status_code == 404


def test_status_transitions_enforced(client):
    from sqlalchemy import select, update

    from app.core.database import SessionLocal
    from app.models.user import User, UserRole

    staff_headers, staff_email = register(client)
    res_headers, _ = register(client)

    with SessionLocal() as db:
        db.execute(update(User).where(User.email == staff_email).values(role=UserRole.COMMITTEE))
        db.commit()

    c = _create(client, res_headers)
    cid = c["id"]

    # RESOLVED is terminal
    r = client.patch(
        f"/api/admin/complaints/{cid}/status",
        json={"status": "IN_PROGRESS"},
        headers=staff_headers,
    )
    assert r.status_code == 200

    r = client.patch(
        f"/api/admin/complaints/{cid}/status",
        json={"status": "RESOLVED"},
        headers=staff_headers,
    )
    assert r.status_code == 200

    r = client.patch(
        f"/api/admin/complaints/{cid}/status",
        json={"status": "OPEN"},
        headers=staff_headers,
    )
    assert r.status_code == 409


def test_priority_change_audited(client):
    from sqlalchemy import select, update

    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole

    staff_headers, staff_email = register(client)
    res_headers, _ = register(client)

    with SessionLocal() as db:
        db.execute(update(User).where(User.email == staff_email).values(role=UserRole.COMMITTEE))
        db.commit()

    c = _create(client, res_headers, description=f"Urgent {uuid.uuid4().hex} flood issue")

    r = client.patch(
        f"/api/admin/complaints/{c['id']}/priority",
        json={"priority": "HIGH"},
        headers=staff_headers,
    )
    assert r.status_code == 200
    assert r.json()["priority"] == "HIGH"

    with SessionLocal() as db:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "COMPLAINT_PRIORITY_CHANGED",
                AuditLog.entity_id == c["id"],
            )
        )
    assert audit is not None
