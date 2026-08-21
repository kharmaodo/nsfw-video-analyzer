from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image

from app.core.config import Settings
from app.db.models import MediaType, User, UserRole, VideoStatus
from app.db.session import get_db
from app.main import app
from app.services.jwt_service import JwtService

from app.services.media_upload import LocalMediaUploadService, MediaUploadError
from app.api.v1 import media as media_api


def image_bytes(image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), "white").save(output, format=image_format)
    return output.getvalue()


def guest_headers() -> dict[str, str]:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        user = User(
            id=700001,
            username="rate-limited-guest",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    token = JwtService(settings).create_access_token(user)
    return {"Authorization": f"Bearer {token}"}



@pytest.mark.asyncio
async def test_stores_valid_image_with_prefilled_metadata(tmp_path) -> None:
    service = LocalMediaUploadService(Settings(media_storage_directory=str(tmp_path)))
    upload = UploadFile(filename="my cat.png", file=BytesIO(image_bytes()), headers={"content-type": "image/png"})

    video = await service.store_image(upload)

    assert video.media_type == MediaType.IMAGE
    assert video.status == VideoStatus.READY
    assert video.title == "my cat"
    assert video.content_type == "image/png"
    assert (video.width, video.height) == (12, 8)
    assert video.size_bytes and video.size_bytes > 0
    assert video.sha256 and len(video.sha256) == 64
    assert video.storage_path and (tmp_path / video.storage_path).is_file()


@pytest.mark.asyncio
async def test_rejects_declared_mime_that_does_not_match_content(tmp_path) -> None:
    service = LocalMediaUploadService(Settings(media_storage_directory=str(tmp_path)))
    upload = UploadFile(filename="image.jpg", file=BytesIO(image_bytes()), headers={"content-type": "image/jpeg"})

    with pytest.raises(MediaUploadError, match="MIME"):
        await service.store_image(upload)

    assert list(tmp_path.glob("*.png")) == []


def test_upload_endpoint_returns_successes_and_failures(client, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        media_api,
        "get_settings",
        lambda: Settings(media_storage_directory=str(tmp_path), media_upload_max_files=3),
    )

    response = client.post(
        "/api/v1/media/uploads",
        files=[
            ("files", ("safe.png", image_bytes(), "image/png")),
            ("files", ("unsupported.txt", b"not an image", "text/plain")),
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"][0]["media_type"] == "IMAGE"
    assert body["created"][0]["status"] == "READY"
    assert body["created"][0]["original_filename"] == "safe.png"
    assert body["failures"] == [
        {"filename": "unsupported.txt", "error": "Le fichier n’est pas une vidéo valide."}
    ]


def video_bytes(tmp_path) -> bytes:  # type: ignore[no-untyped-def]
    import subprocess

    path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=16x12:d=1",
            "-an", "-y", str(path),
        ],
        check=True,
    )
    return path.read_bytes()


@pytest.mark.asyncio
async def test_stores_valid_video_with_ffprobe_metadata(tmp_path) -> None:
    service = LocalMediaUploadService(
        Settings(media_storage_directory=str(tmp_path))
    )
    upload = UploadFile(
        filename="clip.mp4",
        file=BytesIO(video_bytes(tmp_path)),
        headers={"content-type": "video/mp4"},
    )

    video = await service.store(upload)

    assert video.media_type == MediaType.VIDEO
    assert video.status == VideoStatus.READY
    assert video.content_type == "video/mp4"
    assert (video.width, video.height) == (16, 12)
    assert video.duration_seconds and video.duration_seconds > 0
    assert video.sampled_frames >= 1


def test_media_aliases_list_and_get_existing_video(client) -> None:  # type: ignore[no-untyped-def]
    created = client.post(
        "/api/v1/videos",
        json={
            "title": "Media alias",
            "page_url": "https://example.org/page",
            "video_url": "https://cdn.example.org/video.mp4",
        },
    )
    assert created.status_code == 201
    media_id = created.json()["id"]

    listed = client.get("/api/v1/media?page=1&size=10")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    detail = client.get(f"/api/v1/media/{media_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == media_id


def test_media_enqueue_returns_404_when_media_does_not_exist(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/v1/media/999999/enqueue")

    assert response.status_code == 404
    assert response.json()["detail"] == "Vidéo introuvable."


def test_upload_endpoint_reports_duplicate_image_friendly(
    client,
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        media_api,
        "get_settings",
        lambda: Settings(
            media_storage_directory=str(tmp_path),
            media_upload_max_files=3,
        ),
    )

    headers = guest_headers()

    first = client.post(
        "/api/v1/media/uploads",
        files={"files": ("already-imported.png", image_bytes(), "image/png")},
    )
    assert first.status_code == 201
    assert len(first.json()["created"]) == 1

    duplicate = client.post(
        "/api/v1/media/uploads",
        files={"files": ("already-imported.png", image_bytes(), "image/png")},
    )

    assert duplicate.status_code == 201
    assert duplicate.json()["created"] == []
    assert duplicate.json()["failures"] == [
        {
            "filename": "already-imported.png",
            "error": (
                "Ce média a déjà été importé. "
                "Utilisez l’élément existant dans la liste."
            ),
        }
    ]


def test_upload_endpoint_rejects_request_exceeding_total_limit(
    client,
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        media_api,
        "get_settings",
        lambda: Settings(
            media_storage_directory=str(tmp_path),
            media_upload_max_total_bytes=1024,
        ),
    )
    monkeypatch.setattr(media_api, "upload_rate_limiter", media_api.UploadRateLimiter())

    response = client.post(
        "/api/v1/media/uploads",
        files={"files": ("too-large.bin", b"x" * 2048, "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "La requête dépasse la taille totale maximale autorisée."
    )


def test_upload_endpoint_rate_limits_client(
    client,
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        media_api,
        "get_settings",
        lambda: Settings(
            media_storage_directory=str(tmp_path),
            media_upload_rate_limit_requests=1,
            media_upload_rate_limit_window_seconds=60,
        ),
    )
    monkeypatch.setattr(media_api, "upload_rate_limiter", media_api.UploadRateLimiter())

    headers = guest_headers()

    first = client.post(
        "/api/v1/media/uploads",
        headers=headers,

        files={"files": ("first.png", image_bytes(), "image/png")},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/media/uploads",
        headers=headers,

        files={"files": ("second.png", image_bytes("JPEG"), "image/jpeg")},
    )

    assert second.status_code == 429
    assert second.json()["detail"] == (
        "Trop de téléversements. Réessayez dans quelques instants."
    )


def test_delete_local_media_removes_stored_file(
    client,
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    from app.services import video_service

    settings = Settings(media_storage_directory=str(tmp_path))
    monkeypatch.setattr(media_api, "get_settings", lambda: settings)
    monkeypatch.setattr(video_service, "get_settings", lambda: settings)

    imported = client.post(
        "/api/v1/media/uploads",
        files={"files": ("to-delete.png", image_bytes(), "image/png")},
    )

    assert imported.status_code == 201
    media_id = imported.json()["created"][0]["id"]
    stored_files = list(tmp_path.glob("*.png"))
    assert len(stored_files) == 1

    deleted = client.delete(f"/api/v1/videos/{media_id}")

    assert deleted.status_code == 204
    assert list(tmp_path.glob("*.png")) == []
    assert client.get(f"/api/v1/media/{media_id}").status_code == 404


def image_bytes_with_metadata() -> bytes:
    output = BytesIO()
    exif = Image.Exif()
    exif[270] = "Titre EXIF dynamique"
    exif[306] = "2026:08:20 09:30:18"
    exif[36867] = "2026:08:20 09:30:18"
    Image.new("RGB", (12, 8), "white").save(
        output,
        format="JPEG",
        exif=exif,
    )
    return output.getvalue()


def guest_headers() -> dict[str, str]:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        user = User(
            id=700001,
            username="rate-limited-guest",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    token = JwtService(settings).create_access_token(user)
    return {"Authorization": f"Bearer {token}"}



@pytest.mark.asyncio
async def test_image_metadata_sets_dynamic_title_and_date(tmp_path) -> None:
    service = LocalMediaUploadService(
        Settings(media_storage_directory=str(tmp_path))
    )
    upload = UploadFile(
        filename="fallback-name.jpg",
        file=BytesIO(image_bytes_with_metadata()),
        headers={"content-type": "image/jpeg"},
    )

    video = await service.store(upload)

    assert video.title == "Titre EXIF dynamique"
    assert video.metadata_title == "Titre EXIF dynamique"
    assert video.media_created_at is not None
    assert video.media_created_at.year == 2026


def test_extract_image_metadata_reads_gps_coordinates(
    tmp_path,
    monkeypatch,
) -> None:
    from app.services import media_metadata

    class Tag:
        def __init__(self, value, values=None) -> None:
            self.value = value
            self.values = values if values is not None else value

        def __str__(self) -> str:
            return str(self.value)

    path = tmp_path / "metadata.jpg"
    path.write_bytes(b"image")

    monkeypatch.setattr(
        media_metadata.exifread,
        "process_file",
        lambda _source, details=False: {
            "Image ImageDescription": Tag("Photo géolocalisée"),
            "EXIF DateTimeOriginal": Tag("2026:08:20 09:30:18"),
            "GPS GPSLatitude": Tag("", (14, 40, 30)),
            "GPS GPSLatitudeRef": Tag("N"),
            "GPS GPSLongitude": Tag("", (17, 25, 15)),
            "GPS GPSLongitudeRef": Tag("W"),
        },
    )

    metadata = media_metadata.extract_image_metadata(path)

    assert metadata.title == "Photo géolocalisée"
    assert metadata.media_created_at is not None
    assert metadata.gps_latitude == pytest.approx(14.675)
    assert metadata.gps_longitude == pytest.approx(-17.420833, abs=0.000001)


@pytest.mark.asyncio
async def test_image_without_metadata_uses_filename_as_title(tmp_path) -> None:
    service = LocalMediaUploadService(
        Settings(media_storage_directory=str(tmp_path))
    )
    upload = UploadFile(
        filename="no-metadata.png",
        file=BytesIO(image_bytes()),
        headers={"content-type": "image/png"},
    )

    video = await service.store(upload)

    assert video.title == "no-metadata"
    assert video.metadata_title is None
    assert video.media_created_at is None
    assert video.gps_latitude is None
    assert video.gps_longitude is None
