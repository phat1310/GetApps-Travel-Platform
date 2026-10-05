"""add share type

Revision ID: a0233a7a1963
Revises: 53d5dbdf367b
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a0233a7a1963"
down_revision = "53d5dbdf367b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "shares",
        sa.Column(
            "share_type",
            sa.String(length=20),
            nullable=True
        )
    )


def downgrade():
    op.drop_column("shares", "share_type")