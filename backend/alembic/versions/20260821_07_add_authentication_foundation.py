"""add authentication foundation

Revision ID: 20260821_07
Revises: 20260820_06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_07"
down_revision: str | None = "20260820_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role_enum = sa.Enum(
        "GUEST",
        "SUPER_POWER",
        name="userrole",
        native_enum=False,
        length=32,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            role_enum,
            nullable=False,
            server_default="GUEST",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_audit_logs_actor_created_at",
        "audit_logs",
        ["actor_user_id", "created_at"],
    )

    with op.batch_alter_table("videos") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_videos_owner_user_id",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_videos_owner_user_id",
            ["owner_user_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_index("ix_videos_owner_user_id")
        batch_op.drop_constraint("fk_videos_owner_user_id", type_="foreignkey")
        batch_op.drop_column("owner_user_id")

    op.drop_index("ix_audit_logs_actor_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")