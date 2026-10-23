"""add pgvector chunks table

Revision ID: df181132cd96
Revises: d5bf5270848c
Create Date: 2026-09-10 14:08:27.300289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df181132cd96'
down_revision: Union[str, Sequence[str], None] = 'd5bf5270848c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE chunks (
            id SERIAL PRIMARY KEY,
            owner VARCHAR(100) NOT NULL,
            repo VARCHAR(100) NOT NULL,
            commit_sha VARCHAR(40) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            language VARCHAR(50),
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(384) NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_chunks_owner_repo ON chunks (owner, repo)")
    op.execute("CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
