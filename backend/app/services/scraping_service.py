from app.repositories.video_repository import VideoRepository
from app.schemas.scraping import ScrapeResponse
from app.services.scraper import Scraper


class ScrapingService:
    def __init__(self, scraper: Scraper, repository: VideoRepository) -> None:
        self.scraper = scraper
        self.repository = repository

    async def scrape(
        self,
        page_url: str,
        owner_user_id: int | None = None,
    ) -> ScrapeResponse:
        final_url, discovered = await self.scraper.discover(page_url)
        created, duplicates = self.repository.create_discovered(
            page_url=final_url,
            candidates=[(item.title, item.video_url) for item in discovered],
            owner_user_id=owner_user_id,

        )
        return ScrapeResponse(
            page_url=final_url,
            discovered=len(discovered),
            created=len(created),
            duplicates=duplicates,
            videos=created,
        )

