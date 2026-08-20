from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image

from app.core.config import Settings
from app.db.models import MediaType, VideoStatus
from app.services.media_upload import LocalMediaUploadService, MediaUploadError
from app.api.v1 import media as media_api


def image_bytes(image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), "white").save(output, format=image_format)
    return output.getvalue()


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

    assert list(tmp_path.iterdir()) == []


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
        {"filename": "unsupported.txt", "error": "Seules les images sont disponibles dans ce premier lot."}
    ]
