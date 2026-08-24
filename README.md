# Society Maintenance Tracker

Production-grade apartment/society management platform: residents raise and track
maintenance complaints (with photos), committee/admin manage them through a strict
lifecycle with SLA-based overdue detection, and everyone stays informed via a notice
board and email updates. Includes billing, UPI payments, expense/fund accounting,
background jobs, and full audit logging.

## Live App

| Service | URL |
|---|---|
| Frontend (React SPA) | https://smt-frontend-u3e6.onrender.com |
| API (FastAPI) | https://smt-api-w11c.onrender.com |
| Swagger/OpenAPI docs | https://smt-api-w11c.onrender.com/docs |
| Health check | https://smt-api-w11c.onrender.com/health |

> Free tier note: services spin down after ~15 min idle; first request may take ~50 s to wake up.

## Features

- **Complaints** - residents file category-tagged tickets with photos; committee drives
  an enforced status lifecycle (RESOLVED is terminal) with SLA due-dates, overdue
  flags, priority changes, and full status history. Residents see only their own.
- **Notices** - committee-published board; important notices pin first and fan out to
  every resident via email/notification queue.
- **Billing** - maintenance plans (monthly cycles), idempotent billing runs per period,
  late fees applied exactly once past grace, admin invoice browser with filters.
- **Payments** - Razorpay orders with HMAC-verified capture/webhooks (simulated flow
  when keys are blank), idempotent settlement, auto-reconciliation ledger.
- **Accounting** - expense tracking with receipts, recurring expense definitions,
  double-entry-style fund ledger (`balance_after` snapshots), manual credits/debits
  with atomic insufficient-funds protection.
- **Documents** - entity-scoped attachments (complaints/invoices/expenses) with
  role-aware read/upload authorization.
- **Notifications** - queued email delivery (Resend; log-only fallback) for payment
  receipts, complaint updates, invoices, and notices.
- **Dashboards & reports** - role-specific stats plus expense-by-category and
  collections-by-period reports, cached in Redis with targeted invalidation.
- **Security** - JWT auth, 4-role RBAC, audit log on every mutation, security headers,
  CORS allow-list, upload magic-byte validation and path-traversal containment.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | FastAPI (Python 3.11) |
| ORM / DB | SQLAlchemy 2.x · PostgreSQL 16 |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Cache/Jobs | Redis + Celery (dev); inline mode for free-tier prod |
| Payments | Razorpay (env-gated, simulated fallback) |
| Files | Local disk (dev) / Cloudinary (prod) |
| Email | Resend (env-gated fallback) |

## Repository Layout

```
Society-Maintenance-Tracker/
├── backend/            FastAPI app (app/core|models|schemas|routers|services|workers)
│   ├── alembic/        DB migrations
│   ├── scripts/        seed.py demo data
│   └── tests/          pytest suite (31 tests)
├── frontend/           React SPA (pages, role-based layout, auth context)
├── database/           Reference SQL schema (schema.sql)
├── docs/               architecture.md · deployment.md · roadmap.md · ...
├── system-design.md    System design document
├── docker-compose.yml  Postgres (:5433) + Redis (:6379) for local dev
└── render.yaml         Render blueprint: API web service + static frontend
```

## Quick Start (Local Development)

### Prerequisites
- Docker Desktop (for PostgreSQL + Redis)
- Python 3.11+
- Node 20+ (frontend phase)

### 1. Infrastructure

```bash
docker compose up -d          # postgres on host :5433 (5432 taken on Windows), redis :6379
```

### 2. Backend

```bash
cd backend
python -m venv .venv                        # first time only
.venv/Scripts/pip install -r requirements.txt   # Windows bash; use .venv/bin on Linux
cp .env.example .env                        # then edit values if needed
.venv/Scripts/alembic upgrade head          # create schema
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger/OpenAPI docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 3. Seed demo data (optional)

```bash
cd backend
.venv/Scripts/python scripts/seed.py
```

| Account | Password | Role |
|---|---|---|
| admin@smt.dev | Admin@123 | ADMIN |
| committee@smt.dev | Committee@123 | COMMITTEE |
| accountant@smt.dev | Account@123 | ACCOUNTANT |
| resident1@smt.dev | Resident@123 | RESIDENT |
| resident2@smt.dev | Resident@123 | RESIDENT |

### 4. Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173 (proxies /api to :8000)
```

## Running Tests

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -q
```

The suite (31 tests) spins up an isolated `society_test_db` on the same Postgres
instance and exercises auth, RBAC, complaints, notices, billing, payments,
accounting, documents, and the security hardening in-process - no live server needed.

## Environment Variables

See [`backend/.env.example`](backend/.env.example) - every integration is optional:
blank credentials automatically switch that feature to its safe fallback
(local file storage, logged emails, simulated payments).

## API Documentation

FastAPI auto-generates interactive OpenAPI docs at `/docs` when the backend runs.
The exported schema is available at `/openapi.json`.

## Database Schema

Canonical migrations live in `backend/alembic/versions/`.
A human-readable reference of the full target schema is in
[`database/schema.sql`](database/schema.sql).

## Deployment

Free-tier production stack (Render web service + Render static site + Neon Postgres +
cron-job.org for scheduled jobs), provisionable in one click via
[`render.yaml`](render.yaml). Step-by-step guide:
Architecture overview: [`system-design.md`](system-design.md).

## License

All rights reserved.
