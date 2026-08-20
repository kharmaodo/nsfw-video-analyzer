"""add extracted media metadata

Revision ID: 20260820_06
Revises: 20260820_05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_06"
down_revision: str | None = "20260820_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("metadata_title", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("media_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("gps_latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("gps_longitude", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "gps_longitude")
    op.drop_column("videos", "gps_latitude")
    op.drop_column("videos", "media_created_at")
    op.drop_column("videos", "metadata_title")
