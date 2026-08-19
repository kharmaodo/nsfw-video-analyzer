from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.video_repository import VideoRepository
from app.schemas.scraping import ScrapeRequest, ScrapeResponse
from app.services.scraper import PageFetcher, Scraper, ScrapingError
from app.services.scraping_service import ScrapingService
from app.services.url_security import UnsafeUrlError

router = APIRouter(prefix="/scraping", tags=["scraping"])


def get_scraping_service(db: Annotated[Session, Depends(get_db)]) -> ScrapingService:
    return ScrapingService(
        scraper=Scraper(PageFetcher(get_settings())),
        repository=VideoRepository(db),
    )


@router.post("/discover", response_model=ScrapeResponse, status_code=status.HTTP_201_CREATED)
async def discover_videos(
    payload: ScrapeRequest,
    service: Annotated[ScrapingService, Depends(get_scraping_service)],
) -> ScrapeResponse:
    try:
        return await service.scrape(str(payload.page_url))
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScrapingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

