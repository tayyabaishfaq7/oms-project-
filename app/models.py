"""
PostgreSQL data modelling.

MULTI-TENANCY: every table (except `organizations` itself) has an
`organization_id` FK. All queries in the routers filter by the logged-in
user's organization_id, so one organization can never see another's data.

ENTITIES
organizations    <- the company/tenant that owns everything below
users            <- login accounts (role: hr / employee), belong to an organization
departments      <- e.g. Engineering, HR, Sales
positions        <- the org-chart boxes. Either ORG-WIDE (Chairman, CEO, General Manager: no department)
                    or DEPARTMENT-SPECIFIC (IT Manager, Software Engineer ...). Each position can
                    "report to" another position, which is what builds the hierarchy tree.
designations     <- job titles + seniority level, belong to a department
shifts           <- work shift timings
employees        <- one profile per user; has a position (and the position's department)
attendance       <- one row per employee per day
leave_requests   <- leave applications, approved/rejected by HR
"""
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _org_fk() -> Mapped[int]:
    """Same column on every tenant table: FK -> organizations.id, indexed (filtered on every request)."""
    return mapped_column(ForeignKey("organizations.id"), index=True)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    """Login accounts. role is 'hr' or 'employee'. Username/email stay globally unique (login is by username)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="employee")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Department(Base):
    __tablename__ = "departments"
    # Department names are unique PER ORGANIZATION (two orgs may both have "Sales").
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_department_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Position(Base):
    """One box on the organization chart.

    * department_id = NULL  -> ORG-WIDE position (Chairman, CEO, General Manager).
    * department_id = N     -> belongs to that department only (e.g. 'UI/UX Designer' in Web Design).
    * reports_to_id         -> the position directly above this one (builds the tree).
    * rank                  -> depth in the chart: 1 = top (Chairman), 2 = CEO, 3 = General Manager,
                               4 = Department Manager, 5 = team members ...
    """
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    reports_to_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Designation(Base):
    __tablename__ = "designations"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    title: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    level: Mapped[str] = mapped_column(String(20), default="junior")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    name: Mapped[str] = mapped_column(String(50))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    national_id: Mapped[str] = mapped_column(String(30), nullable=True)
    # department_id is NULL for org-wide executives (Chairman, CEO, General Manager).
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))          # org-wide, or from department_id
    designation_id: Mapped[int] = mapped_column(ForeignKey("designations.id"), nullable=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), nullable=True)
    hire_date: Mapped[date] = mapped_column(Date)
    salary: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    manager_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_employee_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    date: Mapped[date] = mapped_column(Date)
    check_in: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="present")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    @property
    def work_hours(self) -> float | None:
        """Hours between check-in and check-out (None until the employee checks out)."""
        if self.check_in and self.check_out:
            return round((self.check_out - self.check_in).total_seconds() / 3600, 2)
        return None


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    leave_type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
