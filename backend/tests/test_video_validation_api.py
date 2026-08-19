from fastapi.testclient import TestClient

from app.api.v1.videos import get_validation_service
from app.db.session import get_db
from app.main import app
from app.repositories.video_repository import VideoRepository
from app.services.remote_video import RemoteVideoError, RemoteVideoMetadata
from app.services.video_validation_service import VideoValidationService


VIDEO = {
    "title": "Vidéo distante",
    "page_url": "https://media.example/catalogue",
    "video_url": "https://cdn.example/video.mp4",
}


class SuccessfulInspector:
    async def inspect(self, url: str) -> RemoteVideoMetadata:
        return RemoteVideoMetadata(url, "video/mp4", 123456, True)


class RejectedInspector:
    async def inspect(self, _url: str) -> RemoteVideoMetadata:
        raise RemoteVideoError("Le serveur ne supporte pas les requêtes HTTP Range.")


def install_validation_override(inspector) -> None:  # type: ignore[no-untyped-def]
    db_override = app.dependency_overrides[get_db]

    def override():
        session_generator = db_override()
        session = next(session_generator)
        try:
            yield VideoValidationService(inspector, VideoRepository(session))
        finally:
            try:
                next(session_generator)
            except StopIteration:
                pass

    app.dependency_overrides[get_validation_service] = override


def test_validate_video_to_ready(client: TestClient) -> None:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    install_validation_override(SuccessfulInspector())

    response = client.post(f"/api/v1/videos/{video_id}/validate")

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["size_bytes"] == 123456
    assert response.json()["accepts_ranges"] is True
    assert response.json()["resolved_video_url"] == VIDEO["video_url"]
    assert client.post(f"/api/v1/videos/{video_id}/validate").status_code == 409


def test_validate_video_to_rejected(client: TestClient) -> None:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    install_validation_override(RejectedInspector())

    response = client.post(f"/api/v1/videos/{video_id}/validate")

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert "Range" in response.json()["error_message"]


def test_validate_unknown_video(client: TestClient) -> None:
    install_validation_override(SuccessfulInspector())
    assert client.post("/api/v1/videos/999/validate").status_code == 404
