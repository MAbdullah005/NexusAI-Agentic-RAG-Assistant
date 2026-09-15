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
from typing import List
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


def init_db():
    cursor = conn.cursor()

    #user 
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # 🔥 DOCUMENTS TABLE (MISSING)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS  documents (
    doc_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type TEXT,
    content_hash TEXT NOT NULL,
    source TEXT,
    filename TEXT,
    vectorstore_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
        REFERENCES users(user_id)
)
"""
)
    # 🔥 RELATION TABLE (MISSING)
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

    # for email verfication 

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

    conn.commit()


# Thread Utilities

def retrieve_all_threads(user_id:int) -> List[str]:
    """
    Retrieve all stored conversation thread IDs.

    Returns
    -------
    List[str]get_thread_title_db
        List of thread IDs.
    """

    logger.info("Retrieving all conversation threads")

    try:

      cursor = conn.cursor()
      cursor.execute(f"SELECT thread_id FROM threads WHERE user_id={user_id} ORDER BY created_at DESC")
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





def get_thread_title_db(thread_id: str) -> str:
    try:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT title FROM threads WHERE thread_id=?
        """, (thread_id,))

        row = cursor.fetchone()

        if row and row[0]:
            return row[0]

        return f"Chat {thread_id[:6]}"

    except Exception as e:
        logger.error(f"Failed to get thread title: {str(e)}")
        return f"Chat {thread_id[:6]}"


def save_thread_title(thread_id: str,user_id:int, title: str):
    try:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO threads (thread_id,user_id,title)
        VALUES (?, ?,?)
        ON CONFLICT(thread_id)
        DO UPDATE SET title=excluded.title
        """, (thread_id,user_id, title))

        conn.commit()

    except Exception as e:
        logger.error(f"Failed to save thread title: {str(e)}")




def save_youtube_url(thread_id: str, youtube_url: str):
    try:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO thread_context (thread_id, youtube_url)
        VALUES (?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET youtube_url=excluded.youtube_url
        """, (thread_id, youtube_url))

        conn.commit()

        logger.info(f"YouTube URL saved | thread={thread_id}")

    except Exception as e:
        logger.error(f"Failed to save YouTube URL: {str(e)}")

    
def get_youtube_url(thread_id: str) -> str:
    try:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT youtube_url FROM thread_context WHERE thread_id=?
        """, (thread_id,))

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    except Exception as e:
        logger.error(f"Failed to fetch YouTube URL: {str(e)}")
        return None
    

init_db()