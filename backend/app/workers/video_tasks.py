import asyncio
from pathlib import Path

from celery import Task

from app.core.config import get_settings
from app.db.models import VideoStatus
from app.db.session import SessionLocal
from app.repositories.video_repository import VideoRepository
from app.services.video_processor import VideoProcessingError, VideoProcessor
from app.services.nsfw_classifier import NsfwClassificationError, TransformersNsfwClassifier
from app.workers.celery_app import celery_app

settings = get_settings()
nsfw_classifier = TransformersNsfwClassifier(settings)


def cleanup_sample_frames(frame_paths: tuple[Path, ...]) -> None:
    temporary_root = Path(settings.video_temporary_directory).resolve()
    directories: set[Path] = set()
    for frame_path in frame_paths:
        resolved = frame_path.resolve()
        if not resolved.is_relative_to(temporary_root):
            continue
        directories.add(resolved.parent)
        resolved.unlink(missing_ok=True)
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


async def process_queued_video(
    video_id: int,
    processor: VideoProcessor,
    classifier: TransformersNsfwClassifier,
) -> dict[str, int | float | str]:
    with SessionLocal() as session:
        repository = VideoRepository(session)
        video = repository.get(video_id)
        if video is None:
            raise LookupError(f"Vidéo {video_id} introuvable.")
        if video.status not in {VideoStatus.QUEUED, VideoStatus.PROCESSING}:
            raise ValueError(
                f"Vidéo {video_id} non traitable au statut {video.status.value}."
            )
        video.status = VideoStatus.PROCESSING
        video.error_message = None
        repository.save(video)
        source_url = video.resolved_video_url or video.video_url

    sample = await processor.extract_central_frames(video_id, source_url)
    try:
        summary = await asyncio.to_thread(classifier.classify, sample.frame_paths)
    finally:
        if settings.nsfw_cleanup_frames and sample.frame_paths:
            cleanup_sample_frames(sample.frame_paths)

    with SessionLocal() as session:
        repository = VideoRepository(session)
        video = repository.get(video_id)
        if video is None:
            raise LookupError(f"Vidéo {video_id} introuvable après traitement.")
        video.duration_seconds = sample.source_duration_seconds
        video.sampled_frames = len(sample.frame_paths)
        video.nsfw_score = summary.maximum_score
        video.nsfw_average_score = summary.average_score
        video.nsfw_positive_frames = summary.positive_frames
        video.nsfw_model = classifier.model_identifier
        video.status = (
            VideoStatus.SAMPLED_NSFW if summary.is_nsfw else VideoStatus.SAMPLED_SAFE
        )
        repository.save(video)
    return {
        "video_id": video_id,
        "duration_seconds": sample.source_duration_seconds,
        "sampled_frames": len(sample.frame_paths),
        "nsfw_score": summary.maximum_score,
        "status": video.status.value,
    }


def mark_video_error(video_id: int, message: str) -> None:
    with SessionLocal() as session:
        repository = VideoRepository(session)
        video = repository.get(video_id)
        if video is None:
            return
        video.status = VideoStatus.ERROR
        video.error_message = message[-2000:]
        repository.save(video)


@celery_app.task(
    bind=True,
    name="videos.process",
    max_retries=settings.celery_max_retries,
)
def process_video_task(self: Task, video_id: int) -> dict[str, int | float | str]:
    try:
        return asyncio.run(
            process_queued_video(video_id, VideoProcessor(settings), nsfw_classifier)
        )
    except (VideoProcessingError, NsfwClassificationError) as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=settings.celery_retry_delay_seconds,
            )
        mark_video_error(video_id, str(exc))
        raise
    except Exception as exc:
        mark_video_error(video_id, str(exc))
        raise
