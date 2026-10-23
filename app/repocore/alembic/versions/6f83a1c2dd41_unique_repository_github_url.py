"""make github_url unique

Revision ID: 6f83a1c2dd41
Revises: 5a91aeca01ba
Create Date: 2026-09-05 10:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6f83a1c2dd41'
down_revision: Union[str, Sequence[str], None] = '5a91aeca01ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # remove duplicate urls, keeping the earliest row (lowest id)
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("""
            DELETE FROM repositories a
            USING repositories b
            WHERE a.github_url = b.github_url AND a.id > b.id
        """))
    elif conn.dialect.name == "sqlite":
        conn.execute(sa.text("""
            DELETE FROM repositories
            WHERE id NOT IN (
                SELECT MIN(id) FROM repositories GROUP BY github_url
            )
        """))

    op.create_index(op.f('ix_repositories_github_url'), 'repositories', ['github_url'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_repositories_github_url'), table_name='repositories')