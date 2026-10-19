"""
Employees. HR: full access within their organization.
Employee: can only see/update their OWN profile (phone/email only).
Every employee has a POSITION. The position decides the department:
  - department position (e.g. 'UI/UX Designer')  -> the employee's department is that position's department
  - org-wide position (Chairman, CEO, General Manager) -> the employee has no department
If a department_id is sent it must match the position, and a designation must belong to the same department.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser, HRUser
from app.models import Department, Designation, Employee, Position, Shift, User
from app.schemas import EmployeeCreate, EmployeeOut, EmployeeSelfUpdate, EmployeeUpdate

router = APIRouter(prefix="/employees", tags=["Employees"])


def _get_or_404(db, employee_id: int, org_id: int) -> Employee:
    emp = db.get(Employee, employee_id)
    if not emp or emp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


def _check_ownership(employee: Employee, user) -> None:
    if user.role != "hr" and employee.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only access your own employee record")


def _exists_in_org(db, model, obj_id, org_id) -> bool:
    obj = db.get(model, obj_id)
    return bool(obj and obj.organization_id == org_id)


def _validate_refs(db, org_id, *, user_id=None, department_id=None, position_id=None,
                   designation_id=None, shift_id=None, manager_id=None):
    """Every referenced row must exist AND belong to the same organization."""
    checks = [
        (user_id, User, "user_id"),
        (department_id, Department, "department_id"),
        (position_id, Position, "position_id"),
        (designation_id, Designation, "designation_id"),
        (shift_id, Shift, "shift_id"),
        (manager_id, Employee, "manager_id"),
    ]
    for value, model, name in checks:
        if value is not None and not _exists_in_org(db, model, value, org_id):
            raise HTTPException(status_code=400, detail=f"{name} does not exist")


def _resolve_department(db, position_id: int, department_id):
    """Return the employee's final department_id, or raise 400 if position and department disagree."""
    pos = db.get(Position, position_id)
    if pos.department_id is None:                       # org-wide executive position
        if department_id is not None:
            raise HTTPException(status_code=400, detail="This is an org-wide position; leave department_id empty")
        return None
    if department_id is not None and department_id != pos.department_id:
        raise HTTPException(status_code=400, detail="position_id does not belong to the employee's department")
    return pos.department_id


def _check_designation_department(db, designation_id, department_id):
    if designation_id is None:
        return
    des = db.get(Designation, designation_id)
    if department_id is None or des.department_id != department_id:
        raise HTTPException(status_code=400, detail="designation_id does not belong to the employee's department (send designation_id: null to clear it)")


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(data: EmployeeCreate, db: DB, hr: HRUser):
    org_id = hr.organization_id
    _validate_refs(
        db, org_id, user_id=data.user_id, department_id=data.department_id, position_id=data.position_id,
        designation_id=data.designation_id, shift_id=data.shift_id, manager_id=data.manager_id,
    )
    final_department = _resolve_department(db, data.position_id, data.department_id)
    _check_designation_department(db, data.designation_id, final_department)
    if db.scalar(select(Employee).where(Employee.user_id == data.user_id)):
        raise HTTPException(status_code=400, detail="This user already has an employee profile")
    if db.scalar(select(Employee).where(Employee.email == data.email)):
        raise HTTPException(status_code=400, detail="Email already used by another employee")
    values = data.model_dump()
    values["department_id"] = final_department
    emp = Employee(organization_id=org_id, **values)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("", response_model=list[EmployeeOut])
def list_employees(db: DB, user: CurrentUser):
    """HR sees every employee in their organization. A non-HR user sees only their own record."""
    query = select(Employee).where(Employee.organization_id == user.organization_id).order_by(Employee.id)
    if user.role != "hr":
        query = query.where(Employee.user_id == user.id)
    return db.scalars(query).all()


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: DB, user: CurrentUser):
    emp = _get_or_404(db, employee_id, user.organization_id)
    _check_ownership(emp, user)
    return emp


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, data: EmployeeUpdate, db: DB, user: CurrentUser):
    """HR: any field. Employee: own record, phone/email only (anything else -> 403)."""
    emp = _get_or_404(db, employee_id, user.organization_id)
    _check_ownership(emp, user)
    changes = data.model_dump(exclude_unset=True)

    if user.role != "hr":
        allowed = set(EmployeeSelfUpdate.model_fields.keys())
        if set(changes) - allowed:
            raise HTTPException(status_code=403, detail=f"You may only update: {', '.join(sorted(allowed))}")

    _validate_refs(
        db, user.organization_id,
        department_id=changes.get("department_id"), position_id=changes.get("position_id"),
        designation_id=changes.get("designation_id"), shift_id=changes.get("shift_id"),
        manager_id=changes.get("manager_id"),
    )
    if changes.get("manager_id") == emp.id:
        raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
    # Re-check position / department / designation using the FINAL values after this update.
    if {"department_id", "position_id", "designation_id"} & set(changes):
        final_position = changes.get("position_id", emp.position_id)
        if "department_id" in changes:
            wanted_department = changes["department_id"]
        else:                                   # only the position changed -> department follows the position
            wanted_department = None if "position_id" in changes else emp.department_id
        final_department = _resolve_department(db, final_position, wanted_department)
        changes["department_id"] = final_department
        _check_designation_department(db, changes.get("designation_id", emp.designation_id), final_department)
    if "email" in changes:
        existing = db.scalar(select(Employee).where(Employee.email == changes["email"]))
        if existing and existing.id != employee_id:
            raise HTTPException(status_code=400, detail="Email already used by another employee")

    for field, value in changes.items():
        setattr(emp, field, value)
    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: DB, hr: HRUser):
    emp = _get_or_404(db, employee_id, hr.organization_id)
    db.delete(emp)
    db.commit()
