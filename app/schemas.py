"""Pydantic schemas: the JSON going IN and OUT of the API.
organization_id is never accepted from the client on tenant data — it is always
taken from the logged-in user's token, so nobody can write into another organization."""
from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

DesignationLevel = Literal["intern", "junior", "senior", "lead", "manager"]


# ---------- Organizations ----------
class OrganizationCreate(BaseModel):
    """Public sign-up of a new organization together with its first HR admin."""
    name: str = Field(min_length=1, max_length=150)
    admin_username: str = Field(min_length=3, max_length=50)
    admin_email: EmailStr
    admin_password: str = Field(min_length=6, max_length=72)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)


class OrganizationOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# ---------- Users / Auth ----------
class UserCreate(BaseModel):
    """Used by HR (POST /users): the user is created inside HR's own organization."""
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    role: Literal["hr", "employee"] = "employee"


class UserRegister(BaseModel):
    """Used by POST /auth/register: self sign-up. Always role=employee."""
    organization_id: int
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    organization_id: int
    username: str
    email: str
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


# ---------- Departments ----------
class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None


class DepartmentOut(DepartmentCreate):
    id: int
    organization_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Positions ----------
class PositionCreate(BaseModel):
    """department_id = None  -> org-wide position (Chairman / CEO / General Manager).
    reports_to_id           -> the position above this one in the chart.
    rank                    -> optional; if omitted it becomes (parent rank + 1), or 1 for a top position."""
    title: str = Field(min_length=1, max_length=100)
    department_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    rank: Optional[int] = Field(default=None, ge=1, le=20)
    description: Optional[str] = Field(default=None, max_length=300)


class PositionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    department_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    rank: Optional[int] = Field(default=None, ge=1, le=20)
    description: Optional[str] = Field(default=None, max_length=300)


class PositionOut(BaseModel):
    id: int
    organization_id: int
    title: str
    department_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    rank: int
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- Organization chart ----------
class OrgChartEmployee(BaseModel):
    id: int
    full_name: str


class OrgChartNode(BaseModel):
    """One box of the chart: a position, the people holding it, and the boxes below it."""
    position_id: int
    title: str
    rank: int
    department: Optional[str] = None      # None = org-wide (Chairman, CEO, General Manager)
    employees: list[OrgChartEmployee] = []
    children: list["OrgChartNode"] = []


class OrgChartOut(BaseModel):
    organization: str
    total_positions: int
    total_employees: int
    chart: list[OrgChartNode]


# ---------- Designations ----------
class DesignationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    department_id: int
    level: DesignationLevel = "junior"


class DesignationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    department_id: Optional[int] = None
    level: Optional[DesignationLevel] = None


class DesignationOut(DesignationCreate):
    id: int
    organization_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Shifts ----------
class ShiftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    start_time: time
    end_time: time


class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None


class ShiftOut(ShiftCreate):
    id: int
    organization_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Employees ----------
class EmployeeCreate(BaseModel):
    user_id: int
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    phone: Optional[str] = None
    national_id: Optional[str] = None
    position_id: int                         # org-wide position, or one that belongs to the department
    department_id: Optional[int] = None      # optional: filled automatically from the position
    designation_id: Optional[int] = None
    shift_id: Optional[int] = None
    hire_date: date
    salary: Optional[float] = None
    manager_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    designation_id: Optional[int] = None
    shift_id: Optional[int] = None
    salary: Optional[float] = None
    status: Optional[Literal["active", "resigned", "terminated"]] = None
    manager_id: Optional[int] = None


class EmployeeSelfUpdate(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class EmployeeOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    department_id: Optional[int] = None
    position_id: int
    designation_id: Optional[int] = None
    shift_id: Optional[int] = None
    hire_date: date
    salary: Optional[float] = None
    status: str
    manager_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- Attendance ----------
class AttendanceOut(BaseModel):
    id: int
    organization_id: int
    employee_id: int
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    work_hours: Optional[float] = None
    status: str
    model_config = ConfigDict(from_attributes=True)


class AttendanceTodayRow(BaseModel):
    """HR dashboard row: one employee and what they did today."""
    employee_id: int
    full_name: str
    department: Optional[str] = None
    position: str
    status: str                               # present / late / absent / leave / not_checked_in
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None


class AttendanceSummaryRow(BaseModel):
    """Monthly totals for one employee."""
    employee_id: int
    full_name: str
    days_present: int
    days_late: int
    days_absent: int
    days_leave: int
    total_hours: float


class AttendanceUpdate(BaseModel):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: Optional[Literal["present", "absent", "leave", "late"]] = None


# ---------- Leave requests ----------
class LeaveCreate(BaseModel):
    leave_type: Literal["sick", "casual", "annual"]
    start_date: date
    end_date: date
    reason: Optional[str] = Field(default=None, max_length=300)


class LeaveOut(BaseModel):
    id: int
    organization_id: int
    employee_id: int
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: str
    approved_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
