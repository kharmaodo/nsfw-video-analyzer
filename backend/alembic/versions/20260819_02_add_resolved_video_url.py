"""add resolved video url

Revision ID: 20260819_02
Revises: 20260819_01
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_02"
down_revision: str | None = "20260819_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("resolved_video_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "resolved_video_url")
