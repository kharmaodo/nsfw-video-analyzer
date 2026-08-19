from app.db.models import Video, VideoStatus
from app.repositories.video_repository import VideoRepository
from app.services.media_resolver import MediaResolutionError, MediaResolver
from app.services.remote_video import RemoteVideoError, RemoteVideoInspector


class VideoNotFoundError(LookupError):
    pass


class VideoNotDiscoverableError(ValueError):
    pass


class VideoValidationService:
    def __init__(
        self,
        inspector: RemoteVideoInspector,
        repository: VideoRepository,
        media_resolver: MediaResolver | None = None,
    ) -> None:
        self.inspector = inspector
        self.repository = repository
        self.media_resolver = media_resolver or MediaResolver()

    async def validate(self, video_id: int) -> Video:
        video = self.repository.get(video_id)
        if video is None:
            raise VideoNotFoundError("Vidéo introuvable.")
        if video.status not in {VideoStatus.DISCOVERED, VideoStatus.REJECTED}:
            raise VideoNotDiscoverableError(
                "La vidéo doit être au statut DISCOVERED ou REJECTED, "
                f"statut actuel : {video.status.value}."
            )

        video.status = VideoStatus.VALIDATING
        video.error_message = None
        self.repository.save(video)
        try:
            media = await self.media_resolver.resolve(video.video_url)
            metadata = await self.inspector.inspect(media.stream_url)
        except (MediaResolutionError, RemoteVideoError) as exc:
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