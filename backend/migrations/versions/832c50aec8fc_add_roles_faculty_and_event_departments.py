"""add roles, faculty and event departments

Revision ID: 832c50aec8fc
Revises: d951269155d5
Create Date: 2026-10-15 19:30:26.644174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '832c50aec8fc'
down_revision: Union[str, Sequence[str], None] = 'd951269155d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('faculty',
    sa.Column('faculty_id', sa.String(length=20), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('department', sa.String(length=100), nullable=False),
    sa.Column('office', sa.String(length=100), nullable=True),
    sa.Column('office_hours', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_faculty_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('faculty_id', name=op.f('pk_faculty')),
    sa.UniqueConstraint('user_id', name=op.f('uq_faculty_user_id'))
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department', sa.String(length=100), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), server_default='student', nullable=False))
        # Added empty, filled from the roster below, then made required.
        batch_op.add_column(sa.Column('name', sa.String(length=100), nullable=True))
        batch_op.alter_column('student_id', existing_type=sa.VARCHAR(length=10), nullable=True)

    op.execute(
        "UPDATE users SET name = "
        "(SELECT students.name FROM students WHERE students.student_id = users.student_id)"
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('name', existing_type=sa.String(length=100), nullable=False)
        batch_op.create_check_constraint(
            op.f('ck_users_valid_role'),
            "role IN ('student', 'faculty', 'staff', 'admin')",
        )
        batch_op.create_check_constraint(
            op.f('ck_users_student_link'),
            "(role = 'student' AND student_id IS NOT NULL) "
            "OR (role <> 'student' AND student_id IS NULL)",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_users_student_link'), type_='check')
        batch_op.drop_constraint(op.f('ck_users_valid_role'), type_='check')

    # Faculty, staff and admin accounts have no student record, which the old
    # schema cannot hold, so they are removed.
    op.execute("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE student_id IS NULL)")
    op.execute("DELETE FROM faculty")
    op.execute("DELETE FROM users WHERE student_id IS NULL")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('student_id', existing_type=sa.VARCHAR(length=10), nullable=False)
        batch_op.drop_column('name')
        batch_op.drop_column('role')

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('department')

    op.drop_table('faculty')
