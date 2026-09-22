"""add original post id

Revision ID: e965311d54fe
Revises: a0233a7a1963
Create Date: 2026-09-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e965311d54fe"
down_revision = "a0233a7a1963"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "original_post_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_foreign_key(
            "fk_posts_original_post_id",
            "posts",
            ["original_post_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_posts_original_post_id",
            type_="foreignkey"
        )

        batch_op.drop_column("original_post_id")