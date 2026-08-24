# System Design — Society Maintenance Tracker

## 1. Purpose and stack

A production-grade apartment-society management platform covering residents, complaints,
notices, maintenance billing, payments, accounting, documents, notifications, dashboards,
and reports. Stack: React 18 + Vite + Tailwind SPA; FastAPI + SQLAlchemy 2.0 + Alembic;
PostgreSQL; Redis/Celery optional for async jobs. Every external integration degrades
gracefully when credentials are absent, so the system runs end-to-end at zero cost.

## 2. Topology

The browser SPA talks only to the FastAPI service (`/api/*`, plus `/uploads` in local
storage mode). The API owns all business logic and persistence. In development, Vite
proxies `/api` and `/uploads` to the backend. In production the frontend is a static
site configured with `VITE_API_URL`; CORS on the API allows exactly that origin.

Async work has two interchangeable modes selected by `JOB_EXECUTION_MODE`:
`celery` (Redis broker) or `inline` (executed in-process). Production uses `inline`
plus three secret-guarded HTTP job endpoints driven by an external cron service.

Integrations are env-gated wrappers:

| Integration | Configured | Fallback |
|---|---|---|
| Razorpay | real orders + HMAC signature verification | simulated orders, `simulate-success` endpoint |
| Resend | HTTP email delivery | log-only provider |
| Cloudinary | cloud image/document storage | local `uploads/` directory |

## 3. Backend structure

Three layers with one-directional imports:

- **Routers** (`app/routers`) — HTTP parsing, auth guards, response schemas.
- **Services** (`app/services`) — business rules, transaction ownership.
- **Models** (`app/models`) — SQLAlchemy declarative base, exported centrally so Alembic
  autogenerate sees everything.

Two invariants hold everywhere: every mutation writes an `audit_logs` row inside the
same database transaction, and routers never commit — services own transactions.

## 4. Authentication and RBAC

JWT bearer tokens (HS256, 60-minute expiry). Passwords hashed with bcrypt; registration
enforces 8+ characters with letters and digits. Four roles — RESIDENT, COMMITTEE,
ACCOUNTANT, ADMIN — enforced by FastAPI dependencies (`require_committee`,
`require_accountant`, `require_admin`). Admins cannot change their own role. Role changes
are audited (`USER_ROLE_CHANGED`). Object ownership is checked per request; denials
return 404 rather than 403 where existence itself is sensitive (e.g., foreign complaints
and documents).

## 5. Core domain flows

**Billing run** (`generate_invoices_for_period`): for each active plan × each RESIDENT,
skip if an invoice already exists for `(plan, resident, period)` — making reruns and
cron/admin triggers idempotent. Invoice items record plan charges; emails fan out to
residents.

**Late fees**: unpaid invoices past `due_date + grace` get exactly one `LATE_FEE` item
(dedupe by item kind), flipping status PENDING → OVERDUE.

**Payments**: initiate creates a PENDING payment (own-invoice enforced); capture succeeds
via verified webhook HMAC, verified redirect signature, or simulation. Idempotency comes
from a unique `provider_payment_id` plus a `SELECT … FOR UPDATE` row lock on the invoice.
Capture updates `amount_paid`/status, auto-creates a MATCHED reconciliation (or
MANUAL_REVIEW for unmatched webhooks), credits the fund, emits a receipt email, and
invalidates dashboard caches — all in one transaction.

**Fund ledger**: `maintenance_funds` holds the authoritative balance; `fund_transactions`
append CREDIT/DEBIT rows from typed sources (payments, expenses, manual ops) with
`balance_after` snapshots. Debits that would go negative roll back atomically (409).

**Expenses**: manual entries debit the fund in-transaction; edits post delta
adjustments. Recurring definitions generate expenses when their `next_run_date` falls in
the requested period, deduped by `(source_recurring_id, generated_period)`.

**Complaints**: categories carry SLA target days; a `complaint_sla` row stores `due_at`
and powers overdue flags. Status transitions follow a validated map with RESOLVED
terminal (409 on reopening); every change appends history and notifies the owner.
Committee can reprioritize (audited).

**Documents**: entity-scoped attachments with separate read/upload authorization rules;
missing files return 410, unauthorized access 404. Local paths are containment-checked
against the uploads root to block traversal.

## 6. Notifications and jobs

`notify()` never raises into business flows — delivery failures degrade to FAILED
notification rows. Dispatch respects the execution mode (Celery task with retries, or
inline isolated session). Cron endpoints (`/api/internal/jobs/*`) compare
`X-Cron-Secret` with `hmac.compare_digest` and run billing, late fees, and recurring
expenses.

## 7. Caching

Dashboard/report reads cache JSON under `dash:*` keys (60 s TTL) via a Redis helper that
silently no-ops when Redis is unavailable. Mutations that affect figures call targeted
prefix invalidations.

## 8. Security posture

CORS restricted to configured origins; security headers on all responses
(nosniff, frame-deny, no-referrer); webhook and cron secrets compared in constant time;
uploads magic-byte sniffed with size caps; SQL via bound parameters only; `.env`
gitignored.

## 9. Deployment

Render blueprint (`render.yaml`): Python web service runs `alembic upgrade head &&
uvicorn` behind `/health`; static site serves the built SPA with rewrite-to-index
routing. Database is Neon Postgres (`DATABASE_URL`). Cron-job.org hits the internal job
endpoints on schedule. Cloudinary provides persistent media on ephemeral free disks;
Resend delivers email. Total infrastructure cost: $0.
