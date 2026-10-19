"""Organizations. POST is public (sign up a new company + its first HR admin). /me endpoints are for logged-in users."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.core.security import hash_password
from app.dependencies import CurrentUser, HRUser
from app.models import Organization, User
from app.schemas import OrganizationCreate, OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(data: OrganizationCreate, db: DB):
    if db.scalar(select(Organization).where(Organization.name == data.name)):
        raise HTTPException(status_code=400, detail="Organization name already exists")
    if db.scalar(select(User).where(User.username == data.admin_username)):
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.scalar(select(User).where(User.email == data.admin_email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    org = Organization(name=data.name)
    db.add(org)
    db.flush()
    db.add(User(
        organization_id=org.id,
        username=data.admin_username,
        email=data.admin_email,
        hashed_password=hash_password(data.admin_password),
        role="hr",
    ))
    db.commit()
    db.refresh(org)
    return org


@router.get("/me", response_model=OrganizationOut)
def my_organization(db: DB, user: CurrentUser):
    return db.get(Organization, user.organization_id)


@router.put("/me", response_model=OrganizationOut)
def update_my_organization(data: OrganizationUpdate, db: DB, hr: HRUser):
    org = db.get(Organization, hr.organization_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        taken = db.scalar(select(Organization).where(Organization.name == changes["name"]))
        if taken and taken.id != org.id:
            raise HTTPException(status_code=400, detail="Organization name already exists")
    for field, value in changes.items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org
