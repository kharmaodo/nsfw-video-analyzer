from pydantic import AnyHttpUrl, BaseModel, Field

from app.schemas.video import VideoRead


class ScrapeRequest(BaseModel):
    page_url: AnyHttpUrl


class ScrapeResponse(BaseModel):
    page_url: str
    discovered: int = Field(ge=0)
    created: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    videos: list[VideoRead]

