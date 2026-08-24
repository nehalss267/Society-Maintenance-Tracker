import uuid

from tests.conftest import register

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_complaint(client, headers, description="Leaking pipe in bathroom area"):
    r = client.post(
        "/api/complaints",
        headers=headers,
        data={"category": "PLUMBING", "description": description},
    )
    assert r.status_code == 201
    return r.json()


def _accountant(client):
    from sqlalchemy import update

    from app.core.database import SessionLocal
    from app.models.user import User, UserRole

    headers, email = register(client)
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == email).values(role=UserRole.ACCOUNTANT))
        db.commit()
    return headers


def test_complaint_owner_can_upload_and_read_document(client):
    owner_headers, _ = register(client)
    complaint = _create_complaint(client, owner_headers)

    r = client.post(
        f"/api/documents/COMPLAINT/{complaint['id']}",
        files={"file": ("proof.png", PNG_BYTES, "image/png")},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()[0]["id"] if isinstance(r.json(), list) else r.json()["id"]

    listed = client.get(
        f"/api/documents/COMPLAINT/{complaint['id']}", headers=owner_headers
    )
    assert listed.status_code == 200

    dl = client.get(f"/api/documents/download/{doc_id}", headers=owner_headers)
    assert dl.status_code == 200


def test_other_resident_cannot_read_or_upload_to_foreign_complaint(client):
    a_headers, _ = register(client)
    b_headers, _ = register(client)

    complaint = _create_complaint(client, a_headers)

    up = client.post(
        f"/api/documents/COMPLAINT/{complaint['id']}",
        files={"file": ("sneak.png", PNG_BYTES, "image/png")},
        headers=b_headers,
    )
    assert up.status_code == 404  # no existence leak

    # even list is denied
    lst = client.get(f"/api/documents/COMPLAINT/{complaint['id']}", headers=b_headers)
    assert lst.status_code == 404


def test_committee_can_read_but_resident_cannot_upload_invoice_docs(client):
    acc = _accountant(client)
    res_headers, res_email = register(client)

    from sqlalchemy import select, update

    from app.core.database import SessionLocal
    from app.models.invoice import Invoice
    from app.models.maintenance_plan import MaintenancePlan
    from app.models.user import User, UserRole

    committee_headers, committee_email = register(client)
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == committee_email).values(role=UserRole.COMMITTEE))
        plan_id = db.scalar(select(MaintenancePlan.id).limit(1))
        if not plan_id:
            plan = MaintenancePlan(
                name=f"P{uuid.uuid4().hex[:6]}",
                amount=1000,
                cycle="MONTHLY",
                due_day_of_month=5,
                late_fee_amount=50,
                late_fee_grace_days=0,
            )
            db.add(plan)
            db.flush()
            plan_id = plan.id
        resident_id = db.scalar(select(User.id).where(User.email == res_email))
        inv = Invoice(
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            resident_id=resident_id,
            plan_id=plan_id,
            billing_period="2093-01",
            subtotal=1000,
            late_fee=0,
            total_amount=1000,
            amount_paid=0,
            due_date=__import__("datetime").date(2093, 1, 5),
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        invoice_id = inv.id

    # resident cannot upload to invoices (staff only)
    up = client.post(
        f"/api/documents/INVOICE/{invoice_id}",
        files={"file": ("r.png", PNG_BYTES, "image/png")},
        headers=res_headers,
    )
    assert up.status_code == 404

    # accountant CAN upload
    up2 = client.post(
        f"/api/documents/INVOICE/{invoice_id}",
        files={"file": ("receipt.png", PNG_BYTES, "image/png")},
        headers=acc,
    )
    assert up2.status_code == 201, up2.text
    doc_id = up2.json()[0]["id"] if isinstance(up2.json(), list) else up2.json()["id"]

    # committee can read invoice documents
    read = client.get(f"/api/documents/INVOICE/{invoice_id}", headers=committee_headers)
    assert read.status_code == 200

    # unrelated third resident cannot
    other_headers, _ = register(client)
    denied = client.get(
        f"/api/documents/INVOICE/{invoice_id}", headers=other_headers
    )
    assert denied.status_code == 404

    # download of nonexistent document -> 404 not 500
    missing = client.get(
        f"/api/documents/download/{uuid.uuid4()}", headers=acc
    )
    assert missing.status_code == 404
