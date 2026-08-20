from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Video, VideoStatus
from app.db.session import build_engine
from app.services.video_processor import SampleWindow, VideoSample
from app.services.nsfw_classifier import NsfwSummary
from app.workers import video_tasks


class FakeProcessor:
    async def extract_central_frames(self, _video_id: int, _url: str) -> VideoSample:
        return VideoSample(
            source_duration_seconds=600,
            window=SampleWindow(150, 300),
            frame_paths=(Path("frame-1.jpg"), Path("frame-2.jpg")),
        )


class FakeClassifier:
    model_identifier = "fake/model@test"

    def classify(self, _frame_paths) -> NsfwSummary:
        return NsfwSummary(
            maximum_score=0.91,
            average_score=0.55,
            positive_frames=1,
            total_frames=2,
            is_nsfw=True,
        )


@pytest.mark.asyncio
async def test_worker_processes_queued_video(tmp_path, monkeypatch) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(video_tasks, "SessionLocal", local_session)
    with local_session() as session:
        video = Video(
            title="Worker",
            page_url="https://media.example",
            video_url="https://cdn.example/worker.mp4",
            status=VideoStatus.QUEUED,
        )
        session.add(video)
        session.commit()
        video_id = video.id

    result = await video_tasks.process_queued_video(  # type: ignore[arg-type]
        video_id, FakeProcessor(), FakeClassifier()
    )

    assert result["sampled_frames"] == 2
    with local_session() as session:
        saved = session.get(Video, video_id)
        assert saved is not None
        assert saved.status == VideoStatus.SAMPLED_NSFW
        assert saved.duration_seconds == 600
        assert saved.sampled_frames == 2
        assert saved.nsfw_score == 0.91
        assert saved.nsfw_positive_frames == 1
        assert saved.nsfw_model == "fake/model@test"
    engine.dispose()


@pytest.mark.asyncio
async def test_worker_processes_local_image_without_url_resolution(
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import Settings
    from app.db.models import MediaType

    engine = build_engine(f"sqlite:///{tmp_path / 'worker-image.db'}")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    storage = tmp_path / "media"
    storage.mkdir()
    (storage / "saved.png").write_bytes(b"image")

    monkeypatch.setattr(video_tasks, "SessionLocal", local_session)
    monkeypatch.setattr(
        video_tasks,
        "settings",
        Settings(media_storage_directory=str(storage)),
    )

    with local_session() as session:
        video = Video(
            title="Image locale",
            page_url="local://saved.png",
            video_url="local://saved.png",
            media_type=MediaType.IMAGE,
            storage_path="saved.png",
            status=VideoStatus.QUEUED,
        )
        session.add(video)
        session.commit()
        video_id = video.id

    result = await video_tasks.process_queued_video(
        video_id,
        FakeProcessor(),
        FakeClassifier(),
    )

    assert result["sampled_frames"] == 1
    with local_session() as session:
        saved = session.get(Video, video_id)
        assert saved is not None
        assert saved.status == VideoStatus.SAMPLED_NSFW
        assert saved.duration_seconds is None
        assert saved.sampled_frames == 1

    engine.dispose()
