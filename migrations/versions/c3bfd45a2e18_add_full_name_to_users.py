"""add full_name to users

Revision ID: c3bfd45a2e18
Revises: eb2c6b969610
Create Date: 2026-10-15 13:45:10.308115

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3bfd45a2e18'
down_revision = 'eb2c6b969610'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('full_name', sa.String(length=150), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('full_name')
