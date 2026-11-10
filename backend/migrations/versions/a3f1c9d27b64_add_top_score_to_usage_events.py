"""add top score to usage events

Revision ID: a3f1c9d27b64
Revises: 7eb7356d1e68
Create Date: 2026-11-10 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d27b64'
down_revision: Union[str, Sequence[str], None] = '7eb7356d1e68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('top_score', sa.Double(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.drop_column('top_score')
