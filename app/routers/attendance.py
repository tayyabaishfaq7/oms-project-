"""
Attendance.
  Employee: check-in / check-out (once per day), sees own history.
  HR: sees everyone in their organization, today's board, monthly summary, can correct/delete rows.

Rules:
  * "Today" is calculated in the organization's TIMEZONE (.env), not in UTC.
  * Times are STORED in UTC. If the employee has a shift and checks in later than
    shift start + LATE_GRACE_MINUTES, the row is saved with status "late".
  * work_hours = check_out - check_in (shown once the employee has checked out).
"""
from calendar import monthrange
from datetime import date as date_type, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.config import LATE_GRACE_MINUTES, TIMEZONE
from app.core.database import DB
from app.dependencies import CurrentEmployee, CurrentUser, HRUser
from app.models import Attendance, Department, Employee, Position, Shift
from app.schemas import AttendanceOut, AttendanceSummaryRow, AttendanceTodayRow, AttendanceUpdate

router = APIRouter(prefix="/attendance", tags=["Attendance"])

LOCAL_TZ = ZoneInfo(TIMEZONE)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)      # naive UTC, matches the DB column


def _local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def _is_late(db, employee: Employee, local_now: datetime) -> bool:
    if not employee.shift_id:
        return False
    shift = db.get(Shift, employee.shift_id)
    if not shift:
        return False
    deadline = datetime.combine(local_now.date(), shift.start_time, tzinfo=LOCAL_TZ) + timedelta(minutes=LATE_GRACE_MINUTES)
    return local_now > deadline


def _get_or_404(db, att_id: int, org_id: int) -> Attendance:
    att = db.get(Attendance, att_id)
    if not att or att.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return att


@router.post("/check-in", response_model=AttendanceOut, status_code=201)
def check_in(db: DB, employee: CurrentEmployee):
    now_local = _local_now()
    today = now_local.date()
    existing = db.scalar(
        select(Attendance).where(Attendance.employee_id == employee.id, Attendance.date == today)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already checked in today")
    att = Attendance(
        organization_id=employee.organization_id, employee_id=employee.id, date=today,
        check_in=_utc_now(), status="late" if _is_late(db, employee, now_local) else "present",
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@router.post("/check-out", response_model=AttendanceOut)
def check_out(db: DB, employee: CurrentEmployee):
    today = _local_now().date()
    att = db.scalar(
        select(Attendance).where(Attendance.employee_id == employee.id, Attendance.date == today)
    )
    if not att:
        raise HTTPException(status_code=400, detail="You have not checked in today")
    if att.check_out:
        raise HTTPException(status_code=400, detail="Already checked out today")
    att.check_out = _utc_now()
    db.commit()
    db.refresh(att)
    return att


@router.get("/today", response_model=list[AttendanceTodayRow])
def today_board(db: DB, hr: HRUser):
    """HR dashboard: every active employee and whether they have checked in today."""
    today = _local_now().date()
    org_id = hr.organization_id
    rows = {a.employee_id: a for a in db.scalars(
        select(Attendance).where(Attendance.organization_id == org_id, Attendance.date == today))}
    depts = {d.id: d.name for d in db.scalars(select(Department).where(Department.organization_id == org_id))}
    titles = {p.id: p.title for p in db.scalars(select(Position).where(Position.organization_id == org_id))}
    out = []
    for e in db.scalars(select(Employee).where(Employee.organization_id == org_id, Employee.status == "active")
                        .order_by(Employee.full_name)):
        a = rows.get(e.id)
        out.append(AttendanceTodayRow(
            employee_id=e.id, full_name=e.full_name, department=depts.get(e.department_id),
            position=titles.get(e.position_id, "-"), status=a.status if a else "not_checked_in",
            check_in=a.check_in if a else None, check_out=a.check_out if a else None,
        ))
    return out


@router.get("/summary", response_model=list[AttendanceSummaryRow])
def monthly_summary(db: DB, hr: HRUser, month: Optional[int] = None, year: Optional[int] = None,
                    department_id: Optional[int] = None):
    """HR: per-employee totals for one month (defaults to the current month)."""
    now = _local_now()
    month, year = month or now.month, year or now.year
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="month must be 1-12")
    start, end = date_type(year, month, 1), date_type(year, month, monthrange(year, month)[1])
    org_id = hr.organization_id

    emp_query = select(Employee).where(Employee.organization_id == org_id, Employee.status == "active").order_by(Employee.full_name)
    if department_id is not None:
        emp_query = emp_query.where(Employee.department_id == department_id)
    result = []
    for e in db.scalars(emp_query):
        records = db.scalars(select(Attendance).where(
            Attendance.employee_id == e.id, Attendance.date >= start, Attendance.date <= end)).all()
        count = lambda st: sum(1 for r in records if r.status == st)
        result.append(AttendanceSummaryRow(
            employee_id=e.id, full_name=e.full_name,
            days_present=count("present") + count("late"), days_late=count("late"),
            days_absent=count("absent"), days_leave=count("leave"),
            total_hours=round(sum(r.work_hours or 0 for r in records), 2),
        ))
    return result


@router.get("", response_model=list[AttendanceOut])
def list_attendance(db: DB, user: CurrentUser, employee_id: Optional[int] = None,
                    date_from: Optional[date_type] = None, date_to: Optional[date_type] = None):
    """Employee: own rows only. HR: everyone (optionally ?employee_id=, ?date_from=, ?date_to=)."""
    query = (
        select(Attendance)
        .where(Attendance.organization_id == user.organization_id)
        .order_by(Attendance.date.desc())
    )
    if user.role != "hr":
        own = db.scalar(select(Employee).where(Employee.user_id == user.id))
        if not own:
            return []
        query = query.where(Attendance.employee_id == own.id)
    elif employee_id is not None:
        query = query.where(Attendance.employee_id == employee_id)
    if date_from:
        query = query.where(Attendance.date >= date_from)
    if date_to:
        query = query.where(Attendance.date <= date_to)
    return db.scalars(query).all()


@router.get("/{att_id}", response_model=AttendanceOut)
def get_attendance(att_id: int, db: DB, user: CurrentUser):
    att = _get_or_404(db, att_id, user.organization_id)
    if user.role != "hr":
        own = db.scalar(select(Employee).where(Employee.user_id == user.id))
        if not own or att.employee_id != own.id:
            raise HTTPException(status_code=403, detail="You can only view your own attendance")
    return att


@router.put("/{att_id}", response_model=AttendanceOut)
def correct_attendance(att_id: int, data: AttendanceUpdate, db: DB, hr: HRUser):
    att = _get_or_404(db, att_id, hr.organization_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(att, field, value)
    db.commit()
    db.refresh(att)
    return att


@router.delete("/{att_id}", status_code=204)
def delete_attendance(att_id: int, db: DB, hr: HRUser):
    att = _get_or_404(db, att_id, hr.organization_id)
    db.delete(att)
    db.commit()
