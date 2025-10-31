"""initial schema

Revision ID: 20251031_000001
Revises: 
Create Date: 2025-10-31 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251031_000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop tables if they exist
    op.execute("DROP INDEX IF EXISTS ix_tasks_user_id ON tasks;")
    op.execute("DROP INDEX IF EXISTS ix_tasks_id ON tasks;")
    op.execute("DROP INDEX IF EXISTS ix_journals_user_id ON journals;")
    op.execute("DROP INDEX IF EXISTS ix_journals_id ON journals;")
    op.execute("DROP TABLE IF EXISTS tasks;")
    op.execute("DROP TABLE IF EXISTS journals;")
    # tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(255), index=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('due_date', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_tasks_id'), 'tasks', ['id'], unique=False)
    op.create_index(op.f('ix_tasks_user_id'), 'tasks', ['user_id'], unique=False)

    # journals table
    op.create_table(
        'journals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(255), index=True, nullable=False),
        sa.Column('entry', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index(op.f('ix_journals_id'), 'journals', ['id'], unique=False)
    op.create_index(op.f('ix_journals_user_id'), 'journals', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_journals_user_id'), table_name='journals')
    op.drop_index(op.f('ix_journals_id'), table_name='journals')
    op.drop_table('journals')

    op.drop_index(op.f('ix_tasks_user_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_id'), table_name='tasks')
    op.drop_table('tasks')
