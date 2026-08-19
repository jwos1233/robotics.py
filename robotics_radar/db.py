from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from robotics_radar.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Read-only API, so no commit on the happy path."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


# Arbitrary but fixed key identifying the bootstrap (seed + series register)
# critical section.
BOOTSTRAP_LOCK_KEY = 8_483_400


def acquire_bootstrap_lock(session: Session) -> None:
    """Serialise boot-time reference-data writes across containers.

    Seeding runs on every boot so the deployed reference data always matches
    the repo. With more than one replica those boots overlap, and two
    processes inserting the same nodes race on the unique constraints. The
    lock is transaction-scoped, so it releases on commit or rollback without
    any cleanup path of its own.
    """
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BOOTSTRAP_LOCK_KEY})
