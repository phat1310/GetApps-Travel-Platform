"""add is_private to users

Revision ID: 9a15e3e81b28
Revises: b5276ad32acc
Create Date: 2026-10-03 02:56:16.332369
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9a15e3e81b28"
down_revision = "b5276ad32acc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_private",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            )
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_private")