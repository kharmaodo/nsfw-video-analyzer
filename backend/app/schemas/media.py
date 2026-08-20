from pydantic import BaseModel, Field

from app.schemas.video import VideoRead


class MediaUploadFailure(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    error: str


class MediaUploadResponse(BaseModel):
    created: list[VideoRead]
    failures: list[MediaUploadFailure]
