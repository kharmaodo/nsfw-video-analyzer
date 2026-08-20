from fastapi import APIRouter

from app.api.v1.media import router as media_router

from app.api.v1.scraping import router as scraping_router
from app.api.v1.videos import router as videos_router

router = APIRouter(prefix="/api/v1")
router.include_router(media_router)
router.include_router(scraping_router)
router.include_router(videos_router)

