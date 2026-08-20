"""add local media metadata

Revision ID: 20260820_05
Revises: 20260819_04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_05"
down_revision: str | None = "20260819_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("media_type", sa.String(length=16), server_default="VIDEO", nullable=False))
    op.add_column("videos", sa.Column("original_filename", sa.String(length=500), nullable=True))
    op.add_column("videos", sa.Column("storage_path", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("videos", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("height", sa.Integer(), nullable=True))
    op.create_index("uq_videos_storage_path", "videos", ["storage_path"], unique=True)
    op.create_index("uq_videos_sha256", "videos", ["sha256"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_videos_sha256", table_name="videos")
    op.drop_index("uq_videos_storage_path", table_name="videos")
    op.drop_column("videos", "height")
    op.drop_column("videos", "width")
    op.drop_column("videos", "sha256")
    op.drop_column("videos", "storage_path")
    op.drop_column("videos", "original_filename")
    op.drop_column("videos", "media_type")
