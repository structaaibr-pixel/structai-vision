"""captures.has_video (upload de vídeo com extração de frames no servidor)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("captures", sa.Column("has_video", sa.Boolean(), nullable=False,
                                        server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("captures", "has_video")
