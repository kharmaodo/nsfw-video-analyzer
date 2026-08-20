from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.video_repository import VideoRepository
from app.schemas.media import MediaUploadFailure, MediaUploadResponse
from app.services.media_upload import LocalMediaUploadService, MediaUploadError

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/uploads", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    files: Annotated[list[UploadFile], File(...)],
    db: Annotated[Session, Depends(get_db)],
) -> MediaUploadResponse:
    settings = get_settings()
    if len(files) > settings.media_upload_max_files:
        raise HTTPException(status_code=413, detail="Nombre maximal de fichiers dépassé.")
    repository = VideoRepository(db)
    service = LocalMediaUploadService(settings)
    created = []
    failures = []
    for file in files:
        filename = file.filename or "media"
        video = None
        if not (file.content_type or "").lower().startswith("image/"):
            failures.append(MediaUploadFailure(filename=filename, error="Seules les images sont disponibles dans ce premier lot."))
            await file.close()
            continue
        try:
            video = await service.store_image(file)
            created.append(repository.create(video))
        except (MediaUploadError, IntegrityError) as exc:
            if isinstance(exc, IntegrityError) and video is not None:
                Path(settings.media_storage_directory, video.storage_path or "").unlink(missing_ok=True)
            failures.append(MediaUploadFailure(filename=filename, error=str(exc)))
    return MediaUploadResponse(created=created, failures=failures)
