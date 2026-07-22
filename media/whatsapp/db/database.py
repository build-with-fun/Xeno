"""SQLAlchemy database engine and session management.

Uses SQLite by default (zero-config, file-based). Can be swapped to
PostgreSQL by changing DATABASE_URL.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

# Database URL: SQLite by default, or PostgreSQL for production scale
# Handle various SQLite URL formats: sqlite:///path, file:path, or bare path
_raw_db_url = getattr(settings, "database_url", "").strip()
if not _raw_db_url:
    # Default: SQLite at data/bot.db
    DATABASE_URL = f"sqlite:///{settings.data_dir / 'bot.db'}"
elif _raw_db_url.startswith("file:"):
    # Convert file:path to sqlite:///path
    _path = _raw_db_url[5:]
    DATABASE_URL = f"sqlite:///{_path}"
elif _raw_db_url.startswith(("sqlite:", "postgresql:", "mysql:", "mssql:")):
    DATABASE_URL = _raw_db_url
else:
    # Bare path — assume SQLite
    DATABASE_URL = f"sqlite:///{_raw_db_url}"

logger.info(f"[DB] Using database URL: {DATABASE_URL}")

# SQLite needs check_same_thread=False for multi-threaded access
_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, **_engine_kwargs)

# Enable WAL mode for SQLite (better concurrent read performance)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, conn_rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Thread-local session storage
_local = threading.local()


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    from .models import Base
    Base.metadata.create_all(engine)
    logger.info(f"[DB] Initialized at {DATABASE_URL}")


def get_session() -> Session:
    """Get a thread-local session. Creates one if none exists."""
    if not hasattr(_local, "session"):
        _local.session = SessionLocal()
    return _local.session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for a session that auto-commits/rolls back.

    Usage:
        with session_scope() as s:
            s.add(Contact(name="Alice"))
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class Database:
    """Convenience wrapper for database operations."""

    @property
    def engine(self):
        return engine

    def init(self) -> None:
        init_db()

    @property
    def session(self) -> Session:
        return get_session()

    def execute_raw(self, sql: str, params: dict | None = None):
        """Execute raw SQL (for admin/migration use)."""
        with engine.connect() as conn:
            result = conn.exec_driver_sql(sql, params or {})
            return result.fetchall()


# Singleton
db = Database()
