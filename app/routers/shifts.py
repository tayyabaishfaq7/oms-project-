"""Shifts. Create/update/delete = HR only. Read = any logged-in user. Org-scoped."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser, HRUser
from app.models import Shift
from app.schemas import ShiftCreate, ShiftOut, ShiftUpdate

router = APIRouter(prefix="/shifts", tags=["Shifts"])


def _get_or_404(db, shift_id: int, org_id: int) -> Shift:
    shift = db.get(Shift, shift_id)
    if not shift or shift.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


@router.post("", response_model=ShiftOut, status_code=201)
def create_shift(data: ShiftCreate, db: DB, hr: HRUser):
    shift = Shift(organization_id=hr.organization_id, **data.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.get("", response_model=list[ShiftOut])
def list_shifts(db: DB, user: CurrentUser):
    return db.scalars(
        select(Shift).where(Shift.organization_id == user.organization_id).order_by(Shift.id)
    ).all()


@router.get("/{shift_id}", response_model=ShiftOut)
def get_shift(shift_id: int, db: DB, user: CurrentUser):
    return _get_or_404(db, shift_id, user.organization_id)


@router.put("/{shift_id}", response_model=ShiftOut)
def update_shift(shift_id: int, data: ShiftUpdate, db: DB, hr: HRUser):
    shift = _get_or_404(db, shift_id, hr.organization_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shift, field, value)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: int, db: DB, hr: HRUser):
    shift = _get_or_404(db, shift_id, hr.organization_id)
    db.delete(shift)
    db.commit()
