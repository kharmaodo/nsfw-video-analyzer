from app.db.models import Video, VideoStatus
from app.repositories.video_repository import VideoRepository
from app.services.video_processor import VideoProcessingError, VideoProcessor, VideoSample


class VideoSamplingNotFoundError(LookupError):
    pass


class VideoNotReadyError(ValueError):
    pass


class VideoSamplingService:
    def __init__(self, processor: VideoProcessor, repository: VideoRepository) -> None:
        self.processor = processor
        self.repository = repository

    async def sample(self, video_id: int) -> tuple[Video, VideoSample]:
        video = self.repository.get(video_id)
        if video is None:
            raise VideoSamplingNotFoundError("Vidéo introuvable.")
        if video.status != VideoStatus.READY:
            raise VideoNotReadyError(
                f"La vidéo doit être au statut READY, statut actuel : {video.status.value}."
            )

        source_url = video.resolved_video_url or video.video_url
        sample = await self.processor.extract_central_frames(video.id, source_url)
        video.duration_seconds = sample.source_duration_seconds
        video.sampled_frames = len(sample.frame_paths)
        self.repository.save(video)
        return video, sample

