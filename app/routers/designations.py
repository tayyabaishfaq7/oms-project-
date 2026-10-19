"""Designations (job titles + level). Create/update/delete = HR only. Read = any logged-in user. Org-scoped."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser, HRUser
from app.models import Department, Designation
from app.schemas import DesignationCreate, DesignationOut, DesignationUpdate

router = APIRouter(prefix="/designations", tags=["Designations"])


def _get_or_404(db, des_id: int, org_id: int) -> Designation:
    des = db.get(Designation, des_id)
    if not des or des.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Designation not found")
    return des


def _ensure_department_exists(db, department_id: int, org_id: int):
    dep = db.get(Department, department_id)
    if not dep or dep.organization_id != org_id:
        raise HTTPException(status_code=400, detail="department_id does not exist")


@router.post("", response_model=DesignationOut, status_code=201)
def create_designation(data: DesignationCreate, db: DB, hr: HRUser):
    _ensure_department_exists(db, data.department_id, hr.organization_id)
    des = Designation(organization_id=hr.organization_id, **data.model_dump())
    db.add(des)
    db.commit()
    db.refresh(des)
    return des


@router.get("", response_model=list[DesignationOut])
def list_designations(db: DB, user: CurrentUser):
    return db.scalars(
        select(Designation).where(Designation.organization_id == user.organization_id).order_by(Designation.id)
    ).all()


@router.get("/{des_id}", response_model=DesignationOut)
def get_designation(des_id: int, db: DB, user: CurrentUser):
    return _get_or_404(db, des_id, user.organization_id)


@router.put("/{des_id}", response_model=DesignationOut)
def update_designation(des_id: int, data: DesignationUpdate, db: DB, hr: HRUser):
    des = _get_or_404(db, des_id, hr.organization_id)
    changes = data.model_dump(exclude_unset=True)
    if "department_id" in changes:
        _ensure_department_exists(db, changes["department_id"], hr.organization_id)
    for field, value in changes.items():
        setattr(des, field, value)
    db.commit()
    db.refresh(des)
    return des


@router.delete("/{des_id}", status_code=204)
def delete_designation(des_id: int, db: DB, hr: HRUser):
    des = _get_or_404(db, des_id, hr.organization_id)
    db.delete(des)
    db.commit()
