"""memory embedding

Revision ID: 3474be29cf67
Revises: 579b46e28a74
Create Date: 2026-09-30 17:19:57.651161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '3474be29cf67'
down_revision: Union[str, Sequence[str], None] = '579b46e28a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector/pgvector:pg16 ships the extension but doesn't enable it per-database —
    # confirmed via a direct pg_extension query against this DB before writing this
    # migration (only plpgsql was present).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column('memories', sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=768), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('memories', 'embedding')
