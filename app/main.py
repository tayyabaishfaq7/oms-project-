"""Entry point. Run with:  uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models
from app.core.config import HR_EMAIL, HR_ORG_NAME, HR_PASSWORD, HR_USERNAME, SEED_DEMO_DATA, SEED_RESET
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.seed import seed_demo_data
from app.routers import (
    attendance, auth, departments, designations, employees,
    leaves, org_chart, organizations, positions, shifts, users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: create tables, then the first organization + its HR account."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.scalar(select(models.User).where(models.User.username == HR_USERNAME)):
            org = db.scalar(select(models.Organization).where(models.Organization.name == HR_ORG_NAME))
            if not org:
                org = models.Organization(name=HR_ORG_NAME)
                db.add(org)
                db.flush()  # gives org.id without committing yet
            db.add(models.User(
                organization_id=org.id,
                username=HR_USERNAME,
                email=HR_EMAIL,
                hashed_password=hash_password(HR_PASSWORD),
                role="hr",
            ))
            db.commit()
        if SEED_DEMO_DATA:
            seed_demo_data(db, reset=SEED_RESET)   # fake employees/attendance/etc. (skipped if employees already exist)
    yield


app = FastAPI(title="Organization Management System", version="2.0", lifespan=lifespan)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """A database rule was broken (duplicate value, or deleting a row that other rows still use).
    Return a clean 409 instead of a 500 crash."""
    return JSONResponse(status_code=409, content={
        "detail": "This change conflicts with existing data (a duplicate value, or other records still depend on this one)."})

app.include_router(organizations.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(positions.router)
app.include_router(org_chart.router)
app.include_router(designations.router)
app.include_router(shifts.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(leaves.router)


@app.get("/health", tags=["Root"])
def health():
    return {"status": "ok"}


@app.get("/", tags=["Root"])
def root():
    return {"message": "Employee Management System API is running. Open /docs"}
