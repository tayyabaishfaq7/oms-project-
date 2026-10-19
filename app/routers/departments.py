"""Departments. Create/update/delete = HR only. Read = any logged-in user. Scoped to the user's organization."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser, HRUser
from app.models import Department, Designation, Employee, Position
from app.schemas import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["Departments"])


def _get_or_404(db, dep_id: int, org_id: int) -> Department:
    dep = db.get(Department, dep_id)
    if not dep or dep.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Department not found")
    return dep


def _name_taken(db, org_id: int, name: str, exclude_id: int | None = None) -> bool:
    found = db.scalar(select(Department).where(Department.organization_id == org_id, Department.name == name))
    return bool(found and found.id != exclude_id)


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(data: DepartmentCreate, db: DB, hr: HRUser):
    if _name_taken(db, hr.organization_id, data.name):
        raise HTTPException(status_code=400, detail="Department name already exists")
    dep = Department(organization_id=hr.organization_id, **data.model_dump())
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: DB, user: CurrentUser):
    return db.scalars(
        select(Department).where(Department.organization_id == user.organization_id).order_by(Department.id)
    ).all()


@router.get("/{dep_id}", response_model=DepartmentOut)
def get_department(dep_id: int, db: DB, user: CurrentUser):
    return _get_or_404(db, dep_id, user.organization_id)


@router.put("/{dep_id}", response_model=DepartmentOut)
def update_department(dep_id: int, data: DepartmentUpdate, db: DB, hr: HRUser):
    dep = _get_or_404(db, dep_id, hr.organization_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and _name_taken(db, hr.organization_id, changes["name"], dep.id):
        raise HTTPException(status_code=400, detail="Department name already exists")
    for field, value in changes.items():
        setattr(dep, field, value)
    db.commit()
    db.refresh(dep)
    return dep


@router.delete("/{dep_id}", status_code=204)
def delete_department(dep_id: int, db: DB, hr: HRUser):
    dep = _get_or_404(db, dep_id, hr.organization_id)
    for model, label in ((Employee, "employees"), (Position, "positions"), (Designation, "designations")):
        if db.scalar(select(model.id).where(model.department_id == dep.id)):
            raise HTTPException(status_code=409, detail=f"This department still has {label}; remove or move them first")
    db.delete(dep)
    db.commit()
