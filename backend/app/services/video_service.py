from math import ceil

from app.db.models import Video, VideoStatus
from app.repositories.video_repository import VideoRepository
from app.schemas.video import VideoCreate, VideoListResponse


ALLOWED_TRANSITIONS: dict[VideoStatus, frozenset[VideoStatus]] = {
    VideoStatus.DISCOVERED: frozenset({VideoStatus.VALIDATING, VideoStatus.REJECTED}),
    VideoStatus.VALIDATING: frozenset({VideoStatus.READY, VideoStatus.REJECTED, VideoStatus.ERROR}),
    VideoStatus.READY: frozenset({VideoStatus.QUEUED, VideoStatus.REJECTED}),
    VideoStatus.QUEUED: frozenset({VideoStatus.PROCESSING, VideoStatus.ERROR}),
    VideoStatus.PROCESSING: frozenset(
        {VideoStatus.SAMPLED_SAFE, VideoStatus.SAMPLED_NSFW, VideoStatus.ERROR}
    ),
    VideoStatus.ERROR: frozenset({VideoStatus.QUEUED}),
    VideoStatus.REJECTED: frozenset(),
    VideoStatus.SAMPLED_SAFE: frozenset(),
    VideoStatus.SAMPLED_NSFW: frozenset(),
}


class InvalidStatusTransition(ValueError):
    pass


class VideoService:
    def __init__(self, repository: VideoRepository) -> None:
        self.repository = repository

    def create(self, payload: VideoCreate) -> Video:
        video = Video(
            title=payload.title.strip(),
            page_url=str(payload.page_url),
            video_url=str(payload.video_url),
        )
        return self.repository.create(video)

    def get(self, video_id: int) -> Video | None:
        return self.repository.get(video_id)

    def list(
        self,
        *,
        page: int,
        size: int,
        status: VideoStatus | None,
        search: str | None,
    ) -> VideoListResponse:
        items, total = self.repository.list(
            offset=(page - 1) * size,
            limit=size,
            status=status,
            search=search,
        )
        return VideoListResponse(
            items=items,
            page=page,
            size=size,
            total=total,
            pages=ceil(total / size) if total else 0,
        )

    def update_status(
        self,
        video_id: int,
        target: VideoStatus,
        error_message: str | None,
    ) -> Video | None:
        video = self.repository.get(video_id)
        if video is None:
            return None
        if target not in ALLOWED_TRANSITIONS[video.status]:
            raise InvalidStatusTransition(
                f"Transition interdite : {video.status.value} -> {target.value}."
            )

        video.status = target
        video.error_message = error_message if target == VideoStatus.ERROR else None
        return self.repository.save(video)

    def delete(self, video_id: int) -> bool:
        video = self.repository.get(video_id)
        if video is None:
            return False
        self.repository.delete(video)
        return True

