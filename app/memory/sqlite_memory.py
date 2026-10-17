"""
SQLite Memory Store

Handles persistent conversation memory for the LangGraph agent
using SqliteSaver.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


import os
import sqlite3
import uuid
import struct
try:
    import numpy as np
except ImportError:
    np = None
from typing import List, Optional, Dict, Any, Union
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Database Setup

DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "chatbot_conv.db")

os.makedirs(DB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")

checkpointer = SqliteSaver(conn=conn)

logger.info(f"SQLite memory initialized | db={DB_PATH}")


def init_db(target_conn=None):
    db = target_conn or conn
    db.execute("PRAGMA foreign_keys = ON")
    cursor = db.cursor()

    # user 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
     user_id INTEGER PRIMARY KEY AUTOINCREMENT,
     email TEXT UNIQUE NOT NULL,
     password_hash TEXT NOT NULL,
     is_verified BOOLEAN DEFAULT 0,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    """)

    # THREADS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT,
        summary TEXT,
        checkpoint_synced BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # Idempotent migration: ensure threads table has summary and checkpoint_synced columns
    cursor.execute("PRAGMA table_info(threads)")
    columns = [col[1] for col in cursor.fetchall()]
    if "summary" not in columns:
        cursor.execute("ALTER TABLE threads ADD COLUMN summary TEXT")
        logger.info("Migrated threads table: added summary column")
    if "checkpoint_synced" not in columns:
        cursor.execute("ALTER TABLE threads ADD COLUMN checkpoint_synced BOOLEAN DEFAULT 0")
        logger.info("Migrated threads table: added checkpoint_synced column")

    # DOCUMENTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        type TEXT,
        content_hash TEXT NOT NULL,
        source TEXT,
        filename TEXT,
        vectorstore_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # RELATION TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS thread_documents (
        thread_id TEXT,
        doc_id TEXT,
        PRIMARY KEY (thread_id, doc_id),
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id),
        FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS thread_context (
        thread_id TEXT PRIMARY KEY,
        youtube_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
    )
    """)

    # for rest-password table 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # for email verification 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # DURABLE MESSAGES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    # INDEXES FOR CHRONOLOGICAL RETRIEVAL & ISOLATION
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_thread_created
    ON messages(thread_id, created_at ASC)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_user_thread
    ON messages(user_id, thread_id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_threads_user_created
    ON threads(user_id, created_at DESC)
    """)

    # MESSAGE EMBEDDINGS CACHE TABLE FOR SEMANTIC RETRIEVAL
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_embeddings (
        message_id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        embedding BLOB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(message_id) REFERENCES messages(message_id) ON DELETE CASCADE,
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_msg_embed_thread_user
    ON message_embeddings(thread_id, user_id)
    """)

    db.commit()


# Thread & Message Utilities

def verify_thread_ownership(
    thread_id: str,
    user_id: int,
    target_conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Validate whether a thread exists and belongs to the given user.
    """
    db = target_conn or conn
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT 1 FROM threads WHERE thread_id = ? AND user_id = ?",
            (thread_id, user_id)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Thread ownership check failed: {str(e)}")
        return False


def save_message(
    thread_id: str,
    user_id: int,
    role: str,
    content: str,
    message_id: Optional[str] = None,
    strict: bool = False,
    target_conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """
    Save a visible chat message to durable SQLite storage.
    Validates that the thread exists and is owned by user_id.
    Prevents duplicate insertion if message_id already exists.
    If strict=True, raises ValueError if an existing message_id has conflicting content.
    Always raises ValueError if an existing message_id belongs to a different thread, user, or role.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role: '{role}'. Must be 'user' or 'assistant'.")

    db = target_conn or conn
    cursor = db.cursor()

    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    mid = message_id or str(uuid.uuid4())

    # Check for existing message with this ID to verify idempotency / conflicts
    cursor.execute(
        """
        SELECT message_id, thread_id, user_id, role, content, created_at
        FROM messages
        WHERE message_id = ?
        """,
        (mid,)
    )
    existing = cursor.fetchone()
    if existing:
        if existing[1] != thread_id or existing[2] != user_id or existing[3] != role:
            raise ValueError(
                f"Message ID '{mid}' already exists with conflicting thread, user, or role."
            )
        if existing[4] != content:
            if strict:
                raise ValueError(
                    f"Message ID '{mid}' already exists with conflicting content."
                )
            logger.warning(
                f"Reused message_id '{mid}' with different content; preserving original content."
            )
        return {
            "message_id": existing[0],
            "thread_id": existing[1],
            "user_id": existing[2],
            "role": existing[3],
            "content": existing[4],
            "created_at": existing[5]
        }

    try:
        cursor.execute(
            """
            INSERT INTO messages (
                message_id,
                thread_id,
                user_id,
                role,
                content
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                mid,
                thread_id,
                user_id,
                role,
                content
            )
        )
        db.commit()
    except sqlite3.IntegrityError:
        cursor.execute(
            """
            SELECT message_id, thread_id, user_id, role, content, created_at
            FROM messages
            WHERE message_id = ?
            """,
            (mid,)
        )
        existing = cursor.fetchone()
        if existing:
            if existing[1] != thread_id or existing[2] != user_id or existing[3] != role:
                raise ValueError(
                    f"Message ID '{mid}' already exists with conflicting thread, user, or role."
                )
            if existing[4] != content and strict:
                raise ValueError(
                    f"Message ID '{mid}' already exists with conflicting content."
                )
            return {
                "message_id": existing[0],
                "thread_id": existing[1],
                "user_id": existing[2],
                "role": existing[3],
                "content": existing[4],
                "created_at": existing[5]
            }
        raise

    cursor.execute(
        """
        SELECT message_id, thread_id, user_id, role, content, created_at
        FROM messages
        WHERE message_id = ?
        """,
        (mid,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "message_id": row[0],
            "thread_id": row[1],
            "user_id": row[2],
            "role": row[3],
            "content": row[4],
            "created_at": row[5]
        }
    return None


def backfill_thread_messages_from_checkpoint(
    thread_id: str,
    user_id: int,
    checkpoint_messages: List[Any],
    target_conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Backfill legacy or missing thread messages from LangGraph checkpoint into durable messages table.
    Filters out internal tool messages, tool calls, and system messages.
    Safely accounts for messages that already exist in SQLite to prevent duplicate writes
    even when some messages are already stored.
    """
    db = target_conn or conn
    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    # Fetch existing messages from SQLite for this thread
    existing_messages = get_thread_messages(thread_id, user_id, target_conn=db)
    existing_ids = {m["message_id"] for m in existing_messages}

    # Count existing (role, content) pairs in SQLite to accurately match against checkpoint turns
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

        # If this exact message ID is already in SQLite, decrement available count and skip
        if msg_id and msg_id in existing_ids:
            if existing_counts.get(msg_key, 0) > 0:
                existing_counts[msg_key] -= 1
            continue

        # If an existing SQLite record already accounts for this (role, content) turn, skip
        if existing_counts.get(msg_key, 0) > 0:
            existing_counts[msg_key] -= 1
            continue

        # This checkpoint message is genuinely missing from SQLite; persist it
        mid = msg_id or f"legacy_{thread_id}_{idx}"
        saved = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role=role,
            content=content,
            message_id=mid,
            strict=False,
            target_conn=db
        )
        if saved:
            backfilled.append(saved)
            existing_ids.add(saved["message_id"])

    return backfilled


def save_thread_summary(
    thread_id: str,
    summary: str,
    user_id: Optional[int] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Persist the rolling conversation summary for a thread.
    If user_id is provided, validates that the thread belongs to that user.
    """
    db = target_conn or conn
    cursor = db.cursor()
    if user_id is not None:
        if not verify_thread_ownership(thread_id, user_id, target_conn=db):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")
        cursor.execute(
            """
            UPDATE threads
            SET summary = ?
            WHERE thread_id = ? AND user_id = ?
            """,
            (summary, thread_id, user_id)
        )
    else:
        cursor.execute(
            """
            UPDATE threads
            SET summary = ?
            WHERE thread_id = ?
            """,
            (summary, thread_id)
        )
    db.commit()
    return cursor.rowcount > 0


def get_thread_summary(
    thread_id: str,
    user_id: Optional[int] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> Optional[str]:
    """
    Retrieve the latest persisted conversation summary for a thread.
    If user_id is provided, validates that the thread belongs to that user.
    """
    db = target_conn or conn
    cursor = db.cursor()
    if user_id is not None:
        if not verify_thread_ownership(thread_id, user_id, target_conn=db):
            raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")
        cursor.execute(
            """
            SELECT summary
            FROM threads
            WHERE thread_id = ? AND user_id = ?
            """,
            (thread_id, user_id)
        )
    else:
        cursor.execute(
            """
            SELECT summary
            FROM threads
            WHERE thread_id = ?
            """,
            (thread_id,)
        )
    row = cursor.fetchone()
    return row[0] if row and row[0] is not None else None


def get_thread_messages(
    thread_id: str,
    user_id: int,
    limit: Optional[int] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve messages for a specific thread and authenticated user in chronological order.
    Validates that the thread belongs to user_id.
    """
    db = target_conn or conn
    cursor = db.cursor()

    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    if limit is not None and limit > 0:
        query = """
        SELECT message_id, thread_id, user_id, role, content, created_at
        FROM (
            SELECT message_id, thread_id, user_id, role, content, created_at, rowid
            FROM messages
            WHERE thread_id = ? AND user_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
        )
        ORDER BY created_at ASC, rowid ASC
        """
        cursor.execute(query, (thread_id, user_id, limit))
    else:
        query = """
        SELECT message_id, thread_id, user_id, role, content, created_at
        FROM messages
        WHERE thread_id = ? AND user_id = ?
        ORDER BY created_at ASC, rowid ASC
        """
        cursor.execute(query, (thread_id, user_id))

    rows = cursor.fetchall()
    return [
        {
            "message_id": r[0],
            "thread_id": r[1],
            "user_id": r[2],
            "role": r[3],
            "content": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]


def retrieve_all_threads(user_id: int, target_conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """
    Retrieve all stored conversation thread IDs for a user.
    """
    logger.info("Retrieving all conversation threads")
    db = target_conn or conn
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT thread_id FROM threads WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Failed to retrieve threads: {str(e)}")
        return []


def thread_exists(thread_id: str) -> bool:
    """
    Check if a thread exists in memory.
    """
    try:
        for checkpoint in checkpointer.list(None):
            if checkpoint.config.get("configurable", {}).get("thread_id") == thread_id:
                return True
        return False
    except Exception as e:
        conn.rollback()
        logger.error(f"Thread existence check failed: {str(e)}")
        return False


def get_thread_title_db(
    thread_id: str,
    user_id: Optional[int] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> str:
    db = target_conn or conn
    try:
        cursor = db.cursor()
        if user_id is not None:
            cursor.execute(
                "SELECT title FROM threads WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id)
            )
        else:
            cursor.execute(
                "SELECT title FROM threads WHERE thread_id = ?",
                (thread_id,)
            )

        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return f"Chat {thread_id[:6]}"
    except Exception as e:
        logger.error(f"Failed to get thread title: {str(e)}")
        return f"Chat {thread_id[:6]}"


def save_thread_title(
    thread_id: str,
    user_id: int,
    title: str,
    target_conn: Optional[sqlite3.Connection] = None
):
    db = target_conn or conn
    try:
        cursor = db.cursor()
        cursor.execute("""
        INSERT INTO threads (thread_id, user_id, title)
        VALUES (?, ?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET title = excluded.title
        """, (thread_id, user_id, title))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save thread title: {str(e)}")


def save_youtube_url(
    thread_id: str,
    youtube_url: str,
    target_conn: Optional[sqlite3.Connection] = None
):
    db = target_conn or conn
    try:
        cursor = db.cursor()
        cursor.execute("""
        INSERT INTO thread_context (thread_id, youtube_url)
        VALUES (?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET youtube_url = excluded.youtube_url
        """, (thread_id, youtube_url))
        db.commit()
        logger.info(f"YouTube URL saved | thread={thread_id}")
    except Exception as e:
        logger.error(f"Failed to save YouTube URL: {str(e)}")


def get_youtube_url(
    thread_id: str,
    target_conn: Optional[sqlite3.Connection] = None
) -> Optional[str]:
    db = target_conn or conn
    try:
        cursor = db.cursor()
        cursor.execute("""
        SELECT youtube_url FROM thread_context WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Failed to fetch YouTube URL: {str(e)}")
        return None


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


def save_message_embedding(
    message_id: str,
    thread_id: str,
    user_id: int,
    embedding: List[float],
    target_conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Store or update a message embedding vector in SQLite.
    Validates that thread ownership belongs to user_id.
    """
    db = target_conn or conn
    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    blob = serialize_embedding(embedding)
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO message_embeddings (
                message_id,
                thread_id,
                user_id,
                embedding
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id)
            DO UPDATE SET embedding = excluded.embedding
            """,
            (message_id, thread_id, user_id, blob)
        )
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save message embedding for '{message_id}': {e}")
        return False


def get_message_embeddings(
    thread_id: str,
    user_id: int,
    message_ids: Optional[List[str]] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> Dict[str, List[float]]:
    """
    Retrieve stored message embeddings for a specific thread and authenticated user.
    Returns mapping from message_id to float embedding vector.
    Enforces thread ownership and user isolation.
    """
    db = target_conn or conn
    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    cursor = db.cursor()
    if message_ids is not None:
        if not message_ids:
            return {}
        placeholders = ",".join("?" for _ in message_ids)
        cursor.execute(
            f"""
            SELECT message_id, embedding
            FROM message_embeddings
            WHERE thread_id = ? AND user_id = ? AND message_id IN ({placeholders})
            """,
            [thread_id, user_id, *message_ids]
        )
    else:
        cursor.execute(
            """
            SELECT message_id, embedding
            FROM message_embeddings
            WHERE thread_id = ? AND user_id = ?
            """,
            (thread_id, user_id)
        )

    rows = cursor.fetchall()
    result = {}
    for mid, blob in rows:
        try:
            result[mid] = deserialize_embedding(blob)
        except Exception as e:
            logger.warning(f"Failed to deserialize embedding for message '{mid}': {e}")
    return result


def get_unembedded_messages(
    thread_id: str,
    user_id: int,
    limit: Optional[int] = None,
    target_conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve messages in a thread that do not yet have an embedding stored.
    Enforces thread ownership and user isolation.
    """
    db = target_conn or conn
    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        raise ValueError(f"Thread '{thread_id}' not found or access denied for user {user_id}")

    cursor = db.cursor()
    query = """
    SELECT m.message_id, m.thread_id, m.user_id, m.role, m.content, m.created_at
    FROM messages m
    LEFT JOIN message_embeddings me
        ON m.message_id = me.message_id
    WHERE m.thread_id = ? AND m.user_id = ? AND me.message_id IS NULL
    ORDER BY m.created_at ASC
    """
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        cursor.execute(query, (thread_id, user_id, limit))
    else:
        cursor.execute(query, (thread_id, user_id))

    rows = cursor.fetchall()
    return [
        {
            "message_id": r[0],
            "thread_id": r[1],
            "user_id": r[2],
            "role": r[3],
            "content": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]


init_db()