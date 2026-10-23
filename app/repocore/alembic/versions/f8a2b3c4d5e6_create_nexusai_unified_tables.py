"""create nexusai unified tables

Revision ID: f8a2b3c4d5e6
Revises: c4b1a8f90123
Create Date: 2026-10-23 02:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'f8a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'c4b1a8f90123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Update users table with email and is_verified
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
    op.execute("UPDATE users SET email = username || '@repoguide.local' WHERE email IS NULL;")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email);")

    # 3. Handle messages table disambiguation:
    # If messages table exists and has conversation_id (RepoCore's old messages table),
    # rename it to repo_messages so messages can be used for NexusAI threads.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'messages' AND column_name = 'conversation_id'
        ) THEN
            ALTER TABLE messages RENAME TO repo_messages;
        END IF;
    END
    $$;
    """)

    # 4. Create threads table
    op.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id VARCHAR(100) PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255),
        summary TEXT,
        checkpoint_synced BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_threads_user_created ON threads(user_id, created_at DESC);
    """)

    # 5. Create thread_context table
    op.execute("""
    CREATE TABLE IF NOT EXISTS thread_context (
        thread_id VARCHAR(100) PRIMARY KEY REFERENCES threads(thread_id) ON DELETE CASCADE,
        youtube_url TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # 6. Create documents table
    op.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        doc_id VARCHAR(100) PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type VARCHAR(50),
        content_hash VARCHAR(128) DEFAULT '',
        source TEXT,
        filename TEXT,
        vectorstore_path TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
    """)

    # 7. Create thread_documents table
    op.execute("""
    CREATE TABLE IF NOT EXISTS thread_documents (
        thread_id VARCHAR(100) REFERENCES threads(thread_id) ON DELETE CASCADE,
        doc_id VARCHAR(100) REFERENCES documents(doc_id) ON DELETE CASCADE,
        PRIMARY KEY (thread_id, doc_id)
    );
    """)

    # 8. Create messages table (NexusAI threads)
    op.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id VARCHAR(100) PRIMARY KEY,
        thread_id VARCHAR(100) NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON messages(thread_id, created_at ASC);
    CREATE INDEX IF NOT EXISTS idx_messages_user_thread ON messages(user_id, thread_id);
    """)

    # 9. Create message_embeddings table (with pgvector 768)
    op.execute("""
    CREATE TABLE IF NOT EXISTS message_embeddings (
        message_id VARCHAR(100) PRIMARY KEY REFERENCES messages(message_id) ON DELETE CASCADE,
        thread_id VARCHAR(100) NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        embedding vector(768) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_msg_embed_thread_user ON message_embeddings(thread_id, user_id);
    """)

    # 10. Create password_resets table
    op.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(128) UNIQUE NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_pwd_resets_user_id ON password_resets(user_id);
    """)

    # 11. Create email_verifications table
    op.execute("""
    CREATE TABLE IF NOT EXISTS email_verifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(128) UNIQUE NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_email_verif_user_id ON email_verifications(user_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_verifications;")
    op.execute("DROP TABLE IF EXISTS password_resets;")
    op.execute("DROP TABLE IF EXISTS message_embeddings;")
    op.execute("DROP TABLE IF EXISTS messages;")
    op.execute("DROP TABLE IF EXISTS thread_documents;")
    op.execute("DROP TABLE IF EXISTS documents;")
    op.execute("DROP TABLE IF EXISTS thread_context;")
    op.execute("DROP TABLE IF EXISTS threads;")

