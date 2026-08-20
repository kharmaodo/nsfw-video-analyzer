from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.db.models import MediaType, VideoStatus


class VideoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    page_url: AnyHttpUrl
    video_url: AnyHttpUrl


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    page_url: str
    video_url: str
    resolved_video_url: str | None
    media_type: MediaType
    original_filename: str | None
    metadata_title: str | None
    media_created_at: datetime | None
    gps_latitude: float | None
    gps_longitude: float | None
    width: int | None
    height: int | None
    content_type: str | None
    size_bytes: int | None
    duration_seconds: float | None
    accepts_ranges: bool | None
    status: VideoStatus
    nsfw_score: float | None
    nsfw_average_score: float | None
    nsfw_positive_frames: int
    nsfw_model: str | None
    sampled_frames: int
    task_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class VideoListResponse(BaseModel):
    items: list[VideoRead]
    page: int
    size: int
    total: int
    pages: int


class VideoStatusUpdate(BaseModel):
    status: VideoStatus
    error_message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def error_status_requires_message(self) -> "VideoStatusUpdate":
        if self.status == VideoStatus.ERROR and not self.error_message:
            raise ValueError("error_message est obligatoire pour le statut ERROR")
        return self
