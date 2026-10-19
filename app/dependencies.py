"""
============================================================
 DAY 6 — AUTHENTICATION FUNDAMENTALS (part 2: protected routes)
============================================================
This file answers two separate questions, one function each:

  get_current_user  -> WHO are you?    (authentication)
  require_role       -> WHAT can you do? (authorization)

A "protected route" is simply a FastAPI endpoint that takes
`user: CurrentUser` (or `hr: HRUser`) as a parameter. FastAPI runs
the dependency BEFORE the endpoint's own code, so by the time your
function body runs, you already know the request is from a real,
logged-in user (or specifically an HR user).

oauth2_scheme is what makes the green "Authorize" button appear in
Swagger UI — it reads the "Authorization: Bearer <token>" header for us.
"""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from app.core.database import DB
from app.core.security import decode_access_token
from app.models import Employee, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    """Reads the Bearer token, verifies it, and loads the matching User row.
    Any failure (bad signature, expired, unknown user) -> 401 Unauthorized."""
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = decode_access_token(token).get("sub")
    except jwt.PyJWTError:
        raise error
    if not username:
        raise error
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise error
    return user


# Shortcut: `user: CurrentUser` in an endpoint = "must be logged in".
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Factory that builds a role-checking dependency.
    Wrong role -> 403 Forbidden (different from 401: you ARE logged in,
    you're just not ALLOWED to do this)."""

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return user

    return checker


# Shortcut: `hr: HRUser` in an endpoint = "must be logged in AND be HR".
HRUser = Annotated[User, Depends(require_role("hr"))]


def get_current_employee(user: CurrentUser, db: DB) -> Employee:
    """Loads the Employee profile linked to the logged-in user (via user_id).
    404 if HR hasn't created one for this account yet."""
    employee = db.scalar(select(Employee).where(Employee.user_id == user.id))
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile linked to this account")
    return employee


CurrentEmployee = Annotated[Employee, Depends(get_current_employee)]
