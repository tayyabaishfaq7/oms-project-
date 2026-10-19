"""Config: secrets and settings are read from .env, never hardcoded."""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/ems_db"
)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# --- First organization + first HR account, auto-created on startup ---
HR_ORG_NAME = os.getenv("HR_ORG_NAME", "Default Organization")   # NEW
HR_USERNAME = os.getenv("HR_USERNAME", "hr_admin")
HR_EMAIL = os.getenv("HR_EMAIL", "hr_admin@example.com")
HR_PASSWORD = os.getenv("HR_PASSWORD", "hradmin123")

# --- Attendance rules ---
TIMEZONE = os.getenv("TIMEZONE", "Asia/Karachi")              # used for "today" and for late detection
LATE_GRACE_MINUTES = int(os.getenv("LATE_GRACE_MINUTES", "15"))  # check-in later than shift start + grace = "late"

# --- Demo data: fake employees, attendance, shifts etc. inserted on startup if DB has no employees ---
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() in ("1", "true", "yes")
SEED_RESET = os.getenv("SEED_RESET", "false").lower() in ("1", "true", "yes")   # true = wipe org data + re-seed on startup
