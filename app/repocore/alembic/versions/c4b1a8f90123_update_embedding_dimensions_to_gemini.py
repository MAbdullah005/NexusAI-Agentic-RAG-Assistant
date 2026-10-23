"""update embedding dimensions to 768 for Google Gemini

Revision ID: c4b1a8f90123
Revises: e7c3d91a2b4f
Create Date: 2026-10-23 01:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4b1a8f90123'
down_revision: Union[str, Sequence[str], None] = 'e7c3d91a2b4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing HNSW index before changing vector dimension
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    # Alter vector column to vector(768)
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(768)")
    # Recreate HNSW index with cosine distance ops
    op.execute("CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384)")
    op.execute("CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)")

