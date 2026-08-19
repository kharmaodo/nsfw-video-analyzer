"""add nsfw analysis fields

Revision ID: 20260819_04
Revises: 20260819_03
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_04"
down_revision: str | None = "20260819_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("nsfw_average_score", sa.Float(), nullable=True))
    op.add_column(
        "videos",
        sa.Column("nsfw_positive_frames", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("videos", sa.Column("nsfw_model", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "nsfw_model")
    op.drop_column("videos", "nsfw_positive_frames")
    op.drop_column("videos", "nsfw_average_score")
