"""add hashtags to posts

Revision ID: 1facb5323760
Revises: 7b59ee3a9bda
Create Date: 2026-10-03 04:39:16.977324

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1facb5323760"
down_revision = "7b59ee3a9bda"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "posts",
        sa.Column(
            "hashtags",
            sa.String(length=255),
            nullable=True
        )
    )


def downgrade():
    op.drop_column(
        "posts",
        "hashtags"
    )