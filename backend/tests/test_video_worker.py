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


class LocalVideoProcessor:
    def __init__(self, temporary_directory: Path) -> None:
        self.temporary_directory = temporary_directory
        self.received_source: Path | None = None

    async def extract_central_frames(
        self,
        video_id: int,
        source: Path,
    ) -> VideoSample:
        self.received_source = source
        frame_directory = self.temporary_directory / f"video-{video_id}"
        frame_directory.mkdir(parents=True)
        frames = (
            frame_directory / "frame-00001.jpg",
            frame_directory / "frame-00002.jpg",
        )
        for frame in frames:
            frame.write_bytes(b"jpeg")
        return VideoSample(
            source_duration_seconds=20,
            window=SampleWindow(0, 20),
            frame_paths=frames,
        )


@pytest.mark.asyncio
async def test_worker_processes_local_video_and_cleans_frames(
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import Settings
    from app.db.models import MediaType

    engine = build_engine(f"sqlite:///{tmp_path / 'worker-local-video.db'}")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    storage = tmp_path / "media"
    storage.mkdir()
    local_video = storage / "saved.mp4"
    local_video.write_bytes(b"video")

    temporary_directory = tmp_path / "temporary"
    worker_settings = Settings(
        media_storage_directory=str(storage),
        video_temporary_directory=str(temporary_directory),
        nsfw_cleanup_frames=True,
    )
    processor = LocalVideoProcessor(temporary_directory)

    monkeypatch.setattr(video_tasks, "SessionLocal", local_session)
    monkeypatch.setattr(video_tasks, "settings", worker_settings)

    with local_session() as session:
        video = Video(
            title="Vidéo locale",
            page_url="local://saved.mp4",
            video_url="local://saved.mp4",
            media_type=MediaType.VIDEO,
            storage_path="saved.mp4",
            status=VideoStatus.QUEUED,
        )
        session.add(video)
        session.commit()
        video_id = video.id

    result = await video_tasks.process_queued_video(
        video_id,
        processor,  # type: ignore[arg-type]
        FakeClassifier(),
    )

    assert processor.received_source == local_video.resolve()
    assert result["sampled_frames"] == 2
    assert not (temporary_directory / f"video-{video_id}").exists()

    with local_session() as session:
        saved = session.get(Video, video_id)
        assert saved is not None
        assert saved.status == VideoStatus.SAMPLED_NSFW
        assert saved.duration_seconds == 20
        assert saved.sampled_frames == 2

    engine.dispose()


def test_cleanup_sample_frames_keeps_files_outside_temporary_directory(
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import Settings

    temporary_directory = tmp_path / "temporary"
    frame_directory = temporary_directory / "video-1"
    frame_directory.mkdir(parents=True)
    local_frame = frame_directory / "frame-00001.jpg"
    local_frame.write_bytes(b"jpeg")

    external_frame = tmp_path / "external.jpg"
    external_frame.write_bytes(b"jpeg")

    monkeypatch.setattr(
        video_tasks,
        "settings",
        Settings(video_temporary_directory=str(temporary_directory)),
    )

    video_tasks.cleanup_sample_frames((local_frame, external_frame))

    assert not local_frame.exists()
    assert not frame_directory.exists()
    assert external_frame.exists()


def test_worker_requeues_queued_media_on_startup(tmp_path, monkeypatch) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(video_tasks, "SessionLocal", local_session)

    with local_session() as session:
        video = Video(
            title="À reprendre",
            page_url="https://media.example",
            video_url="https://cdn.example/recovery.mp4",
            status=VideoStatus.QUEUED,
        )
        session.add(video)
        session.commit()
        video_id = video.id

    dispatched: list[int] = []

    class RecoveryTask:
        id = "recovered-task-123"

    class RecoveryDispatcher:
        @staticmethod
        def delay(media_id: int) -> RecoveryTask:
            dispatched.append(media_id)
            return RecoveryTask()

    monkeypatch.setattr(video_tasks, "process_video_task", RecoveryDispatcher)

    assert video_tasks.recover_queued_media() == 1
    assert dispatched == [video_id]

    with local_session() as session:
        recovered = session.get(Video, video_id)
        assert recovered is not None
        assert recovered.status == VideoStatus.QUEUED
        assert recovered.task_id == "recovered-task-123"

    engine.dispose()

