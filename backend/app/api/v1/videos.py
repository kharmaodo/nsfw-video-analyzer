from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import VideoStatus
from app.db.session import get_db
from app.repositories.video_repository import VideoRepository
from app.schemas.video import (
    VideoCreate,
    VideoListResponse,
    VideoRead,
    VideoStatusUpdate,
)
from app.services.video_service import InvalidStatusTransition, VideoService
from app.core.config import get_settings
from app.core.authentication import CurrentUserDependency

from app.services.remote_video import RemoteVideoInspector
from app.services.video_validation_service import (
    VideoNotDiscoverableError,
    VideoNotFoundError,
    VideoValidationService,
)
from app.schemas.sampling import VideoSampleResponse
from app.services.video_processor import VideoProcessingError, VideoProcessor
from app.services.video_sampling_service import (
    VideoNotReadyError,
    VideoSamplingNotFoundError,
    VideoSamplingService,
)
from app.schemas.jobs import EnqueueResponse
from app.services.media_authorization_service import (
    MediaAccessDeniedError,
    MediaAuthorizationService,
)

from app.services.video_queue_service import (
    QueueUnavailableError,
    QueueVideoNotFoundError,
    VideoNotQueueableError,
    VideoQueueService,
)
from app.workers.video_tasks import process_video_task

router = APIRouter(prefix="/videos", tags=["videos"])
DbSession = Annotated[Session, Depends(get_db)]


def get_service(db: DbSession) -> VideoService:
    return VideoService(VideoRepository(db))


VideoServiceDependency = Annotated[VideoService, Depends(get_service)]


def get_validation_service(db: DbSession) -> VideoValidationService:
    return VideoValidationService(
        inspector=RemoteVideoInspector(get_settings()),
        repository=VideoRepository(db),
    )


VideoValidationDependency = Annotated[VideoValidationService, Depends(get_validation_service)]


def get_sampling_service(db: DbSession) -> VideoSamplingService:
    return VideoSamplingService(
        processor=VideoProcessor(get_settings()),
        repository=VideoRepository(db),
    )


VideoSamplingDependency = Annotated[VideoSamplingService, Depends(get_sampling_service)]


def get_queue_service(db: DbSession) -> VideoQueueService:
    return VideoQueueService(
        repository=VideoRepository(db),
        dispatcher=process_video_task.delay,
    )


VideoQueueDependency = Annotated[VideoQueueService, Depends(get_queue_service)]




def require_video_access(
    video_id: int,
    user: CurrentUserDependency,
    repository: VideoRepository,
) -> None:
    video = repository.get(video_id)
    if video is None:
        return
    try:
        MediaAuthorizationService.require_access(user, video)
    except MediaAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vidéo introuvable.",
        ) from exc


@router.post("", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
def create_video(payload: VideoCreate, service: VideoServiceDependency, user: CurrentUserDependency) -> VideoRead:
    try:
        return service.create(payload, owner_user_id=user.id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une vidéo avec cette URL existe déjà.",
        ) from exc


@router.get("", response_model=VideoListResponse)
def list_videos(
    service: VideoServiceDependency,
    user: CurrentUserDependency,

    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    video_status: Annotated[VideoStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> VideoListResponse:
    return service.list(page=page, size=size, status=video_status, search=search)


@router.get("/{video_id}", response_model=VideoRead)
def get_video(video_id: int, service: VideoServiceDependency, user: CurrentUserDependency) -> VideoRead:
    video = service.get(video_id)
    require_video_access(video_id, user, service.repository)

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable.")
    return video


@router.post("/{video_id}/validate", response_model=VideoRead)
async def validate_video(video_id: int, service: VideoValidationDependency, user: CurrentUserDependency) -> VideoRead:
    require_video_access(video_id, user, service.repository)

    try:
        return await service.validate(video_id)
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VideoNotDiscoverableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{video_id}/sample", response_model=VideoSampleResponse)
async def sample_video(video_id: int, service: VideoSamplingDependency, user: CurrentUserDependency) -> VideoSampleResponse:
    require_video_access(video_id, user, service.repository)

    try:
        video, sample = await service.sample(video_id)
    except VideoSamplingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VideoNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except VideoProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return VideoSampleResponse(
        video=video,
        source_duration_seconds=sample.source_duration_seconds,
        sample_start_seconds=sample.window.start_seconds,
        sample_duration_seconds=sample.window.duration_seconds,
        frame_count=len(sample.frame_paths),
    )


@router.post("/{video_id}/enqueue", response_model=EnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_video(video_id: int, service: VideoQueueDependency, user: CurrentUserDependency) -> EnqueueResponse:
    require_video_access(video_id, user, service.repository)

    try:
        return service.enqueue(video_id)
    except QueueVideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VideoNotQueueableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.patch("/{video_id}/status", response_model=VideoRead)
def update_video_status(
    video_id: int,
    payload: VideoStatusUpdate,
    service: VideoServiceDependency,
    user: CurrentUserDependency,

) -> VideoRead:
    require_video_access(video_id, user, service.repository)

    try:
        video = service.update_status(video_id, payload.status, payload.error_message)
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable.")
    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: int, service: VideoServiceDependency, user: CurrentUserDependency) -> Response:
    require_video_access(video_id, user, service.repository)

    if not service.delete(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
