"""schema inicial (users, buildings, captures, measurements)

Corresponde EXATAMENTE ao estado que o antigo Base.metadata.create_all criava
(pré-Alembic). Banco de dev criado antes desta migração: rode
`alembic stamp 0001` uma vez e siga com `alembic upgrade head`.

Revision ID: 0001
Revises:
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

capture_source = sa.Enum("phone", "drone", "mixed", name="capturesource")
capture_status = sa.Enum("pending", "processing", "completed", "failed",
                         name="capturestatus")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_buildings_owner_id", "buildings", ["owner_id"])

    op.create_table(
        "captures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"),
                  nullable=False),
        sa.Column("source", capture_source, nullable=False),
        sa.Column("status", capture_status, nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("has_gcp", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_captures_building_id", "captures", ["building_id"])

    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("capture_id", sa.Integer(), sa.ForeignKey("captures.id"),
                  nullable=False, unique=True),
        sa.Column("surface_area_m2", sa.Float(), nullable=False),
        sa.Column("height_m", sa.Float(), nullable=False),
        sa.Column("footprint_perimeter_m", sa.Float(), nullable=False),
        sa.Column("mesh_key", sa.String(length=500), nullable=True),
        sa.Column("pointcloud_key", sa.String(length=500), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("measurements")
    op.drop_index("ix_captures_building_id", table_name="captures")
    op.drop_table("captures")
    op.drop_index("ix_buildings_owner_id", table_name="buildings")
    op.drop_table("buildings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    capture_source.drop(op.get_bind(), checkfirst=True)
    capture_status.drop(op.get_bind(), checkfirst=True)
