from pydantic import BaseModel, Field

from app.schemas.video import VideoRead


class VideoSampleResponse(BaseModel):
    video: VideoRead
    source_duration_seconds: float = Field(gt=0)
    sample_start_seconds: float = Field(ge=0)
    sample_duration_seconds: float = Field(gt=0)
    frame_count: int = Field(gt=0)

