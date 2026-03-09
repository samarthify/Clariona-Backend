"""
Session utilities for safe transaction handling.

Prevents transaction leaks by enforcing commit/rollback/close in a single pattern.
Use session_scope for any code that opens a DB session — ensures the connection
is always returned to the pool, even on exception.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from src.api.database import SessionLocal


@contextmanager
def session_scope(commit_on_success: bool = True) -> Generator[Session, None, None]:
    """
    Context manager that guarantees session cleanup.

    Use for any block that performs DB work. Ensures:
    - commit() on normal exit (if commit_on_success=True)
    - rollback() on exception
    - close() always (returns connection to pool)

    Example:
        with session_scope() as db:
            record = db.query(Model).first()
            record.name = "updated"
        # commit + close happen here
    """
    session = SessionLocal()
    try:
        yield session
        if commit_on_success:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
