"""
Positions = the boxes of the organization chart.

Two kinds:
  * ORG-WIDE   (department_id is empty)  -> Chairman, CEO, General Manager
  * DEPARTMENT (department_id is set)    -> IT Manager, Software Engineer, Graphic Designer ...

Each position can "report to" another position (reports_to_id). Rules enforced here:
  - a position cannot report to itself or to one of its own subordinates (no loops)
  - a department position may report to an org-wide position OR to a position of the SAME department
  - an org-wide position can only report to another org-wide position
  - title is unique inside its department (or among the org-wide ones)
Create/update/delete = HR only. Read = any logged-in user. Always scoped to the user's organization.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser, HRUser
from app.models import Department, Employee, Position
from app.schemas import PositionCreate, PositionOut, PositionUpdate

router = APIRouter(prefix="/positions", tags=["Positions"])


def _get_or_404(db, pos_id: int, org_id: int) -> Position:
    pos = db.get(Position, pos_id)
    if not pos or pos.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Position not found")
    return pos


def _ensure_department(db, department_id: Optional[int], org_id: int):
    if department_id is None:
        return
    dep = db.get(Department, department_id)
    if not dep or dep.organization_id != org_id:
        raise HTTPException(status_code=400, detail="department_id does not exist")


def _ensure_title_free(db, org_id: int, department_id: Optional[int], title: str, exclude_id: Optional[int] = None):
    query = select(Position).where(Position.organization_id == org_id, Position.title == title)
    query = query.where(Position.department_id == department_id) if department_id is not None \
        else query.where(Position.department_id.is_(None))
    found = db.scalar(query)
    if found and found.id != exclude_id:
        where = "this department" if department_id is not None else "the org-wide positions"
        raise HTTPException(status_code=400, detail=f"{where.capitalize()} already has a position called '{title}'")


def _check_parent(db, org_id: int, parent_id: Optional[int], department_id: Optional[int],
                  self_id: Optional[int]) -> Optional[Position]:
    """Validate the 'reports to' link and return the parent position (or None)."""
    if parent_id is None:
        return None
    parent = db.get(Position, parent_id)
    if not parent or parent.organization_id != org_id:
        raise HTTPException(status_code=400, detail="reports_to_id does not exist")
    if self_id is not None:
        node = parent                      # walk upward; if we meet ourselves, it is a loop
        while node is not None:
            if node.id == self_id:
                raise HTTPException(status_code=400, detail="A position cannot report to itself or to its own subordinate")
            node = db.get(Position, node.reports_to_id) if node.reports_to_id else None
    if department_id is None and parent.department_id is not None:
        raise HTTPException(status_code=400, detail="An org-wide position can only report to another org-wide position")
    if department_id is not None and parent.department_id not in (None, department_id):
        raise HTTPException(status_code=400, detail="A position can only report to an org-wide position or one in its own department")
    return parent


@router.post("", response_model=PositionOut, status_code=201)
def create_position(data: PositionCreate, db: DB, hr: HRUser):
    org_id = hr.organization_id
    _ensure_department(db, data.department_id, org_id)
    _ensure_title_free(db, org_id, data.department_id, data.title)
    parent = _check_parent(db, org_id, data.reports_to_id, data.department_id, None)
    values = data.model_dump()
    if values["rank"] is None:
        values["rank"] = parent.rank + 1 if parent else 1
    pos = Position(organization_id=org_id, **values)
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos


@router.get("", response_model=list[PositionOut])
def list_positions(db: DB, user: CurrentUser, department_id: Optional[int] = None, org_wide: Optional[bool] = None):
    """?department_id=N -> positions of that department.  ?org_wide=true -> only Chairman/CEO/GM style positions."""
    query = select(Position).where(Position.organization_id == user.organization_id).order_by(Position.rank, Position.id)
    if department_id is not None:
        query = query.where(Position.department_id == department_id)
    if org_wide is True:
        query = query.where(Position.department_id.is_(None))
    elif org_wide is False:
        query = query.where(Position.department_id.is_not(None))
    return db.scalars(query).all()


@router.get("/{pos_id}", response_model=PositionOut)
def get_position(pos_id: int, db: DB, user: CurrentUser):
    return _get_or_404(db, pos_id, user.organization_id)


@router.put("/{pos_id}", response_model=PositionOut)
def update_position(pos_id: int, data: PositionUpdate, db: DB, hr: HRUser):
    org_id = hr.organization_id
    pos = _get_or_404(db, pos_id, org_id)
    changes = data.model_dump(exclude_unset=True)
    new_dept = changes.get("department_id", pos.department_id)
    new_parent_id = changes.get("reports_to_id", pos.reports_to_id)

    if "department_id" in changes:
        _ensure_department(db, new_dept, org_id)
        if new_dept != pos.department_id and db.scalar(select(Employee.id).where(Employee.position_id == pos.id)):
            raise HTTPException(status_code=400, detail="Employees hold this position; move them before changing its department")
    _ensure_title_free(db, org_id, new_dept, changes.get("title", pos.title), exclude_id=pos.id)
    parent = _check_parent(db, org_id, new_parent_id, new_dept, pos.id)
    if "rank" not in changes and "reports_to_id" in changes:
        changes["rank"] = parent.rank + 1 if parent else 1
    # Children that sit in another department would become invalid if this position moved departments.
    if "department_id" in changes and new_dept is not None:
        bad_child = db.scalar(select(Position.id).where(
            Position.reports_to_id == pos.id, Position.department_id.is_not(None), Position.department_id != new_dept))
        if bad_child:
            raise HTTPException(status_code=400, detail="Positions of another department report to this one")
    for field, value in changes.items():
        setattr(pos, field, value)
    db.commit()
    db.refresh(pos)
    return pos


@router.delete("/{pos_id}", status_code=204)
def delete_position(pos_id: int, db: DB, hr: HRUser):
    pos = _get_or_404(db, pos_id, hr.organization_id)
    if db.scalar(select(Employee.id).where(Employee.position_id == pos.id)):
        raise HTTPException(status_code=409, detail="Employees still hold this position")
    if db.scalar(select(Position.id).where(Position.reports_to_id == pos.id)):
        raise HTTPException(status_code=409, detail="Other positions report to this one; re-assign them first")
    db.delete(pos)
    db.commit()
