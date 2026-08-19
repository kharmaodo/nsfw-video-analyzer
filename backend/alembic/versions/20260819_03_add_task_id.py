"""add celery task id

Revision ID: 20260819_03
Revises: 20260819_02
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_03"
down_revision: str | None = "20260819_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("task_id", sa.String(length=255), nullable=True))
    op.create_index("ix_videos_task_id", "videos", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_videos_task_id", table_name="videos")
    op.drop_column("videos", "task_id")
