from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.videos import get_sampling_service
from app.db.session import get_db
from app.main import app
from app.repositories.video_repository import VideoRepository
from app.services.video_processor import SampleWindow, VideoSample
from app.services.video_sampling_service import VideoSamplingService


VIDEO = {
    "title": "Vidéo prête",
    "page_url": "https://media.example/catalogue",
    "video_url": "https://cdn.example/video.mp4",
}


class FakeProcessor:
    async def extract_central_frames(self, video_id: int, _url: str) -> VideoSample:
        frames = tuple(Path(f"frame-{index}.jpg") for index in range(3))
        return VideoSample(1200, SampleWindow(450, 300), frames)


def install_sampling_override() -> None:
    db_override = app.dependency_overrides[get_db]

    def override():
        session_generator = db_override()
        session = next(session_generator)
        try:
            yield VideoSamplingService(FakeProcessor(), VideoRepository(session))  # type: ignore[arg-type]
        finally:
            try:
                next(session_generator)
            except StopIteration:
                pass

    app.dependency_overrides[get_sampling_service] = override


def test_sample_ready_video(client: TestClient) -> None:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    client.patch(f"/api/v1/videos/{video_id}/status", json={"status": "VALIDATING"})
    client.patch(f"/api/v1/videos/{video_id}/status", json={"status": "READY"})
    install_sampling_override()

    response = client.post(f"/api/v1/videos/{video_id}/sample")

    assert response.status_code == 200
    assert response.json()["source_duration_seconds"] == 1200
    assert response.json()["sample_start_seconds"] == 450
    assert response.json()["frame_count"] == 3
    assert response.json()["video"]["sampled_frames"] == 3


def test_sample_requires_ready_status(client: TestClient) -> None:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    install_sampling_override()
    assert client.post(f"/api/v1/videos/{video_id}/sample").status_code == 409


def test_sample_unknown_video(client: TestClient) -> None:
    install_sampling_override()
    assert client.post("/api/v1/videos/999/sample").status_code == 404

