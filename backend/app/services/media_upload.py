import asyncio
import hashlib
import json
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
    VIDEO_TYPES = {
        "video/mp4",
        "video/webm",
        "video/x-matroska",
        "video/quicktime",
        "video/x-msvideo",
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.media_storage_directory).resolve()

    async def store(self, upload: UploadFile) -> Video:
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
                    if size > self.settings.video_max_size_bytes:
                        raise MediaUploadError(
                            "Le fichier dépasse la taille maximale autorisée."
                        )
                    digest.update(chunk)
                    target.write(chunk)

            if size == 0:
                raise MediaUploadError("Le fichier est vide.")

            image_metadata = self._inspect_image(destination)
            if image_metadata is not None:
                if size > self.settings.image_max_size_bytes:
                    raise MediaUploadError(
                        "L’image dépasse la taille maximale autorisée."
                    )
                content_type, width, height = image_metadata
                media_type = MediaType.IMAGE
                duration_seconds = None
                sampled_frames = 1
            else:
                content_type, width, height, duration_seconds = (
                    await self._inspect_video(destination)
                )
                media_type = MediaType.VIDEO
                sampled_frames = self._estimated_frame_count(duration_seconds)

            if upload.content_type and upload.content_type.lower() != content_type:
                raise MediaUploadError(
                    "Le type MIME déclaré ne correspond pas au contenu du fichier."
                )

            return Video(
                title=Path(filename).stem[:500] or "Média importé",
                page_url=f"local://{destination.name}",
                video_url=f"local://{destination.name}",
                media_type=media_type,
                original_filename=filename[:500],
                storage_path=destination.name,
                sha256=digest.hexdigest(),
                content_type=content_type,
                size_bytes=size,
                width=width,
                height=height,
                duration_seconds=duration_seconds,
                sampled_frames=sampled_frames,
                status=VideoStatus.READY,
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    async def store_image(self, upload: UploadFile) -> Video:
        video = await self.store(upload)
        if video.media_type != MediaType.IMAGE:
            self.delete(video.storage_path)
            raise MediaUploadError("Le fichier n’est pas une image valide.")
        return video

    def delete(self, storage_path: str | None) -> None:
        if not storage_path:
            return
        path = (self.root / storage_path).resolve()
        if path.is_relative_to(self.root):
            path.unlink(missing_ok=True)

    def local_path(self, storage_path: str | None) -> Path:
        if not storage_path:
            raise MediaUploadError("Le média local ne possède pas de chemin de stockage.")
        path = (self.root / storage_path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise MediaUploadError(
                "Le média local est introuvable ou son chemin est invalide."
            )
        return path

    def _inspect_image(self, path: Path) -> tuple[str, int, int] | None:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                content_type = Image.MIME.get(image.format or "", "").lower()
                width, height = image.size
        except (UnidentifiedImageError, OSError):
            return None

        if content_type not in self.IMAGE_TYPES:
            raise MediaUploadError("Format image non autorisé.")
        return content_type, width, height

    async def _inspect_video(self, path: Path) -> tuple[str, int, int, float]:
        command = [
            self.settings.ffprobe_binary,
            "-v", "error",
            "-show_entries",
            "format=format_name,duration:stream=codec_type,width,height",
            "-of", "json",
            str(path),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.video_process_timeout_seconds,
            )
        except (OSError, TimeoutError) as exc:
            raise MediaUploadError(
                "Impossible de valider la vidéo avec FFprobe."
            ) from exc

        if process.returncode != 0:
            raise MediaUploadError("Le fichier n’est pas une vidéo valide.")

        try:
            payload = json.loads(stdout)
            duration = float(payload["format"]["duration"])
            stream = next(
                item for item in payload["streams"]
                if item["codec_type"] == "video"
            )
            width, height = int(stream["width"]), int(stream["height"])
            format_name = str(payload["format"]["format_name"])
        except (
            KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError
        ) as exc:
            raise MediaUploadError(
                "FFprobe n’a pas retourné des métadonnées vidéo valides."
            ) from exc

        if duration <= 0 or width <= 0 or height <= 0:
            raise MediaUploadError("Les métadonnées vidéo sont invalides.")

        content_type = self._video_content_type(path, format_name)
        if content_type not in self.VIDEO_TYPES:
            raise MediaUploadError("Format vidéo non autorisé.")
        return content_type, width, height, duration

    @staticmethod
    def _video_content_type(path: Path, format_name: str) -> str:
        formats = set(format_name.split(","))
        if "webm" in formats:
            return "video/webm"
        if "matroska" in formats:
            return "video/x-matroska"
        if "avi" in formats:
            return "video/x-msvideo"
        if "mov" in formats:
            with path.open("rb") as source:
                header = source.read(16)
            return "video/quicktime" if header[8:12] == b"qt  " else "video/mp4"
        return ""

    def _estimated_frame_count(self, duration_seconds: float) -> int:
        duration = min(
            duration_seconds,
            self.settings.video_clip_duration_seconds,
        )
        return max(1, int(duration / self.settings.video_frame_interval_seconds))
