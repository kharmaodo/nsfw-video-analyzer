from app.db.models import Video, VideoStatus
from app.repositories.video_repository import VideoRepository
from app.services.remote_video import RemoteVideoError, RemoteVideoInspector


class VideoNotFoundError(LookupError):
    pass


class VideoNotDiscoverableError(ValueError):
    pass


class VideoValidationService:
    def __init__(self, inspector: RemoteVideoInspector, repository: VideoRepository) -> None:
        self.inspector = inspector
        self.repository = repository

    async def validate(self, video_id: int) -> Video:
        video = self.repository.get(video_id)
        if video is None:
            raise VideoNotFoundError("Vidéo introuvable.")
        if video.status != VideoStatus.DISCOVERED:
            raise VideoNotDiscoverableError(
                f"La vidéo doit être au statut DISCOVERED, statut actuel : {video.status.value}."
            )

        video.status = VideoStatus.VALIDATING
        video.error_message = None
        self.repository.save(video)
        try:
            metadata = await self.inspector.inspect(video.video_url)
        except RemoteVideoError as exc:
            video.status = VideoStatus.REJECTED
            video.error_message = str(exc)
            return self.repository.save(video)

        video.resolved_video_url = metadata.final_url
        video.content_type = metadata.content_type
        video.size_bytes = metadata.size_bytes
        video.accepts_ranges = metadata.accepts_ranges
        video.status = VideoStatus.READY
        video.error_message = None
        return self.repository.save(video)
