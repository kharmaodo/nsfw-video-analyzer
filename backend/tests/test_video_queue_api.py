from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.v1.videos import get_queue_service
from app.db.session import get_db
from app.main import app
from app.repositories.video_repository import VideoRepository
from app.services.video_queue_service import VideoQueueService


VIDEO = {
    "title": "Vidéo à mettre en file",
    "page_url": "https://media.example/catalogue",
    "video_url": "https://cdn.example/queue.mp4",
}


@dataclass
class FakeTask:
    id: str = "task-123"


def install_queue_override(dispatcher) -> None:  # type: ignore[no-untyped-def]
    db_override = app.dependency_overrides[get_db]

    def override():
        session_generator = db_override()
        session = next(session_generator)
        try:
            yield VideoQueueService(VideoRepository(session), dispatcher)
        finally:
            try:
                next(session_generator)
            except StopIteration:
                pass

    app.dependency_overrides[get_queue_service] = override


def create_ready_video(client: TestClient) -> int:
    video_id = client.post("/api/v1/videos", json=VIDEO).json()["id"]
    client.patch(f"/api/v1/videos/{video_id}/status", json={"status": "VALIDATING"})
    client.patch(f"/api/v1/videos/{video_id}/status", json={"status": "READY"})
    return video_id


def test_enqueue_ready_video(client: TestClient) -> None:
    video_id = create_ready_video(client)
    install_queue_override(lambda _video_id: FakeTask())

    response = client.post(f"/api/v1/videos/{video_id}/enqueue")

    assert response.status_code == 202
    assert response.json() == {
        "video_id": video_id,
        "task_id": "task-123",
        "status": "QUEUED",
    }
    video = client.get(f"/api/v1/videos/{video_id}").json()
    assert video["task_id"] == "task-123"
    assert video["status"] == "QUEUED"
    assert client.post(f"/api/v1/videos/{video_id}/enqueue").status_code == 409


def test_enqueue_restores_ready_when_broker_is_down(client: TestClient) -> None:
    video_id = create_ready_video(client)

    def unavailable(_video_id: int):
        raise ConnectionError("Redis down")

    install_queue_override(unavailable)
    response = client.post(f"/api/v1/videos/{video_id}/enqueue")

    assert response.status_code == 503
    assert client.get(f"/api/v1/videos/{video_id}").json()["status"] == "READY"


def test_enqueue_unknown_video(client: TestClient) -> None:
    install_queue_override(lambda _video_id: FakeTask())
    assert client.post("/api/v1/videos/999/enqueue").status_code == 404

def test_requeue_queued_video(client: TestClient) -> None:
    video_id = create_ready_video(client)
    install_queue_override(lambda _video_id: FakeTask("initial-task"))

    queued = client.post(f"/api/v1/videos/{video_id}/enqueue")
    assert queued.status_code == 202

    install_queue_override(lambda _video_id: FakeTask("recovered-task"))
    response = client.post(f"/api/v1/media/{video_id}/requeue")

    assert response.status_code == 202
    assert response.json() == {
        "video_id": video_id,
        "task_id": "recovered-task",
        "status": "QUEUED",
    }
def create_error_video(client) -> int:

    media_id = create_ready_video(client)

    install_queue_override(lambda _media_id: FakeTask("failed-task"))

    assert client.post(f"/api/v1/videos/{media_id}/enqueue").status_code == 202

    response = client.patch(

        f"/api/v1/videos/{media_id}/status",

        json={"status": "ERROR", "error_message": "Analyse interrompue."},

    )

    assert response.status_code == 200

    return media_id





def test_reanalyze_error_media(client) -> None:

    media_id = create_error_video(client)

    install_queue_override(lambda _media_id: FakeTask("retry-task"))



    response = client.post(f"/api/v1/media/{media_id}/reanalyze")



    assert response.status_code == 202

    assert response.json()["task_id"] == "retry-task"

    video = client.get(f"/api/v1/media/{media_id}").json()

    assert video["status"] == "QUEUED"

    assert video["task_id"] == "retry-task"

    assert video["error_message"] is None





def test_reanalyze_requires_error_status(client) -> None:

    media_id = create_ready_video(client)



    response = client.post(f"/api/v1/media/{media_id}/reanalyze")



    assert response.status_code == 409

    assert response.json()["detail"] == (

        "La vidéo doit être au statut ERROR, statut actuel : READY."

    )





def test_reanalyze_restores_error_when_broker_is_down(client) -> None:

    media_id = create_error_video(client)



    def unavailable(_media_id: int):

        raise ConnectionError("broker unavailable")



    install_queue_override(unavailable)

    response = client.post(f"/api/v1/media/{media_id}/reanalyze")



    assert response.status_code == 503

    video = client.get(f"/api/v1/media/{media_id}").json()

    assert video["status"] == "ERROR"

    assert video["error_message"] == "Analyse interrompue."

    assert video["task_id"] is None
