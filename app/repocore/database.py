"""
RepoCore Database Interface — Bridges directly to the unified app.db.session.
Avoids competing engines or duplicate connections.
"""
from app.db.session import (
    async_engine as engine,
    sync_engine,
    get_async_db as get_db,
    AsyncSessionLocal,
    SessionLocal,
    get_async_engine as get_engine,
)

__all__ = [
    "engine",
    "sync_engine",
    "get_db",
    "AsyncSessionLocal",
    "SessionLocal",
    "get_engine",
]
