"""merge share repost and location migrations

Revision ID: b5276ad32acc
Revises: 616798142e41, e965311d54fe
Create Date: 2026-10-03 02:22:08.175923

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5276ad32acc'
down_revision = ('616798142e41', 'e965311d54fe')
branch_labels = None
depends_on = None


def upgrade():
    # Tại đây cả hai nhánh migration đã được chạy:
    # - nhánh main: Location, visibility, SavedPost constraint
    # - nhánh Trúc: share_type, original_post_id
    #
    # Một user có thể copy_link, download và repost cùng một post,
    # nhưng mỗi loại chỉ được ghi nhận một lần.
    with op.batch_alter_table('shares', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'unique_share_type',
            ['user_id', 'post_id', 'share_type']
        )


def downgrade():
    with op.batch_alter_table('shares', schema=None) as batch_op:
        batch_op.drop_constraint(
            'unique_share_type',
            type_='unique'
        )