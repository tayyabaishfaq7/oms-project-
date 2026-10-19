"""User account management. HR only, limited to HR's own organization."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import DB
from app.core.security import hash_password
from app.dependencies import HRUser
from app.models import User
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


def _get_or_404(db, user_id: int, org_id: int) -> User:
    user = db.get(User, user_id)
    # Another organization's user looks exactly like a missing one -> 404.
    if not user or user.organization_id != org_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: DB, hr: HRUser):
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        organization_id=hr.organization_id,
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: DB, hr: HRUser):
    return db.scalars(
        select(User).where(User.organization_id == hr.organization_id).order_by(User.id)
    ).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DB, hr: HRUser):
    return _get_or_404(db, user_id, hr.organization_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: DB, hr: HRUser):
    user = _get_or_404(db, user_id, hr.organization_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: DB, hr: HRUser):
    user = _get_or_404(db, user_id, hr.organization_id)
    if user.id == hr.id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    db.delete(user)
    db.commit()
