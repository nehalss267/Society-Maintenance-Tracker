import hashlib
import hmac
import json
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.invoice import Invoice
from tests.conftest import register


def _accountant(client):
    headers, email = register(client)

    from sqlalchemy import update

    from app.models.user import User, UserRole

    with SessionLocal() as db:
        db.execute(update(User).where(User.email == email).values(role=UserRole.ACCOUNTANT))
        db.commit()

    return headers, email


def _plan(client, headers, amount=1500):
    r = client.post(
        "/api/admin/plans",
        json={
            "name": f"Plan {uuid.uuid4().hex[:6]}",
            "amount": amount,
            "cycle": "MONTHLY",
            "due_day_of_month": 10,
            "late_fee_amount": 100,
            "late_fee_grace_days": 0,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_billing_run_idempotent(client):
    acc, _ = _accountant(client)
    register(client)  # billing run invoices RESIDENT users only
    register(client)
    _plan(client, acc)

    period = f"2098-{(hash(uuid.uuid4().hex) % 12) + 1:02d}"

    r1 = client.post(f"/api/admin/billing/run/{period}", headers=acc)
    assert r1.status_code == 200, r1.text
    created_first = r1.json()["invoices_created"]
    # every RESIDENT in the test DB gets one invoice
    assert created_first >= 2

    # re-run: no duplicates
    r2 = client.post(f"/api/admin/billing/run/{period}", headers=acc)
    assert r2.status_code == 200
    assert r2.json()["invoices_created"] == 0

    r3 = client.get("/api/admin/invoices", params={"period": period}, headers=acc)
    total = r3.json()["total"]
    assert total == created_first


def test_late_fee_applied_once_and_marks_overdue(client, db_session):
    acc, _ = _accountant(client)
    register(client)
    _plan(client, acc, amount=1000)

    period = f"2097-{(hash(uuid.uuid4().hex) % 12) + 1:02d}"
    client.post(f"/api/admin/billing/run/{period}", headers=acc)

    # backdate due date so it is past grace
    from datetime import date, timedelta

    from sqlalchemy import update

    with SessionLocal() as db:
        db.execute(
            update(Invoice)
            .where(Invoice.billing_period == period)
            .values(due_date=(date.today() - timedelta(days=10)))
        )
        db.commit()

    first = client.post("/api/admin/billing/late-fees", headers=acc).json()
    second = client.post("/api/admin/billing/late-fees", headers=acc).json()

    assert first["invoices_penalized"] >= 1
    assert second["invoices_penalized"] == 0

    invs = client.get(
        "/api/admin/invoices", params={"period": period}, headers=acc
    ).json()
    target = next(i for i in invs["items"] if i["status"] == "OVERDUE")
    assert float(target["late_fee"]) == 100.0
    assert float(target["total_amount"]) == 1100.0


def test_payment_capture_settles_invoice_and_is_idempotent(client):
    res_headers, _ = register(client)
    acc, _ = _accountant(client)
    _plan(client, acc)

    period = f"2096-{(hash(uuid.uuid4().hex) % 12) + 1:02d}"
    client.post(f"/api/admin/billing/run/{period}", headers=acc)

    invoice = next(
        i for i in client.get("/api/invoices", headers=res_headers).json()
        if i["billing_period"] == period and i["status"] == "PENDING"
    )

    init = client.post(
        "/api/payments/initiate",
        headers=res_headers,
        json={"invoice_id": invoice["id"]},
    )
    assert init.status_code == 200, init.text
    payment_id = init.json()["payment_id"]

    cap = client.post(
        "/api/payments/simulate-success",
        headers=res_headers,
        json={"payment_id": payment_id},
    )
    assert cap.status_code == 200 and cap.json()["status"] == "SUCCESS"

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=res_headers).json()
    assert detail["status"] == "PAID"
    assert float(detail["amount_paid"]) == float(detail["total_amount"])

    # replay does not double credit
    client.post(
        "/api/payments/simulate-success",
        headers=res_headers,
        json={"payment_id": payment_id},
    )
    detail2 = client.get(f"/api/invoices/{invoice['id']}", headers=res_headers).json()
    assert float(detail2["amount_paid"]) == float(detail2["total_amount"])


def test_foreign_invoice_payment_blocked(client):
    a_headers, _ = register(client)
    b_headers, _ = register(client)

    acc, _ = _accountant(client)
    _plan(client, acc)

    period = f"2095-{(hash(uuid.uuid4().hex) % 12) + 1:02d}"
    client.post(f"/api/admin/billing/run/{period}", headers=acc)

    b_invs = [i for i in client.get("/api/invoices", headers=b_headers).json()
              if i["billing_period"] == period]

    r = client.post(
        "/api/payments/initiate", headers=a_headers, json={"invoice_id": b_invs[0]["id"]}
    )
    assert r.status_code in (403, 404, 409)


def test_webhook_signature_enforced(client):
    body = json.dumps({"event": "payment.captured"}).encode()
    bad = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "invalid"},
    )
    assert bad.status_code == 400

    good_sig = hmac.new(b"whsec_test", body, hashlib.sha256).hexdigest()
    ok = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": good_sig},
    )
    assert ok.status_code == 200
