"""add full-text search column + GIN index on chunks

Revision ID: e7c3d91a2b4f
Revises: df181132cd96
Create Date: 2026-09-11 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c3d91a2b4f'
down_revision: Union[str, Sequence[str], None] = 'df181132cd96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE chunks ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', file_path), 'A')
            || setweight(to_tsvector('english', content), 'B')
        ) STORED
    """)
    op.execute("CREATE INDEX idx_chunks_search_tsv ON chunks USING GIN (search_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_search_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS search_tsv")