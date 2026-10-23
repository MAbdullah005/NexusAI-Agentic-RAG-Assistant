"""
PostgreSQL Memory Store

Handles persistent conversation memory for the LangGraph agent
using PostgreSQL, SQLAlchemy models, and pgvector.
"""
from __future__ import annotations

import os
import uuid
import struct
try:
    import numpy as np
except ImportError:
    np = None
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

from sqlalchemy import select, update, and_, desc, asc
from langchain_core.messages import HumanMessage, AIMessage

from app.utils.logger import get_logger
from app.db.session import (
    SessionLocal,
    checkpointer,
    sync_engine,
    get_sync_engine,
)
from app.db.connection_adapter import get_db_connection

from app.db.models import (
    Base,
    User,
    Thread,
    ThreadContext,
    Document,
    ThreadDocument,
    Message,
    MessageEmbedding,
    utc_now,
)

logger = get_logger(__name__)


def serialize_embedding(vec: List[float]) -> bytes:
    """Serialize list of floats to binary float32 bytes."""
    if np is not None:
        return np.array(vec, dtype=np.float32).tobytes()
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_embedding(blob: bytes) -> List[float]:
    """Deserialize binary float32 bytes to list of floats."""
    if np is not None:
        return np.frombuffer(blob, dtype=np.float32).tolist()
    num_floats = len(blob) // 4
    return list(struct.unpack(f"{num_floats}f", blob))



def init_db(target_engine=None):
    """
    Ensure all tables are created in PostgreSQL.
    """
    eng = target_engine or get_sync_engine()
    try:
        from sqlalchemy import text
        with eng.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(bind=eng)
        logger.info("PostgreSQL database tables verified and initialized.")
    except Exception as e:
        logger.warning(f"PostgreSQL init_db deferred or failed: {e}")


# =====================================================================
# THREAD & MESSAGE UTILITIES
# =====================================================================

def verify_thread_ownership(
    thread_id: str,
    user_id: int,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> bool:
    """Validate whether a thread exists and belongs to the given user."""
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    def _run(s):
        row = s.query(Thread.thread_id).filter(
            Thread.thread_id == thread_id,
            Thread.user_id == user_id,
        ).first()
        return row is not None

    try:
        if active_s:
            return _run(active_s)
        with SessionLocal() as s:
            return _run(s)
    except Exception as e:
        logger.error(f"Thread ownership check failed: {e}")
        return False


def save_message(
    thread_id: str,
    user_id: int,
    role: str,
    content: str,
    message_id: Optional[str] = None,
    strict: bool = False,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    Save a visible chat message to durable PostgreSQL storage.
    Validates that the thread exists and is owned by user_id.
    Prevents duplicate insertion if message_id already exists.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role: '{role}'. Must be 'user' or 'assistant'.")

    active_s = session or (target_conn if hasattr(target_conn, "query") else None)

    def _save(s) -> Optional[Dict[str, Any]]:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        mid = message_id or str(uuid.uuid4())

        existing = s.query(Message).filter(Message.message_id == mid).first()
        if existing:
            if existing.thread_id != thread_id or existing.user_id != user_id or existing.role != role:
                raise ValueError(
                    f"Message ID '{mid}' already exists with conflicting thread, user, or role."
                )
            if existing.content != content:
                if strict:
                    raise ValueError(
                        f"Message ID '{mid}' already exists with conflicting content."
                    )
                logger.warning(
                    f"Reused message_id '{mid}' with different content; preserving original content."
                )
            return {
                "message_id": existing.message_id,
                "thread_id": existing.thread_id,
                "user_id": existing.user_id,
                "role": existing.role,
                "content": existing.content,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
            }

        new_msg = Message(
            message_id=mid,
            thread_id=thread_id,
            user_id=user_id,
            role=role,
            content=content,
            created_at=utc_now(),
        )
        s.add(new_msg)
        s.commit()
        s.refresh(new_msg)

        return {
            "message_id": new_msg.message_id,
            "thread_id": new_msg.thread_id,
            "user_id": new_msg.user_id,
            "role": new_msg.role,
            "content": new_msg.content,
            "created_at": new_msg.created_at.isoformat() if new_msg.created_at else None,
        }

    if active_s:
        return _save(active_s)
    with SessionLocal() as s:
        return _save(s)


def backfill_thread_messages_from_checkpoint(
    thread_id: str,
    user_id: int,
    checkpoint_messages: List[Any],
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """
    Backfill legacy or missing thread messages from LangGraph checkpoint into durable messages table.
    Filters out internal tool messages, tool calls, and system messages.
    """
    def _backfill(s) -> List[Dict[str, Any]]:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        existing_messages = get_thread_messages(thread_id, user_id, session=s)
        existing_ids = {m["message_id"] for m in existing_messages}

        existing_counts: Dict[tuple, int] = {}
        for m in existing_messages:
            key = (m["role"], m["content"])
            existing_counts[key] = existing_counts.get(key, 0) + 1

        backfilled = []
        for idx, msg in enumerate(checkpoint_messages):
            role = None
            msg_type = getattr(msg, "type", None)
            if isinstance(msg, HumanMessage) or msg_type == "human":
                role = "user"
            elif isinstance(msg, AIMessage) or msg_type == "ai":
                tool_calls = getattr(msg, "tool_calls", None)
                invalid_tool_calls = getattr(msg, "invalid_tool_calls", None)
                additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}
                if not tool_calls and not invalid_tool_calls and not additional_kwargs.get("function_call"):
                    role = "assistant"

            if not role:
                continue

            raw_content = getattr(msg, "content", "")
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                text_parts = []
                for block in raw_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        text_parts.append(block.text)
                content = "\n".join(text_parts)
            else:
                content = str(raw_content)

            if not content or not content.strip():
                continue

            msg_key = (role, content)
            msg_id = getattr(msg, "id", None)

            if msg_id and msg_id in existing_ids:
                if existing_counts.get(msg_key, 0) > 0:
                    existing_counts[msg_key] -= 1
                continue

            if existing_counts.get(msg_key, 0) > 0:
                existing_counts[msg_key] -= 1
                continue

            mid = msg_id or f"legacy_{thread_id}_{idx}"
            saved = save_message(
                thread_id=thread_id,
                user_id=user_id,
                role=role,
                content=content,
                message_id=mid,
                strict=False,
                session=s,
            )
            if saved:
                backfilled.append(saved)
                existing_ids.add(saved["message_id"])

        return backfilled

    if active_s:
        return _backfill(active_s)
    with SessionLocal() as s:
        return _backfill(s)


def save_thread_summary(
    thread_id: str,
    summary: str,
    user_id: Optional[int] = None,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> bool:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Persist rolling conversation summary for a thread."""
    def _save(s) -> bool:
        query = s.query(Thread).filter(Thread.thread_id == thread_id)
        if user_id is not None:
            query = query.filter(Thread.user_id == user_id)
        thread = query.first()
        if not thread:
            if user_id is not None:
                raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")
            return False
        thread.summary = summary
        s.commit()
        return True

    if active_s:
        return _save(active_s)
    with SessionLocal() as s:
        return _save(s)


def get_thread_summary(
    thread_id: str,
    user_id: Optional[int] = None,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> Optional[str]:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Retrieve the latest persisted conversation summary for a thread."""
    def _get(s) -> Optional[str]:
        query = s.query(Thread.summary).filter(Thread.thread_id == thread_id)
        if user_id is not None:
            query = query.filter(Thread.user_id == user_id)
        row = query.first()
        return row[0] if row and row[0] is not None else None

    if active_s:
        return _get(active_s)
    with SessionLocal() as s:
        return _get(s)


def get_thread_messages(
    thread_id: str,
    user_id: int,
    limit: Optional[int] = None,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Retrieve messages for a specific thread in chronological order."""
    def _get(s) -> List[Dict[str, Any]]:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        query = s.query(Message).filter(
            Message.thread_id == thread_id,
            Message.user_id == user_id,
        )

        if limit is not None and limit > 0:
            subquery = (
                query.order_by(desc(Message.created_at))
                .limit(limit)
                .subquery()
            )
            # Re-order subquery results chronologically
            query = s.query(subquery).order_by(asc(subquery.c.created_at))
            rows = query.all()
            return [
                {
                    "message_id": r.message_id,
                    "thread_id": r.thread_id,
                    "user_id": r.user_id,
                    "role": r.role,
                    "content": r.content,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

        rows = query.order_by(asc(Message.created_at)).all()
        return [
            {
                "message_id": r.message_id,
                "thread_id": r.thread_id,
                "user_id": r.user_id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    if active_s:
        return _get(active_s)
    with SessionLocal() as s:
        return _get(s)


def retrieve_all_threads(
    user_id: int,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> List[str]:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Retrieve all stored conversation thread IDs for a user."""
    def _run(s) -> List[str]:
        rows = (
            s.query(Thread.thread_id)
            .filter(Thread.user_id == user_id)
            .order_by(desc(Thread.created_at))
            .all()
        )
        return [r[0] for r in rows]

    try:
        if active_s:
            return _run(active_s)
        with SessionLocal() as s:
            return _run(s)
    except Exception as e:
        logger.error(f"Failed to retrieve threads: {e}")
        return []


def thread_exists(thread_id: str) -> bool:
    """Check if a thread exists in the database or checkpointer."""
    try:
        with SessionLocal() as s:
            t = s.query(Thread.thread_id).filter(Thread.thread_id == thread_id).first()
            if t:
                return True
        for cp in checkpointer.list(None):
            if cp.config.get("configurable", {}).get("thread_id") == thread_id:
                return True
        return False
    except Exception as e:
        logger.error(f"Thread existence check failed: {e}")
        return False


def get_thread_title_db(
    thread_id: str,
    user_id: Optional[int] = None,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
) -> str:
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Retrieve title for a thread from the database."""
    def _run(s) -> str:
        q = s.query(Thread.title).filter(Thread.thread_id == thread_id)
        if user_id is not None:
            q = q.filter(Thread.user_id == user_id)
        row = q.first()
        if row and row[0]:
            return row[0]
        return f"Chat {thread_id[:6]}"

    try:
        if active_s:
            return _run(active_s)
        with SessionLocal() as s:
            return _run(s)
    except Exception as e:
        logger.error(f"Failed to get thread title: {e}")
        return f"Chat {thread_id[:6]}"


def save_thread_title(
    thread_id: str,
    user_id: int,
    title: str,
    session: Optional[Any] = None,
    target_conn: Optional[Any] = None,
):
    active_s = session or (target_conn if hasattr(target_conn, "query") else None)
    """Insert or update title of a thread."""
    def _run(s):
        thread = s.query(Thread).filter(Thread.thread_id == thread_id).first()
        if thread:
            thread.title = title
        else:
            thread = Thread(
                thread_id=thread_id,
                user_id=user_id,
                title=title,
                created_at=utc_now(),
            )
            s.add(thread)
        s.commit()

    try:
        if active_s:
            _run(active_s)
        else:
            with SessionLocal() as s:
                _run(s)
    except Exception as e:
        logger.error(f"Failed to save thread title: {e}")


def save_youtube_url(
    thread_id: str,
    youtube_url: str,
    session: Optional[Any] = None,
):
    """Save or update YouTube URL associated with a thread context."""
    def _run(s):
        ctx = s.query(ThreadContext).filter(ThreadContext.thread_id == thread_id).first()
        if ctx:
            ctx.youtube_url = youtube_url
        else:
            ctx = ThreadContext(
                thread_id=thread_id,
                youtube_url=youtube_url,
                created_at=utc_now(),
            )
            s.add(ctx)
        s.commit()
        logger.info(f"YouTube URL saved | thread={thread_id}")

    try:
        if session:
            _run(session)
        else:
            with SessionLocal() as s:
                _run(s)
    except Exception as e:
        logger.error(f"Failed to save YouTube URL: {e}")


def get_youtube_url(
    thread_id: str,
    session: Optional[Any] = None,
) -> Optional[str]:
    """Retrieve YouTube URL for a thread context."""
    def _run(s) -> Optional[str]:
        ctx = s.query(ThreadContext.youtube_url).filter(ThreadContext.thread_id == thread_id).first()
        return ctx[0] if ctx and ctx[0] else None

    try:
        if session:
            return _run(session)
        with SessionLocal() as s:
            return _run(s)
    except Exception as e:
        logger.error(f"Failed to fetch YouTube URL: {e}")
        return None


# =====================================================================
# MESSAGE EMBEDDINGS (PGVECTOR)
# =====================================================================

def save_message_embedding(
    message_id: str,
    thread_id: str,
    user_id: int,
    embedding: List[float],
    session: Optional[Any] = None,
) -> bool:
    """Store or update message embedding vector in pgvector."""
    def _save(s) -> bool:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        existing = s.query(MessageEmbedding).filter(MessageEmbedding.message_id == message_id).first()
        if existing:
            existing.embedding = embedding
        else:
            new_emb = MessageEmbedding(
                message_id=message_id,
                thread_id=thread_id,
                user_id=user_id,
                embedding=embedding,
                created_at=utc_now(),
            )
            s.add(new_emb)
        s.commit()
        return True

    try:
        if session:
            return _save(session)
        with SessionLocal() as s:
            return _save(s)
    except Exception as e:
        logger.error(f"Failed to save message embedding for '{message_id}': {e}")
        return False


def get_message_embeddings(
    thread_id: str,
    user_id: int,
    message_ids: Optional[List[str]] = None,
    session: Optional[Any] = None,
) -> Dict[str, List[float]]:
    """Retrieve stored message embeddings for a thread and user."""
    def _get(s) -> Dict[str, List[float]]:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        q = s.query(MessageEmbedding.message_id, MessageEmbedding.embedding).filter(
            MessageEmbedding.thread_id == thread_id,
            MessageEmbedding.user_id == user_id,
        )
        if message_ids is not None:
            if not message_ids:
                return {}
            q = q.filter(MessageEmbedding.message_id.in_(message_ids))

        rows = q.all()
        return {r[0]: list(r[1]) if r[1] is not None else [] for r in rows}

    try:
        if session:
            return _get(session)
        with SessionLocal() as s:
            return _get(s)
    except Exception as e:
        logger.error(f"Failed to fetch message embeddings: {e}")
        return {}


def get_unembedded_messages(
    thread_id: str,
    user_id: int,
    limit: Optional[int] = None,
    session: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Retrieve messages in a thread that do not yet have an embedding stored."""
    def _get(s) -> List[Dict[str, Any]]:
        if not verify_thread_ownership(thread_id, user_id, session=s):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

        q = (
            s.query(Message)
            .outerjoin(MessageEmbedding, Message.message_id == MessageEmbedding.message_id)
            .filter(
                Message.thread_id == thread_id,
                Message.user_id == user_id,
                MessageEmbedding.message_id.is_(None),
            )
            .order_by(asc(Message.created_at))
        )
        if limit is not None and limit > 0:
            q = q.limit(limit)

        rows = q.all()
        return [
            {
                "message_id": r.message_id,
                "thread_id": r.thread_id,
                "user_id": r.user_id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    try:
        if session:
            return _get(session)
        with SessionLocal() as s:
            return _get(s)
    except Exception as e:
        logger.error(f"Failed to fetch unembedded messages: {e}")
        return []
