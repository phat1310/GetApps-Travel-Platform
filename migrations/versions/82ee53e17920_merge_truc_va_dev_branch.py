"""merge truc va dev branch

Revision ID: 82ee53e17920
Revises: 1facb5323760, d82b6eadab73
Create Date: 2026-10-05 14:05:42.402799

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '82ee53e17920'
down_revision = ('1facb5323760', 'd82b6eadab73')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
