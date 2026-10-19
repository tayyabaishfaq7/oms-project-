"""
============================================================
 DAY 4 — SQLALCHEMY: ENGINE + SESSION
============================================================
Three SQLAlchemy building blocks, in order:

1. ENGINE  — the actual connection to PostgreSQL. One engine per app,
   created once at import time from DATABASE_URL.

2. SESSION — a single "conversation" with the database: a place to
   stage changes (db.add), run queries (db.scalars/db.get), and
   decide when to actually save them (db.commit). We open a NEW
   session per request (see get_db below) and always close it —
   this is why every router function takes a `db` argument.

3. BASE    — the parent class every table (model) inherits from.
   SQLAlchemy uses Base.metadata to know what tables exist, so it
   can create them with Base.metadata.create_all() in main.py.

Request flow reminder (Day 2): Router function gets its own `db`
session via FastAPI's dependency injection (Depends(get_db)) — this
is how "database roles" plug into the "request flow".
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

# autoflush=False / autocommit=False: WE decide when to save (explicit db.commit()),
# nothing happens automatically behind our back.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Every model in app/models.py inherits from this."""


def get_db():
    """
    FastAPI dependency: opens one session per request, hands it to the
    endpoint function, then closes it — even if the endpoint raised an error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Shortcut type: writing `db: DB` in a router function means
# "FastAPI, run get_db() first and inject its session here."
DB = Annotated[Session, Depends(get_db)]
