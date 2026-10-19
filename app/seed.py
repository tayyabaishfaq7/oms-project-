"""
FAKE / DEMO DATA for the whole system.

Fills: departments, positions (org chart), designations, shifts, users, employees,
attendance (last ~6 weeks) and leave requests -- so every GET / PUT / DELETE in /docs
returns real-looking rows from the very first run.

* Runs automatically on startup when SEED_DEMO_DATA=true (see main.py) -- but ONLY if the
  organization has no employees yet, so it never creates duplicates on restart.
* Run by hand:      python -m app.seed            (seed if empty)
* Wipe + re-seed:   python -m app.seed --reset    (deletes ALL org data except the HR login)

All demo employees log in with password:  employee123   (username e.g. bilal.ahmed)
"""
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import HR_ORG_NAME, HR_USERNAME, LATE_GRACE_MINUTES, TIMEZONE
from app.core.security import hash_password

LOCAL_TZ = ZoneInfo(TIMEZONE)
DEMO_PASSWORD = "employee123"

# ----------------------------------------------------------------------------------------------
# STATIC DATA
# ----------------------------------------------------------------------------------------------
DEPARTMENTS = {
    "Engineering": "Software development, QA and DevOps",
    "Human Resources": "Hiring, payroll and employee relations",
    "Sales": "Client acquisition and account management",
    "Marketing": "Branding, design and content",
    "Finance": "Accounts, budgeting and audits",
    "Operations": "Office, admin and logistics",
}

SHIFTS = {  # name: (start, end)
    "Morning": (time(8, 0), time(16, 0)),
    "General": (time(9, 0), time(17, 0)),
    "Evening": (time(14, 0), time(22, 0)),
}

# (department, title, level)
DESIGNATIONS = [
    ("Engineering", "Engineering Manager", "manager"),
    ("Engineering", "Tech Lead", "lead"),
    ("Engineering", "Senior Software Engineer", "senior"),
    ("Engineering", "Software Engineer", "junior"),
    ("Engineering", "QA Engineer", "junior"),
    ("Engineering", "Intern Developer", "intern"),
    ("Human Resources", "HR Manager", "manager"),
    ("Human Resources", "HR Executive", "junior"),
    ("Sales", "Sales Manager", "manager"),
    ("Sales", "Senior Sales Executive", "senior"),
    ("Sales", "Sales Executive", "junior"),
    ("Marketing", "Marketing Manager", "manager"),
    ("Marketing", "Graphic Designer", "junior"),
    ("Marketing", "Content Writer", "junior"),
    ("Finance", "Finance Manager", "manager"),
    ("Finance", "Senior Accountant", "senior"),
    ("Operations", "Operations Manager", "manager"),
    ("Operations", "Office Coordinator", "junior"),
]

# ORG-WIDE positions (no department): title, rank, reports_to
ORG_POSITIONS = [
    ("Chairman", 1, None),
    ("CEO", 2, "Chairman"),
    ("General Manager", 3, "CEO"),
]

# DEPARTMENT positions: (department, title, reports_to) -- reports_to is an org-wide title or
# a title in the same department. Rank is computed from the parent (parent.rank + 1).
DEPT_POSITIONS = [
    ("Engineering", "Engineering Manager", "General Manager"),
    ("Engineering", "Tech Lead", "Engineering Manager"),
    ("Engineering", "Software Engineer", "Tech Lead"),
    ("Engineering", "QA Engineer", "Engineering Manager"),
    ("Engineering", "Intern", "Tech Lead"),
    ("Human Resources", "HR Manager", "General Manager"),
    ("Human Resources", "HR Executive", "HR Manager"),
    ("Sales", "Sales Manager", "General Manager"),
    ("Sales", "Sales Executive", "Sales Manager"),
    ("Marketing", "Marketing Manager", "General Manager"),
    ("Marketing", "Graphic Designer", "Marketing Manager"),
    ("Marketing", "Content Writer", "Marketing Manager"),
    ("Finance", "Finance Manager", "General Manager"),
    ("Finance", "Accountant", "Finance Manager"),
    ("Operations", "Operations Manager", "General Manager"),
    ("Operations", "Office Coordinator", "Operations Manager"),
]

# username, full name, department, position, designation, shift, hire date, salary, manager username, status
#   department = None  -> org-wide executive (no department, no designation)
EMPLOYEES = [
    ("tariq.mehmood",   "Tariq Mehmood",   None, "Chairman",         None, None,      date(2015, 1, 5),  950000, None,             "active"),
    ("ayesha.siddiqui", "Ayesha Siddiqui", None, "CEO",              None, None,      date(2016, 3, 14), 780000, "tariq.mehmood", "active"),
    ("usman.farooq",    "Usman Farooq",    None, "General Manager",  None, "General", date(2017, 6, 1),  520000, "ayesha.siddiqui", "active"),

    ("hamza.ali",    "Hamza Ali",    "Engineering", "Engineering Manager", "Engineering Manager",     "General", date(2018, 2, 12), 340000, "usman.farooq", "active"),
    ("sara.qureshi", "Sara Qureshi", "Engineering", "Tech Lead",           "Tech Lead",               "General", date(2019, 8, 5),  280000, "hamza.ali",    "active"),
    ("bilal.ahmed",  "Bilal Ahmed",  "Engineering", "Software Engineer",   "Senior Software Engineer","General", date(2020, 1, 20), 210000, "sara.qureshi", "active"),
    ("sana.malik",   "Sana Malik",   "Engineering", "Software Engineer",   "Software Engineer",       "Morning", date(2022, 9, 1),  150000, "sara.qureshi", "active"),
    ("zain.abbas",   "Zain Abbas",   "Engineering", "Software Engineer",   "Software Engineer",       "Evening", date(2023, 4, 10), 140000, "sara.qureshi", "active"),
    ("hira.noor",    "Hira Noor",    "Engineering", "QA Engineer",         "QA Engineer",             "General", date(2022, 5, 16), 130000, "hamza.ali",    "active"),
    ("ali.hassan",   "Ali Hassan",   "Engineering", "Intern",              "Intern Developer",        "Morning", date(2026, 6, 15), 40000,  "sara.qureshi", "active"),
    ("hassan.raza",  "Hassan Raza",  "Engineering", "Software Engineer",   "Software Engineer",       "General", date(2021, 7, 19), 135000, "sara.qureshi", "resigned"),

    ("maryam.aslam", "Maryam Aslam", "Human Resources", "HR Manager",   "HR Manager",   "General", date(2018, 10, 8), 260000, "usman.farooq", "active"),
    ("kinza.rauf",   "Kinza Rauf",   "Human Resources", "HR Executive", "HR Executive", "General", date(2023, 1, 9),  95000,  "maryam.aslam", "active"),

    ("faisal.raza",  "Faisal Raza",  "Sales", "Sales Manager",   "Sales Manager",          "General", date(2018, 4, 23), 300000, "usman.farooq", "active"),
    ("daniyal.shah", "Daniyal Shah", "Sales", "Sales Executive", "Senior Sales Executive", "Morning", date(2020, 11, 2), 130000, "faisal.raza",  "active"),
    ("rabia.khan",   "Rabia Khan",   "Sales", "Sales Executive", "Sales Executive",        "Evening", date(2024, 2, 5),  90000,  "faisal.raza",  "active"),

    ("noman.iqbal",  "Noman Iqbal",  "Marketing", "Marketing Manager", "Marketing Manager", "General", date(2019, 3, 18), 270000, "usman.farooq", "active"),
    ("laiba.tariq",  "Laiba Tariq",  "Marketing", "Graphic Designer",  "Graphic Designer",  "General", date(2022, 12, 1), 110000, "noman.iqbal",  "active"),
    ("areeba.javed", "Areeba Javed", "Marketing", "Content Writer",    "Content Writer",    "Morning", date(2024, 8, 12), 85000,  "noman.iqbal",  "active"),

    ("saad.hussain", "Saad Hussain", "Finance", "Finance Manager", "Finance Manager",    "General", date(2017, 9, 11), 310000, "usman.farooq", "active"),
    ("mehwish.ali",  "Mehwish Ali",  "Finance", "Accountant",      "Senior Accountant",  "General", date(2021, 3, 29), 125000, "saad.hussain", "active"),

    ("imran.yousaf", "Imran Yousaf", "Operations", "Operations Manager", "Operations Manager", "General", date(2018, 7, 2),  250000, "usman.farooq",  "active"),
    ("zara.pervaiz", "Zara Pervaiz", "Operations", "Office Coordinator", "Office Coordinator", "Morning", date(2023, 10, 16), 80000,  "imran.yousaf", "active"),
]

# username, type, start offset (days from today), length (days), status, reason
LEAVES = [
    ("bilal.ahmed",  "annual", -20, 3, "approved", "Family trip to Murree"),
    ("sana.malik",   "sick",   -9,  2, "approved", "Fever and flu"),
    ("rabia.khan",   "casual", -5,  1, "approved", "Personal work"),
    ("hira.noor",    "annual", 7,   5, "pending",  "Sister's wedding"),
    ("zain.abbas",   "sick",   2,   2, "pending",  "Dental procedure"),
    ("laiba.tariq",  "casual", 4,   1, "pending",  "Passport office visit"),
    ("kinza.rauf",   "annual", -30, 4, "rejected", "Vacation (payroll week)"),
    ("daniyal.shah", "casual", -14, 1, "rejected", "Short notice"),
    ("mehwish.ali",  "sick",   -3,  2, "approved", "Migraine"),
    ("areeba.javed", "annual", 14,  7, "pending",  "Umrah trip"),
]


# ----------------------------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------------------------
def _to_utc_naive(local_date: date, local_time: time, plus_minutes: int = 0) -> datetime:
    """Local (Asia/Karachi) wall-clock -> naive UTC, which is how attendance times are stored."""
    local = datetime.combine(local_date, local_time, tzinfo=LOCAL_TZ) + timedelta(minutes=plus_minutes)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _wipe(db: Session, org_id: int) -> None:
    """Delete everything in this organization except the organization row and the HR login."""
    # Children first so no foreign key is violated.
    db.execute(delete(m.LeaveRequest).where(m.LeaveRequest.organization_id == org_id))
    db.execute(delete(m.Attendance).where(m.Attendance.organization_id == org_id))
    db.execute(m.Employee.__table__.update().where(m.Employee.organization_id == org_id).values(manager_id=None))
    db.execute(delete(m.Employee).where(m.Employee.organization_id == org_id))
    db.execute(m.Position.__table__.update().where(m.Position.organization_id == org_id).values(reports_to_id=None))
    db.execute(delete(m.Position).where(m.Position.organization_id == org_id))
    db.execute(delete(m.Designation).where(m.Designation.organization_id == org_id))
    db.execute(delete(m.Shift).where(m.Shift.organization_id == org_id))
    db.execute(delete(m.Department).where(m.Department.organization_id == org_id))
    db.execute(delete(m.User).where(m.User.organization_id == org_id, m.User.username != HR_USERNAME))
    db.commit()


# ----------------------------------------------------------------------------------------------
# MAIN SEED
# ----------------------------------------------------------------------------------------------
def _find_org(db: Session):
    """The organization that owns the HR login (works even if HR_ORG_NAME differs from the old DB's org name)."""
    hr = db.scalar(select(m.User).where(m.User.username == HR_USERNAME))
    if hr:
        return db.get(m.Organization, hr.organization_id)
    return db.scalar(select(m.Organization).where(m.Organization.name == HR_ORG_NAME))


def seed_demo_data(db: Session, reset: bool = False) -> bool:
    """Insert the demo data. Returns False (and does nothing) if employees already exist
    (unless reset=True, which first wipes the organization's data except the HR login)."""
    org = _find_org(db)
    if not org:
        return False
    if reset:
        _wipe(db, org.id)
    if db.scalar(select(func.count(m.Employee.id)).where(m.Employee.organization_id == org.id)):
        return False

    rng = random.Random(42)           # fixed seed -> same demo data every time
    org_id = org.id
    hr_user = db.scalar(select(m.User).where(m.User.username == HR_USERNAME))

    # --- departments ---------------------------------------------------------------------------
    depts = {}
    for name, desc in DEPARTMENTS.items():
        depts[name] = m.Department(organization_id=org_id, name=name, description=desc)
        db.add(depts[name])
    db.flush()

    # --- shifts --------------------------------------------------------------------------------
    shifts = {}
    for name, (start, end) in SHIFTS.items():
        shifts[name] = m.Shift(organization_id=org_id, name=name, start_time=start, end_time=end)
        db.add(shifts[name])
    db.flush()

    # --- designations --------------------------------------------------------------------------
    designations = {}
    for dept, title, level in DESIGNATIONS:
        designations[(dept, title)] = m.Designation(
            organization_id=org_id, title=title, department_id=depts[dept].id, level=level)
        db.add(designations[(dept, title)])
    db.flush()

    # --- positions (org chart) -----------------------------------------------------------------
    org_pos = {}
    for title, rank, parent in ORG_POSITIONS:
        org_pos[title] = m.Position(
            organization_id=org_id, title=title, rank=rank, department_id=None,
            reports_to_id=org_pos[parent].id if parent else None,
            description=f"Org-wide executive position: {title}")
        db.add(org_pos[title])
        db.flush()
    dept_pos = {}
    for dept, title, parent in DEPT_POSITIONS:
        parent_obj = dept_pos.get((dept, parent)) or org_pos[parent]
        dept_pos[(dept, title)] = m.Position(
            organization_id=org_id, title=title, department_id=depts[dept].id,
            reports_to_id=parent_obj.id, rank=parent_obj.rank + 1,
            description=f"{title} - {dept}")
        db.add(dept_pos[(dept, title)])
        db.flush()

    # --- users + employees ---------------------------------------------------------------------
    pw_hash = hash_password(DEMO_PASSWORD)    # hash once, reuse (bcrypt is slow on purpose)
    emps = {}
    for i, (username, full, dept, pos_title, des_title, shift, hired, salary, _mgr, status) in enumerate(EMPLOYEES, 1):
        user = m.User(organization_id=org_id, username=username, email=f"{username}@example.com",
                      hashed_password=pw_hash, role="employee", is_active=(status == "active"))
        db.add(user)
        db.flush()
        position = dept_pos[(dept, pos_title)] if dept else org_pos[pos_title]
        emp = m.Employee(
            organization_id=org_id, user_id=user.id, full_name=full, email=f"{username}@example.com",
            phone=f"0300-{1000000 + i * 111111}"[:13], national_id=f"37405-{1234500 + i * 7919:07d}-{i % 10}",
            department_id=depts[dept].id if dept else None, position_id=position.id,
            designation_id=designations[(dept, des_title)].id if des_title else None,
            shift_id=shifts[shift].id if shift else None,
            hire_date=hired, salary=salary, status=status)
        db.add(emp)
        emps[username] = emp
    db.flush()
    for username, *_rest in EMPLOYEES:        # second pass: managers (needs every id to exist)
        mgr = _rest[-2]
        if mgr:
            emps[username].manager_id = emps[mgr].id
    db.flush()

    # --- leave requests ------------------------------------------------------------------------
    today = datetime.now(LOCAL_TZ).date()
    leave_days = {}                            # employee id -> set of approved leave dates
    for username, ltype, offset, length, status, reason in LEAVES:
        start = today + timedelta(days=offset)
        end = start + timedelta(days=length - 1)
        db.add(m.LeaveRequest(
            organization_id=org_id, employee_id=emps[username].id, leave_type=ltype,
            start_date=start, end_date=end, reason=reason, status=status,
            approved_by=hr_user.id if status in ("approved", "rejected") and hr_user else None))
        if status == "approved":
            leave_days.setdefault(emps[username].id, set()).update(start + timedelta(days=d) for d in range(length))

    # --- attendance: last 42 days, weekdays only ----------------------------------------------
    now_local = datetime.now(LOCAL_TZ)
    for username, emp in emps.items():
        if emp.status != "active" or emp.shift_id is None:
            continue
        shift = next(s for s in shifts.values() if s.id == emp.shift_id)
        for back in range(42, -1, -1):
            day = today - timedelta(days=back)
            if day.weekday() >= 5 or day < emp.hire_date:           # skip Sat/Sun and pre-hire days
                continue
            if day in leave_days.get(emp.id, set()):
                db.add(m.Attendance(organization_id=org_id, employee_id=emp.id, date=day, status="leave"))
                continue
            roll = rng.random()
            if day == today:                                        # today: some in, some not yet
                if roll > 0.75:
                    continue
                offset = rng.randint(-10, 10)
                check_in = _to_utc_naive(day, shift.start_time, offset)
                if check_in > now_local.astimezone(timezone.utc).replace(tzinfo=None):
                    continue                                        # shift hasn't started yet
                db.add(m.Attendance(organization_id=org_id, employee_id=emp.id, date=day,
                                    check_in=check_in, status="present"))
                continue
            if roll < 0.05:                                         # absent
                db.add(m.Attendance(organization_id=org_id, employee_id=emp.id, date=day, status="absent"))
                continue
            late = roll < 0.17
            offset = rng.randint(LATE_GRACE_MINUTES + 1, LATE_GRACE_MINUTES + 75) if late else rng.randint(-15, LATE_GRACE_MINUTES - 1)
            db.add(m.Attendance(
                organization_id=org_id, employee_id=emp.id, date=day,
                check_in=_to_utc_naive(day, shift.start_time, offset),
                check_out=_to_utc_naive(day, shift.end_time, rng.randint(-20, 45)),
                status="late" if late else "present"))

    db.commit()
    return True


if __name__ == "__main__":
    from app.core.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        org = _find_org(session)
        if not org:
            sys.exit("Organization not found - start the API once first (it creates the org + HR login).")
        print("Demo data inserted." if seed_demo_data(session, reset="--reset" in sys.argv) else "Employees already exist - nothing inserted (use --reset to re-seed).")
