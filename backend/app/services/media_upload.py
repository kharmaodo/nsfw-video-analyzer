import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings
from app.db.models import MediaType, Video, VideoStatus


class MediaUploadError(ValueError):
    pass


class LocalMediaUploadService:
    IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.media_storage_directory).resolve()

    async def store_image(self, upload: UploadFile) -> Video:
        filename = Path(upload.filename or "media").name
        if not filename or filename == ".":
            raise MediaUploadError("Nom de fichier invalide.")

        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{uuid4()}{Path(filename).suffix.lower()}"
        digest = hashlib.sha256()
        size = 0

        try:
            with destination.open("xb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.image_max_size_bytes:
                        raise MediaUploadError(
                            "L’image dépasse la taille maximale autorisée."
                        )
                    digest.update(chunk)
                    target.write(chunk)

            if size == 0:
                raise MediaUploadError("Le fichier est vide.")

            try:
                with Image.open(destination) as image:
                    image.verify()
                with Image.open(destination) as image:
                    content_type = Image.MIME.get(image.format or "", "").lower()
                    width, height = image.size
            except (UnidentifiedImageError, OSError) as exc:
                raise MediaUploadError(
                    "Le fichier n’est pas une image valide."
                ) from exc

            if content_type not in self.IMAGE_TYPES:
                raise MediaUploadError("Format image non autorisé.")
            if upload.content_type and upload.content_type.lower() != content_type:
                raise MediaUploadError(
                    "Le type MIME déclaré ne correspond pas au contenu du fichier."
                )

            return Video(
                title=Path(filename).stem[:500] or "Image importée",
                page_url=f"local://{destination.name}",
                video_url=f"local://{destination.name}",
                media_type=MediaType.IMAGE,
                original_filename=filename[:500],
                storage_path=destination.name,
                sha256=digest.hexdigest(),
                content_type=content_type,
                size_bytes=size,
                width=width,
                height=height,
                sampled_frames=1,
                status=VideoStatus.READY,
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
