"""create videos table

Revision ID: 20260819_01
Revises:
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("accepts_ranges", sa.Boolean(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DISCOVERED", "VALIDATING", "READY", "REJECTED", "QUEUED",
                "PROCESSING", "SAMPLED_SAFE", "SAMPLED_NSFW", "ERROR",
                name="videostatus", native_enum=False, length=32,
            ),
            server_default="DISCOVERED",
            nullable=False,
        ),
        sa.Column("nsfw_score", sa.Float(), nullable=True),
        sa.Column("sampled_frames", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_url"),
    )
    op.create_index("ix_videos_status_created_at", "videos", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_videos_status_created_at", table_name="videos")
    op.drop_table("videos")

