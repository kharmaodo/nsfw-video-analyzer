from fastapi.testclient import TestClient

from app.api.v1.scraping import get_scraping_service
from app.db.session import get_db
from app.main import app
from app.repositories.video_repository import VideoRepository
from app.services.scraper import DiscoveredVideo
from app.services.scraping_service import ScrapingService


class FakeScraper:
    async def discover(self, page_url: str):
        return page_url, [
            DiscoveredVideo("Vidéo A", "https://cdn.example/a.mp4"),
            DiscoveredVideo("Vidéo B", "https://cdn.example/b.webm"),
        ]


def test_discover_endpoint_persists_and_deduplicates(client: TestClient) -> None:
    db_override = app.dependency_overrides[get_db]

    def override_scraping_service():
        session_generator = db_override()
        session = next(session_generator)
        try:
            yield ScrapingService(FakeScraper(), VideoRepository(session))  # type: ignore[arg-type]
        finally:
            try:
                next(session_generator)
            except StopIteration:
                pass

    app.dependency_overrides[get_scraping_service] = override_scraping_service
    payload = {"page_url": "https://media.example/catalogue"}

    first = client.post("/api/v1/scraping/discover", json=payload)
    assert first.status_code == 201
    assert first.json()["discovered"] == 2
    assert first.json()["created"] == 2
    assert first.json()["duplicates"] == 0

    second = client.post("/api/v1/scraping/discover", json=payload)
    assert second.status_code == 201
    assert second.json()["created"] == 0
    assert second.json()["duplicates"] == 2

    listing = client.get("/api/v1/videos")
    assert listing.json()["total"] == 2

