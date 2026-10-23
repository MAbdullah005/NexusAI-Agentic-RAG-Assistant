"""
NexusAI Data Migration: SQLite -> PostgreSQL

Safely migrates all persisted application data from SQLite (database/chatbot_conv.db)
to PostgreSQL without data loss or destructiveness.

Usage:
    python scripts/migrate_sqlite_to_postgres.py [--db-url postgresql://user:password@localhost:5432/nexusai]
"""
import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime, timezone
from typing import Optional, List

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    User,
    PasswordReset,
    EmailVerification,
    Thread,
    ThreadContext,
    Document,
    ThreadDocument,
    Message,
    MessageEmbedding,
    utc_now,
)
from app.db.session import get_database_urls
from app.memory.postgres_memory import deserialize_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")


def parse_datetime(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return utc_now()


def migrate_sqlite_to_postgres(sqlite_path: str, postgres_url: Optional[str] = None):
    if not os.path.exists(sqlite_path):
        logger.info(f"SQLite database file not found at {sqlite_path}. Nothing to migrate.")
        return

    sync_url = postgres_url
    if not sync_url:
        sync_url, _ = get_database_urls()

    logger.info(f"Connecting to SQLite: {sqlite_path}")
    sq_conn = sqlite3.connect(sqlite_path)
    sq_cur = sq_conn.cursor()

    logger.info("Connecting to PostgreSQL...")
    engine = create_engine(sync_url)

    # 1. Enable pgvector and create tables
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    stats = {
        "users": 0,
        "password_resets": 0,
        "email_verifications": 0,
        "threads": 0,
        "thread_context": 0,
        "documents": 0,
        "thread_documents": 0,
        "messages": 0,
        "message_embeddings": 0,
    }

    try:
        # ============================================================
        # 1. USERS
        # ============================================================
        try:
            sq_cur.execute("SELECT user_id, email, password_hash, is_verified, created_at FROM users")
            rows = sq_cur.fetchall()
            for r in rows:
                uid, email, pwd_hash, is_ver, created_at = r
                existing = db.query(User).filter((User.id == uid) | (User.email == email)).first()
                if not existing:
                    user = User(
                        id=uid,
                        email=email,
                        username=email.split("@")[0],
                        password_hash=pwd_hash,
                        is_verified=bool(is_ver),
                        created_at=parse_datetime(created_at),
                    )
                    db.add(user)
                    stats["users"] += 1
            db.commit()

            # Fix Postgres auto-increment sequence for users
            with engine.connect() as conn:
                conn.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1)) FROM users;"))
                conn.commit()
        except sqlite3.OperationalError:
            logger.info("Table 'users' not present in SQLite; skipping.")

        # ============================================================
        # 2. PASSWORD RESETS
        # ============================================================
        try:
            sq_cur.execute("SELECT id, user_id, token_hash, expires_at, created_at FROM password_resets")
            rows = sq_cur.fetchall()
            for r in rows:
                rid, uid, thash, exp, cat = r
                existing = db.query(PasswordReset).filter(PasswordReset.token_hash == thash).first()
                if not existing:
                    pr = PasswordReset(
                        id=rid,
                        user_id=uid,
                        token_hash=thash,
                        expires_at=parse_datetime(exp),
                        created_at=parse_datetime(cat),
                    )
                    db.add(pr)
                    stats["password_resets"] += 1
            db.commit()

            with engine.connect() as conn:
                conn.execute(text("SELECT setval(pg_get_serial_sequence('password_resets', 'id'), COALESCE(MAX(id), 1)) FROM password_resets;"))
                conn.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 3. EMAIL VERIFICATIONS
        # ============================================================
        try:
            sq_cur.execute("SELECT id, user_id, token_hash, expires_at, created_at FROM email_verifications")
            rows = sq_cur.fetchall()
            for r in rows:
                vid, uid, thash, exp, cat = r
                existing = db.query(EmailVerification).filter(EmailVerification.token_hash == thash).first()
                if not existing:
                    ev = EmailVerification(
                        id=vid,
                        user_id=uid,
                        token_hash=thash,
                        expires_at=parse_datetime(exp),
                        created_at=parse_datetime(cat),
                    )
                    db.add(ev)
                    stats["email_verifications"] += 1
            db.commit()

            with engine.connect() as conn:
                conn.execute(text("SELECT setval(pg_get_serial_sequence('email_verifications', 'id'), COALESCE(MAX(id), 1)) FROM email_verifications;"))
                conn.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 4. THREADS
        # ============================================================
        try:
            sq_cur.execute("SELECT thread_id, user_id, title, summary, checkpoint_synced, created_at FROM threads")
            rows = sq_cur.fetchall()
            for r in rows:
                tid, uid, title, summary, syn, cat = r
                existing = db.query(Thread).filter(Thread.thread_id == tid).first()
                if not existing:
                    t = Thread(
                        thread_id=tid,
                        user_id=uid,
                        title=title,
                        summary=summary,
                        checkpoint_synced=bool(syn),
                        created_at=parse_datetime(cat),
                    )
                    db.add(t)
                    stats["threads"] += 1
            db.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 5. THREAD CONTEXT
        # ============================================================
        try:
            sq_cur.execute("SELECT thread_id, youtube_url, created_at FROM thread_context")
            rows = sq_cur.fetchall()
            for r in rows:
                tid, yurl, cat = r
                existing = db.query(ThreadContext).filter(ThreadContext.thread_id == tid).first()
                if not existing:
                    tc = ThreadContext(
                        thread_id=tid,
                        youtube_url=yurl,
                        created_at=parse_datetime(cat),
                    )
                    db.add(tc)
                    stats["thread_context"] += 1
            db.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 6. DOCUMENTS
        # ============================================================
        try:
            sq_cur.execute("SELECT doc_id, user_id, type, content_hash, source, filename, vectorstore_path, created_at FROM documents")
            rows = sq_cur.fetchall()
            for r in rows:
                did, uid, dtype, chash, src, fn, vpath, cat = r
                existing = db.query(Document).filter(Document.doc_id == did).first()
                if not existing:
                    doc = Document(
                        doc_id=did,
                        user_id=uid,
                        type=dtype,
                        content_hash=chash or "",
                        source=src,
                        filename=fn,
                        vectorstore_path=vpath,
                        created_at=parse_datetime(cat),
                    )
                    db.add(doc)
                    stats["documents"] += 1
            db.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 7. THREAD DOCUMENTS
        # ============================================================
        try:
            sq_cur.execute("SELECT thread_id, doc_id FROM thread_documents")
            rows = sq_cur.fetchall()
            for r in rows:
                tid, did = r
                existing = db.query(ThreadDocument).filter(
                    ThreadDocument.thread_id == tid,
                    ThreadDocument.doc_id == did,
                ).first()
                if not existing:
                    td = ThreadDocument(thread_id=tid, doc_id=did)
                    db.add(td)
                    stats["thread_documents"] += 1
            db.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 8. MESSAGES
        # ============================================================
        try:
            sq_cur.execute("SELECT message_id, thread_id, user_id, role, content, created_at FROM messages")
            rows = sq_cur.fetchall()
            for r in rows:
                mid, tid, uid, role, content, cat = r
                existing = db.query(Message).filter(Message.message_id == mid).first()
                if not existing:
                    m = Message(
                        message_id=mid,
                        thread_id=tid,
                        user_id=uid,
                        role=role,
                        content=content,
                        created_at=parse_datetime(cat),
                    )
                    db.add(m)
                    stats["messages"] += 1
            db.commit()
        except sqlite3.OperationalError:
            pass

        # ============================================================
        # 9. MESSAGE EMBEDDINGS (pgvector conversion)
        # ============================================================
        try:
            sq_cur.execute("SELECT message_id, thread_id, user_id, embedding, created_at FROM message_embeddings")
            rows = sq_cur.fetchall()
            for r in rows:
                mid, tid, uid, blob, cat = r
                existing = db.query(MessageEmbedding).filter(MessageEmbedding.message_id == mid).first()
                if not existing:
                    vec = deserialize_embedding(blob)
                    # Verify dimensions (Gemini embedding dimensions = 768)
                    if len(vec) == 768:
                        me = MessageEmbedding(
                            message_id=mid,
                            thread_id=tid,
                            user_id=uid,
                            embedding=vec,
                            created_at=parse_datetime(cat),
                        )
                        db.add(me)
                        stats["message_embeddings"] += 1
                    else:
                        logger.warning(
                            f"Skipping message embedding {mid}: dimension {len(vec)} != 768. "
                            f"Will be re-embedded dynamically by historical retriever."
                        )
            db.commit()
        except sqlite3.OperationalError:
            pass

        logger.info("=" * 60)
        logger.info("SQLite to PostgreSQL Migration Complete:")
        for tbl, count in stats.items():
            logger.info(f"  - {tbl}: {count} records migrated")
        logger.info("=" * 60)
        logger.info("SQLite database file remains intact at: " + sqlite_path)

    except Exception as e:
        db.rollback()
        logger.error(f"Migration error: {e}", exc_info=True)
        raise
    finally:
        db.close()
        sq_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate NexusAI SQLite database to PostgreSQL.")
    parser.add_argument("--sqlite-path", default="database/chatbot_conv.db", help="Path to SQLite database")
    parser.add_argument("--db-url", default=None, help="PostgreSQL connection string (sync driver)")
    args = parser.parse_args()

    migrate_sqlite_to_postgres(sqlite_path=args.sqlite_path, postgres_url=args.db_url)

