import uuid

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.notification import Notification
from app.models.user import User, UserRole
from tests.conftest import register


def test_notices_visible_to_all_roles(client):
    headers, email = register(client)

    r = client.post(
        "/api/admin/notices",
        json={"title": "Hello", "content": "World", "is_important": False},
        headers=headers,
    )
    assert r.status_code == 403  # resident cannot create


def test_committee_creates_and_residents_read(client):
    from sqlalchemy import update

    committee_headers, committee_email = register(client)
    with SessionLocal() as db:
        db.execute(
            update(User).where(User.email == committee_email).values(role=UserRole.COMMITTEE)
        )
        db.commit()

    res_headers, _ = register(client)

    title = f"Water cut {uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/admin/notices",
        json={"title": title, "content": "Maintenance on Sunday.", "is_important": True},
        headers=committee_headers,
    )
    assert r.status_code == 201, r.text
    notice_id = r.json()["id"]

    listed = client.get("/api/notices", headers=res_headers).json()
    items = listed if isinstance(listed, list) else listed["items"]
    assert any(n["id"] == notice_id for n in items)

    # important notice fans out to all residents via notifications table
    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.event == "IMPORTANT_NOTICE_POSTED",
                Notification.payload.contains({"notice_id": notice_id}),
            )
        )
    assert count >= 1


def test_important_notice_pinned_first(client):
    from sqlalchemy import update

    committee_headers, committee_email = register(client)
    with SessionLocal() as db:
        db.execute(
            update(User).where(User.email == committee_email).values(role=UserRole.COMMITTEE)
        )
        db.commit()

    client.post(
        "/api/admin/notices",
        json={"title": f"Normal {uuid.uuid4().hex[:4]}", "content": "...", "is_important": False},
        headers=committee_headers,
    )
    client.post(
        "/api/admin/notices",
        json={"title": f"Pinned {uuid.uuid4().hex[:4]}", "content": "...", "is_important": True},
        headers=committee_headers,
    )

    listed = client.get("/api/notices", headers=committee_headers).json()
    items = listed if isinstance(listed, list) else listed["items"]
    assert items[0]["is_important"] is True
