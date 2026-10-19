"""
Leave requests. Employee: applies, sees own. HR: sees all in their organization, approves/rejects.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentEmployee, CurrentUser, HRUser
from app.models import Employee, LeaveRequest
from app.schemas import LeaveCreate, LeaveOut

router = APIRouter(prefix="/leaves", tags=["Leave Requests"])


def _get_or_404(db, leave_id: int, org_id: int) -> LeaveRequest:
    leave = db.get(LeaveRequest, leave_id)
    if not leave or leave.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave


@router.post("", response_model=LeaveOut, status_code=201)
def apply_leave(data: LeaveCreate, db: DB, employee: CurrentEmployee):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    overlap = db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.employee_id == employee.id, LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= data.end_date, LeaveRequest.end_date >= data.start_date))
    if overlap:
        raise HTTPException(status_code=400, detail="You already have a pending/approved leave in these dates")
    leave = LeaveRequest(
        organization_id=employee.organization_id, employee_id=employee.id,
        status="pending", **data.model_dump(),
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.get("", response_model=list[LeaveOut])
def list_leaves(db: DB, user: CurrentUser):
    query = (
        select(LeaveRequest)
        .where(LeaveRequest.organization_id == user.organization_id)
        .order_by(LeaveRequest.id.desc())
    )
    if user.role != "hr":
        own = db.scalar(select(Employee).where(Employee.user_id == user.id))
        if not own:
            return []
        query = query.where(LeaveRequest.employee_id == own.id)
    return db.scalars(query).all()


@router.put("/{leave_id}/approve", response_model=LeaveOut)
def approve_leave(leave_id: int, db: DB, hr: HRUser):
    leave = _get_or_404(db, leave_id, hr.organization_id)
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail=f"Leave is already {leave.status}")
    leave.status = "approved"
    leave.approved_by = hr.id
    db.commit()
    db.refresh(leave)
    return leave


@router.put("/{leave_id}/reject", response_model=LeaveOut)
def reject_leave(leave_id: int, db: DB, hr: HRUser):
    leave = _get_or_404(db, leave_id, hr.organization_id)
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail=f"Leave is already {leave.status}")
    leave.status = "rejected"
    leave.approved_by = hr.id
    db.commit()
    db.refresh(leave)
    return leave
