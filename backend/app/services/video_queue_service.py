from collections.abc import Callable
from typing import Protocol

from app.db.models import VideoStatus
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
            raise VideoNotQueueableError("La vidéo a déjà été mise en file par une autre requête.")
        try:
            task = self.dispatcher(video_id)
        except Exception as exc:
            video.status = VideoStatus.READY
            video.error_message = "Redis ou Celery est indisponible."
            self.repository.save(video)
            raise QueueUnavailableError(video.error_message) from exc

        video.task_id = task.id
        self.repository.save(video)
        return EnqueueResponse(video_id=video.id, task_id=task.id, status=video.status)

