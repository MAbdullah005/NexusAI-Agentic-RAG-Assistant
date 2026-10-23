"""
NexusAI & RepoCore Unified Database Session & Engine Configuration
"""
import os
import logging
from typing import Generator, AsyncGenerator, Tuple, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

load_dotenv()
logger = logging.getLogger(__name__)

_sync_engine: Optional[Engine] = None
_async_engine: Optional[AsyncEngine] = None
_SessionLocal: Optional[sessionmaker] = None
_AsyncSessionLocal: Optional[async_sessionmaker] = None
_checkpointer = None
_connection_pool = None


def get_database_urls() -> Tuple[str, str]:
    """
    Parse and format DATABASE_URL for both synchronous (psycopg) and
    asynchronous (asyncpg) drivers.
    """
    raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not raw_url:
        raise ValueError(
            "DATABASE_URL is not set. Please set DATABASE_URL in your .env file "
            "(e.g. postgresql://user:password@localhost:5432/nexusai)."
        )

    # Use make_url to reliably split/recombine regardless of existing driver prefix
    url = make_url(raw_url)
    
    # Sync driver (psycopg 3)
    sync_url = url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    # Async driver (asyncpg)
    async_url = url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)

    return sync_url, async_url


def get_psycopg_conninfo() -> str:
    """
    Return a driver-compatible PostgreSQL connection string/URI for psycopg
    preserving encoded credentials and without manual string concatenation.
    """
    raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not raw_url:
        raise ValueError(
            "DATABASE_URL is not set. Please set DATABASE_URL in your .env file "
            "(e.g. postgresql://user:password@localhost:5432/nexusai)."
        )
    url = make_url(raw_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def get_sync_engine() -> Engine:
    """Lazily create and return the singleton synchronous SQLAlchemy engine."""
    global _sync_engine, _SessionLocal
    if _sync_engine is None:
        sync_url, _ = get_database_urls()
        echo = os.getenv("SQL_ECHO", "0").lower() in ("1", "true", "yes")
        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            echo=echo,
        )
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_sync_engine,
        )
    return _sync_engine


def get_async_engine() -> AsyncEngine:
    """Lazily create and return the singleton asynchronous SQLAlchemy engine."""
    global _async_engine, _AsyncSessionLocal
    if _async_engine is None:
        _, async_url = get_database_urls()
        echo = os.getenv("SQL_ECHO", "0").lower() in ("1", "true", "yes")
        _async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            echo=echo,
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_engine


class LazyEngineProxy:
    """Proxy object so modules importing engines don't crash at startup if DB is offline."""
    def __init__(self, engine_getter):
        self._engine_getter = engine_getter

    def __getattr__(self, name):
        return getattr(self._engine_getter(), name)

    def begin(self, *args, **kwargs):
        return self._engine_getter().begin(*args, **kwargs)

    def connect(self, *args, **kwargs):
        return self._engine_getter().connect(*args, **kwargs)


sync_engine = LazyEngineProxy(get_sync_engine)
async_engine = LazyEngineProxy(get_async_engine)


def SessionLocal() -> Session:
    """Create a new synchronous session using the lazily initialized session factory."""
    get_sync_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def AsyncSessionLocal() -> AsyncSession:
    """Create a new asynchronous session using the lazily initialized session factory."""
    get_async_engine()
    assert _AsyncSessionLocal is not None
    return _AsyncSessionLocal()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for synchronous DB sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for asynchronous DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# =====================================================================
# LANGGRAPH POSTGRES CHECKPOINTER
# =====================================================================

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple


def get_checkpointer():
    """
    Return a LangGraph PostgresSaver backed by a psycopg connection pool.
    Initializes tables via checkpointer.setup() on first run.
    """
    global _checkpointer, _connection_pool
    if _checkpointer is None or (_connection_pool is not None and getattr(_connection_pool, "closed", False)):
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        conninfo = get_psycopg_conninfo()

        _connection_pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=int(os.getenv("DB_POOL_SIZE", "10")),
            kwargs={"autocommit": True},
        )
        _checkpointer = PostgresSaver(_connection_pool)
        try:
            _checkpointer.setup()
            logger.info("LangGraph PostgresSaver checkpointer initialized and tables verified.")
        except Exception as e:
            logger.warning(f"PostgresSaver setup deferred or encountered issue: {e}")

    return _checkpointer


class LazyCheckpointerProxy(BaseCheckpointSaver):
    """
    Proxy object satisfying LangGraph BaseCheckpointSaver.
    Defers live PostgreSQL connection until checkpoint operations are invoked.
    """
    def __init__(self):
        super().__init__()

    @property
    def _target(self):
        return get_checkpointer()

    def get_tuple(self, config):
        return self._target.get_tuple(config)

    def list(self, config, *, filter=None, before=None, limit=None):
        return self._target.list(config, filter=filter, before=before, limit=limit)

    def put(self, config, checkpoint, metadata, new_versions):
        return self._target.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=""):
        return self._target.put_writes(config, writes, task_id, task_path)

    async def aget_tuple(self, config):
        return await self._target.aget_tuple(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        return await self._target.alist(config, filter=filter, before=before, limit=limit)

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await self._target.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await self._target.aput_writes(config, writes, task_id, task_path)

    def __getattr__(self, name):
        return getattr(self._target, name)


checkpointer = LazyCheckpointerProxy()
