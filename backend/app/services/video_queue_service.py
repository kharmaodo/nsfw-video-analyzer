from collections.abc import Callable
from typing import Protocol

from app.db.models import Video, VideoStatus
from app.repositories.video_repository import VideoRepository
from app.schemas.jobs import EnqueueResponse


class AsyncTaskResult(Protocol):
    id: str


TaskDispatcher = Callable[[int], AsyncTaskResult]


class QueueVideoNotFoundError(LookupError):
    pass


class VideoNotQueueableError(ValueError):
    pass


class QueueUnavailableError(RuntimeError):
    pass


class VideoQueueService:
    def __init__(self, repository: VideoRepository, dispatcher: TaskDispatcher) -> None:
        self.repository = repository
        self.dispatcher = dispatcher

    def enqueue(self, video_id: int) -> EnqueueResponse:
        video = self.repository.get(video_id)
        if video is None:
            raise QueueVideoNotFoundError("Vidéo introuvable.")
        if video.status != VideoStatus.READY:
            raise VideoNotQueueableError(
                f"La vidéo doit être au statut READY, statut actuel : {video.status.value}."
            )

        video = self.repository.mark_queued(video_id)
        if video is None:
            raise VideoNotQueueableError(
                "La vidéo a déjà été mise en file par une autre requête."
            )

        try:
            return self._dispatch_queued(video)
        except QueueUnavailableError:
            video.status = VideoStatus.READY
            video.error_message = "Redis ou Celery est indisponible."
            self.repository.save(video)
            raise

    def requeue(self, video_id: int) -> EnqueueResponse:
        video = self.repository.get(video_id)
        if video is None:
            raise QueueVideoNotFoundError("Vidéo introuvable.")
        if video.status != VideoStatus.QUEUED:
            raise VideoNotQueueableError(
                f"La vidéo doit être au statut QUEUED, statut actuel : {video.status.value}."
            )

        return self._dispatch_queued(video)

    def recover_queued(self) -> int:
        videos, _ = self.repository.list(
            offset=0,
            limit=100,
            status=VideoStatus.QUEUED,
        )
        recovered = 0

        for video in videos:
            try:
                self.requeue(video.id)
            except QueueUnavailableError:
                break
            except VideoNotQueueableError:
                continue
            else:
                recovered += 1

        return recovered

    def _dispatch_queued(self, video: Video) -> EnqueueResponse:
        try:
            task = self.dispatcher(video.id)
        except Exception as exc:
            raise QueueUnavailableError("Redis ou Celery est indisponible.") from exc

        refreshed = self.repository.get(video.id)
        if refreshed is None:
            raise QueueVideoNotFoundError("Vidéo introuvable.")
        if refreshed.status == VideoStatus.QUEUED:
            refreshed.task_id = task.id
            self.repository.save(refreshed)

        return EnqueueResponse(
            video_id=refreshed.id,
            task_id=refreshed.task_id or task.id,
            status=refreshed.status,
        )