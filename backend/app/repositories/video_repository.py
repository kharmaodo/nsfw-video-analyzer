from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import Video, VideoStatus


class VideoRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, video: Video) -> Video:
        self.session.add(video)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(video)
        return video

    def create_discovered(
        self,
        *,
        page_url: str,
        candidates: list[tuple[str, str]],
    ) -> tuple[list[Video], int]:
        urls = [video_url for _, video_url in candidates]
        existing = set(
            self.session.scalars(select(Video.video_url).where(Video.video_url.in_(urls))).all()
        ) if urls else set()
        created = [
            Video(title=title, page_url=page_url, video_url=video_url)
            for title, video_url in candidates
            if video_url not in existing
        ]
        self.session.add_all(created)
        self.session.commit()
        for video in created:
            self.session.refresh(video)
        return created, len(candidates) - len(created)

    def get(self, video_id: int) -> Video | None:
        return self.session.get(Video, video_id)

    def list(
        self,
        *,
        offset: int,
        limit: int,
        status: VideoStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Video], int]:
        filters = []
        if status is not None:
            filters.append(Video.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Video.title.ilike(pattern), Video.video_url.ilike(pattern)))

        query = select(Video).where(*filters)
        count_query = select(func.count(Video.id)).where(*filters)
        items = self.session.scalars(
            query.order_by(Video.created_at.desc(), Video.id.desc()).offset(offset).limit(limit)
        ).all()
        total = self.session.scalar(count_query) or 0
        return list(items), total

    def save(self, video: Video) -> Video:
        self.session.commit()
        self.session.refresh(video)
        return video

    def mark_queued(self, video_id: int) -> Video | None:
        result = self.session.execute(
            update(Video)
            .where(Video.id == video_id, Video.status == VideoStatus.READY)
            .values(status=VideoStatus.QUEUED, error_message=None)
        )
        self.session.commit()
        if result.rowcount != 1:
            return None
        return self.get(video_id)

    def delete(self, video: Video) -> None:
        self.session.delete(video)
        self.session.commit()
