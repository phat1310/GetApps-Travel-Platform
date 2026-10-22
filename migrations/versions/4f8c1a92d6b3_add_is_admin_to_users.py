"""add is_admin to users

Revision ID: 4f8c1a92d6b3
Revises: c3bfd45a2e18
Create Date: 2026-10-22 13:30:00.000000

Viết tay (không phải autogenerate) vì cột is_admin đã tồn tại sẵn trên DB của
Khánh (tạo lúc build module admin, "db migrate" không thấy khác biệt gì để
sinh ra) -- nhưng DB của các thành viên khác trong team CHƯA có cột này, nên
cần migration thật để `flask db upgrade` thêm đúng cột cho họ.

is_admin là NOT NULL (xem app/models/user.py) nên bắt buộc có server_default
khi thêm cột vào bảng đã có dữ liệu -- nếu không, SQLite sẽ từ chối thêm cột
NOT NULL cho các dòng user đã tồn tại.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f8c1a92d6b3'
down_revision = 'c3bfd45a2e18'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # Bỏ server_default sau khi đã backfill xong -- từ giờ is_admin chỉ được
    # gán tường minh qua code/script (scripts/create_admin.py), không còn
    # default ngầm ở tầng DB nữa, khớp đúng với khai báo model.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_admin', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
