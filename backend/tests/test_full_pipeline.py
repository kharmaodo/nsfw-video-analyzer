from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.v1.videos import get_queue_service, get_validation_service
from app.db.session import get_db
from app.main import app
from app.repositories.video_repository import VideoRepository
from app.services.remote_video import RemoteVideoMetadata
from app.services.video_queue_service import VideoQueueService
from app.services.video_validation_service import VideoValidationService


class Inspector:
    async def inspect(self, url: str) -> RemoteVideoMetadata:
        return RemoteVideoMetadata(url, "video/mp4", 5_000_000, True)


@dataclass
class Task:
    id: str = "e2e-task"


def test_api_lifecycle_from_creation_to_queue(client: TestClient) -> None:
    db_override = app.dependency_overrides[get_db]

    def validation_override():
        generator = db_override()
        session = next(generator)
        try:
            yield VideoValidationService(Inspector(), VideoRepository(session))  # type: ignore[arg-type]
        finally:
            generator.close()

    def queue_override():
        generator = db_override()
        session = next(generator)
        try:
            yield VideoQueueService(VideoRepository(session), lambda _video_id: Task())
        finally:
            generator.close()

    app.dependency_overrides[get_validation_service] = validation_override
    app.dependency_overrides[get_queue_service] = queue_override

    created = client.post(
        "/api/v1/videos",
        json={
            "title": "Pipeline E2E",
            "page_url": "https://media.example/catalogue",
            "video_url": "https://cdn.example/e2e.mp4",
        },
    )
    assert created.status_code == 201
    video_id = created.json()["id"]

    validated = client.post(f"/api/v1/videos/{video_id}/validate")
    assert validated.status_code == 200
    assert validated.json()["status"] == "READY"

    queued = client.post(f"/api/v1/videos/{video_id}/enqueue")
    assert queued.status_code == 202
    assert queued.json()["task_id"] == "e2e-task"

    final = client.get(f"/api/v1/videos/{video_id}").json()
    assert final["status"] == "QUEUED"
    assert final["content_type"] == "video/mp4"
