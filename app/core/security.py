"""
============================================================
 DAY 6 — AUTHENTICATION FUNDAMENTALS (part 1: the tools)
============================================================
Two separate concerns live here:

1. PASSWORD HASHING
   We NEVER store a real password. bcrypt turns it into a one-way
   hash — you can check a password against a hash, but you cannot
   reverse a hash back into the password. Even if the database
   leaks, passwords stay safe.

2. JWT (JSON Web Token) — the "access token" concept
   A JWT is a signed, tamper-proof piece of text the server gives
   the client after a successful login. It carries:
     - WHO the user is (the "sub"/subject claim = username)
     - WHAT role they have (custom "role" claim)
     - WHEN it expires ("exp" claim)
   The client sends this token back on every future request
   (as "Authorization: Bearer <token>"), so the server doesn't need
   to look the user up by password again — it just verifies the
   token's signature, which only the server's SECRET_KEY could have
   produced. This is what makes a route "protected" (Day 6, part 2
   is in app/dependencies.py).
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


def hash_password(password: str) -> str:
    """One-way hash. Store ONLY this, never the real password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Check a login attempt's password against the stored hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(username: str, role: str) -> str:
    """Build and sign a JWT access token after a successful login."""
    payload = {
        "sub": username,                          # who
        "role": role,                              # what they're allowed to do
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),  # when it dies
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Verify the signature + expiry and return the payload.
    Raises jwt.PyJWTError if the token is fake, altered, or expired —
    the caller (see dependencies.py) turns that into a 401 response.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
