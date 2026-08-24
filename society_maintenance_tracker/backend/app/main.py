from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.services.storage_service import UPLOAD_ROOT
from app.models import (  # noqa: F401  (registers all models with Base.metadata)
    AuditLog,
    Complaint,
    ComplaintSla,
    ComplaintStatusHistory,
    Notice,
    User,
)
from app.routers.auth import router as auth_router
from app.routers.billing import admin_router as billing_admin_router
from app.routers.billing import router as invoices_router
from app.routers.complaints import admin_router as complaints_admin_router
from app.routers.complaints import router as complaints_router
from app.routers.notices import admin_router as notices_admin_router
from app.routers.notices import router as notices_router
from app.routers.accounting import router as accounting_router
from app.routers.dashboards import report_router as reports_router
from app.routers.dashboards import router as dashboards_router
from app.routers.documents import router as documents_router
from app.routers.internal_jobs import router as internal_jobs_router
from app.routers.payments import (
    admin_router as payments_admin_router,
)
from app.routers.payments import router as payments_router
from app.routers.payments import webhook_router
from app.routers.users import router as users_router


app = FastAPI(
    title="Society Maintenance Tracker API",
    description="Apartment society complaint and notice management system",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Cron-Secret"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(complaints_router)
app.include_router(complaints_admin_router)
app.include_router(notices_router)
app.include_router(notices_admin_router)
app.include_router(invoices_router)
app.include_router(billing_admin_router)
app.include_router(payments_router)
app.include_router(payments_admin_router)
app.include_router(webhook_router)
app.include_router(accounting_router)
app.include_router(internal_jobs_router)
app.include_router(documents_router)
app.include_router(dashboards_router)
app.include_router(reports_router)

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_ROOT)),
    name="uploads",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "society-maintenance-api",
    }
