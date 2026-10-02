"""add notification model

Revision ID: 7b59ee3a9bda
Revises: 9a15e3e81b28
Create Date: 2026-10-03 03:42:23.602698
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b59ee3a9bda"
down_revision = "9a15e3e81b28"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "actor_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "notification_type",
            sa.String(length=20),
            nullable=False
        ),

        sa.Column(
            "post_id",
            sa.Integer(),
            nullable=True
        ),

        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True
        ),

        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"]
        ),

        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"]
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"]
        ),

        sa.PrimaryKeyConstraint("id")
    )


def downgrade():
    op.drop_table("notifications")