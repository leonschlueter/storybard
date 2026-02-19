<%text>
Revision ID: ${rev_id}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

</%text>
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = ${repr(rev_id)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade():
    pass

def downgrade():
    pass
