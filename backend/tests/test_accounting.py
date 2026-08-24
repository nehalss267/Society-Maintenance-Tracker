from datetime import date

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.fund import FundTransaction, FundTransactionType
from tests.conftest import register


def _accountant(client):
    from sqlalchemy import update

    from app.models.user import User, UserRole

    headers, email = register(client)
    with SessionLocal() as db:
        db.execute(update(User).where(User.email == email).values(role=UserRole.ACCOUNTANT))
        db.commit()

    return headers


def _fund_balance(db):
    fund_id = db.scalar(
        select(FundTransaction.fund_id).order_by(FundTransaction.created_at.desc()).limit(1)
    )
    if fund_id is None:
        return None, None
    credited = db.scalar(
        select(func.coalesce(func.sum(FundTransaction.amount), 0)).where(
            FundTransaction.fund_id == fund_id,
            FundTransaction.type == FundTransactionType.CREDIT,
        )
    )
    debited = db.scalar(
        select(func.coalesce(func.sum(FundTransaction.amount), 0)).where(
            FundTransaction.fund_id == fund_id,
            FundTransaction.type == FundTransactionType.DEBIT,
        )
    )
    return float(credited - debited), fund_id


def test_resident_blocked_from_accounting(client):
    headers, _ = register(client)

    r = client.get("/api/admin/expenses", headers=headers)
    assert r.status_code == 403


def test_expense_debits_fund_and_rolls_back_on_insufficient(client):
    acc = _accountant(client)

    # seed the fund so we have a known positive balance
    r = client.post(
        "/api/admin/funds/transactions",
        json={"type": "CREDIT", "amount": "1000.00", "description": "seed"},
        headers=acc,
    )
    assert r.status_code in (200, 201), r.text

    before, _ = _fund_balance(SessionLocal())

    # overdrawing is rejected atomically
    r = client.post(
        "/api/admin/funds/transactions",
        json={"type": "DEBIT", "amount": str(before + 10000), "description": "force negative"},
        headers=acc,
    )
    assert r.status_code == 409  # insufficient funds rejected atomically

    # successful expense reduces balance exactly
    r = client.post(
        "/api/admin/expenses",
        json={
            "title": "Guard salary",
            "category": "SECURITY",
            "amount": "500.00",
            "expense_date": str(date.today()),
        },
        headers=acc,
    )
    assert r.status_code in (200, 201), r.text
    expense_id = r.json()["id"]

    after, _ = _fund_balance(SessionLocal())
    assert abs((before or 0) - after - 500.0) < 0.01

    # delete not supported? then update to smaller amount adjusts delta +200
    r = client.patch(
        f"/api/admin/expenses/{expense_id}",
        json={"amount": "300.00"},
        headers=acc,
    )
    assert r.status_code == 200

    final, _ = _fund_balance(SessionLocal())
    assert abs(final - after - 200.0) < 0.01


def test_recurring_generation_is_idempotent(client):
    acc = _accountant(client)

    r = client.post(
        "/api/admin/recurring-expenses",
        json={
            "title": "Lift AMC",
            "category": "REPAIRS",
            "amount": "1200.00",
            "frequency": "MONTHLY",
            "day_of_month": 15,
        },
        headers=acc,
    )
    assert r.status_code == 201, r.text

    # recurring generation books a real expense -> fund needs balance
    seed = client.post(
        "/api/admin/funds/transactions",
        json={"type": "CREDIT", "amount": "5000.00", "description": "seed"},
        headers=acc,
    )
    assert seed.status_code in (200, 201), seed.text

    period = r.json()["next_run_date"][:7]

    first = client.post(
        f"/api/admin/expenses/generate-recurring/{period}", headers=acc
    ).json()
    second = client.post(
        f"/api/admin/expenses/generate-recurring/{period}", headers=acc
    ).json()

    assert first["generated"] >= 1
    assert second["generated"] == 0

    listed = client.get("/api/admin/expenses", headers=acc)
    assert listed.status_code == 200


def test_manual_credit_increases_fund(client):
    acc = _accountant(client)

    before, _ = _fund_balance(SessionLocal())

    r = client.post(
        "/api/admin/funds/transactions",
        json={"type": "CREDIT", "amount": "250.50", "description": "donation"},
        headers=acc,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["balance_after"] >= body["amount"]

    after, _ = _fund_balance(SessionLocal())
    assert abs(after - (before or 0) - 250.5) < 0.01
