from fastapi import FastAPI

from app.core.database import Base, engine
from app.models import (
    Complaint,
    ComplaintStatusHistory,
    Notice,
    User,
)
from app.routers.auth import router as auth_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Society Maintenance Tracker API",
    description="Apartment society complaint and notice management system",
    version="1.0.0",
)


app.include_router(auth_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "society-maintenance-api",
    }