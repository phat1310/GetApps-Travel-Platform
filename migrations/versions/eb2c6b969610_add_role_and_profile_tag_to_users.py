"""add role and profile_tag to users

Revision ID: eb2c6b969610
Revises: ad26082250f7
Create Date: 2026-10-10 13:00:10.199608

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb2c6b969610'
down_revision = 'ad26082250f7'
branch_labels = None
depends_on = None


def upgrade():
    # Không cần thao tác gì: các cột role/profile_tag (users) và các cột
    # itinerary/itinerary_days/itinerary_lodgings/itinerary_stops đã tồn tại
    # sẵn trong database (tạo từ trước). Migration này chỉ dùng để đồng bộ
    # version Alembic, không ALTER TABLE gì cả.
    pass


def downgrade():
    pass