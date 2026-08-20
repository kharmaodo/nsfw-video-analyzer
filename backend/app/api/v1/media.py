from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.videos import VideoQueueDependency, VideoServiceDependency
from app.core.config import get_settings
from app.db.models import VideoStatus
from app.db.session import get_db
from app.repositories.video_repository import VideoRepository
from app.schemas.jobs import EnqueueResponse
from app.schemas.media import MediaUploadFailure, MediaUploadResponse
from app.schemas.video import VideoListResponse, VideoRead
from app.services.media_upload import LocalMediaUploadService, MediaUploadError
from app.services.media_upload_rate_limiter import UploadRateLimiter
from app.services.video_queue_service import (
    QueueUnavailableError,
    QueueVideoNotFoundError,
    VideoNotQueueableError,
)

router = APIRouter(prefix="/media", tags=["media"])
DbSession = Annotated[Session, Depends(get_db)]
upload_rate_limiter = UploadRateLimiter()


@router.post(
    "/uploads",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    files: Annotated[list[UploadFile], File(...)],
    db: DbSession,
    request: Request,
) -> MediaUploadResponse:
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            request_size = int(content_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="En-tête Content-Length invalide.") from None
        if request_size > settings.media_upload_max_total_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="La requête dépasse la taille totale maximale autorisée.",
            )

    client_key = request.client.host if request.client else "unknown"
    if not upload_rate_limiter.allow(
        client_key,
        maximum_requests=settings.media_upload_rate_limit_requests,
        window_seconds=settings.media_upload_rate_limit_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de téléversements. Réessayez dans quelques instants.",
        )
    if len(files) > settings.media_upload_max_files:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Nombre maximal de fichiers dépassé.",
        )

    repository = VideoRepository(db)
    service = LocalMediaUploadService(settings)
    created: list[VideoRead] = []
    failures: list[MediaUploadFailure] = []

    for file in files:
        filename = file.filename or "media"
        video = None
        try:
            video = await service.store(file)
            created.append(repository.create(video))
        except IntegrityError:
            if video is not None:
                service.delete(video.storage_path)
            failures.append(
                MediaUploadFailure(
                    filename=filename,
                    error=(
                        "Ce média a déjà été importé. "
                        "Utilisez l’élément existant dans la liste."
                    ),
                )
            )
        except MediaUploadError as exc:
            failures.append(MediaUploadFailure(filename=filename, error=str(exc)))
    return MediaUploadResponse(created=created, failures=failures)


@router.post(
    "/{media_id}/requeue",
    response_model=EnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def requeue_media(
    media_id: int,
    service: VideoQueueDependency,
) -> EnqueueResponse:
    try:
        return service.requeue(media_id)
    except QueueVideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VideoNotQueueableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

@router.get("", response_model=VideoListResponse)
def list_media(
    service: VideoServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    media_status: Annotated[VideoStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> VideoListResponse:
    return service.list(
        page=page,
        size=size,
        status=media_status,
        search=search,
    )


@router.get("/{media_id}", response_model=VideoRead)
def get_media(media_id: int, service: VideoServiceDependency) -> VideoRead:
    media = service.get(media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Média introuvable.",
        )
    return media


@router.post(
    "/{media_id}/enqueue",
    response_model=EnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_media(
    media_id: int,
    service: VideoQueueDependency,
) -> EnqueueResponse:
    try:
        return service.enqueue(media_id)
    except QueueVideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VideoNotQueueableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
