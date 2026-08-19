from pydantic import BaseModel

from app.db.models import VideoStatus


class EnqueueResponse(BaseModel):
    video_id: int
    task_id: str
    status: VideoStatus

