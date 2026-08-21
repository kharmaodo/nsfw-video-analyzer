import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VideoStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SAMPLED_SAFE = "SAMPLED_SAFE"
    SAMPLED_NSFW = "SAMPLED_NSFW"
    ERROR = "ERROR"



class UserRole(str, enum.Enum):
    GUEST = "GUEST"
    SUPER_POWER = "SUPER_POWER"


class MediaType(str, enum.Enum):
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=32),
        nullable=False,
        default=UserRole.GUEST,
        server_default=UserRole.GUEST.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_actor_created_at", "actor_user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    video_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    resolved_video_url: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, native_enum=False, length=16),
        nullable=False,
        default=MediaType.VIDEO,
        server_default=MediaType.VIDEO.value,
    )
    original_filename: Mapped[str | None] = mapped_column(String(500))
    metadata_title: Mapped[str | None] = mapped_column(String(500))
    media_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gps_latitude: Mapped[float | None] = mapped_column(Float)
    gps_longitude: Mapped[float | None] = mapped_column(Float)
    storage_path: Mapped[str | None] = mapped_column(Text, unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    accepts_ranges: Mapped[bool | None] = mapped_column()
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, native_enum=False, length=32),
        nullable=False,
        default=VideoStatus.DISCOVERED,
        server_default=VideoStatus.DISCOVERED.value,
    )
    nsfw_score: Mapped[float | None] = mapped_column(Float)
    nsfw_average_score: Mapped[float | None] = mapped_column(Float)
    nsfw_positive_frames: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    nsfw_model: Mapped[str | None] = mapped_column(String(255))
    sampled_frames: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
