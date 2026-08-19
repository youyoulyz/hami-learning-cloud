# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Shared Database Module

Provides a single SQLAlchemy engine and session factory shared across
all modules (quota, auth, etc.). This ensures efficient connection pooling
and consistent database access.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

# Shared declarative base for all models
Base = declarative_base()

# Global singleton instances
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_database(db_url: str) -> Engine:
    """
    Initialize the shared database connection.

    Args:
        db_url: SQLAlchemy database URL

    Returns:
        The SQLAlchemy engine
    """
    global _engine, _SessionFactory

    if _engine is not None:
        return _engine

    _engine = create_engine(db_url, pool_pre_ping=True)
    _SessionFactory = sessionmaker(bind=_engine)

    print(f"[DATABASE] Initialized: {db_url}")
    return _engine


def get_engine() -> Engine:
    """Get the shared database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    return _SessionFactory()


@contextmanager
def session_scope():
    """
    Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.query(...)
            session.add(...)
            # auto-commits on exit, auto-rollbacks on exception
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables():
    """Create all tables registered with the shared Base."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database first.")

    # Import all ORM models to register them with Base
    from core.authenticators import models as _auth_models
    from core.quota import orm as _quota_orm

    # Ensure models are registered (avoid unused import optimization)
    _ = _auth_models.UserPassword
    _ = _quota_orm.UserQuota

    Base.metadata.create_all(_engine)
