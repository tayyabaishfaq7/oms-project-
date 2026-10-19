"""Auth: register (self sign-up as employee), login, me."""
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.core.security import create_access_token, hash_password, verify_password
from app.dependencies import CurrentUser
from app.models import Organization, User
from app.schemas import Token, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserRegister, db: DB):
    """Self sign-up. Role is ALWAYS 'employee' — HR accounts are created via
    POST /organizations (new org) or POST /users (by an existing HR)."""
    if not db.get(Organization, data.organization_id):
        raise HTTPException(status_code=400, detail="organization_id does not exist")
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        organization_id=data.organization_id,
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="employee",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(username: Annotated[str, Form()], password: Annotated[str, Form()], db: DB):
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is deactivated")
    return Token(access_token=create_access_token(user.username, user.role), token_type="bearer")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
