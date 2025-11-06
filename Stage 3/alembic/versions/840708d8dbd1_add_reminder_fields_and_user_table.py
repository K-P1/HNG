"""add_reminder_fields_and_user_table

Revision ID: 840708d8dbd1
Revises: 5c20efb07450
Create Date: 2025-11-06 18:41:03.711909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '840708d8dbd1'
down_revision: Union[str, None] = '5c20efb07450'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('push_url', sa.Text(), nullable=True),
        sa.Column('push_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=True)

    # Add reminder fields to tasks table
    op.add_column('tasks', sa.Column('reminder_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('last_reminder_sent', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('reminder_enabled', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove reminder fields from tasks table
    op.drop_column('tasks', 'reminder_enabled')
    op.drop_column('tasks', 'last_reminder_sent')
    op.drop_column('tasks', 'reminder_time')

    # Drop users table
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
