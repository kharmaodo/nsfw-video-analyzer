from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User, UserRole, Video
from app.db.session import build_engine
from app.repositories.video_repository import VideoRepository


def create_users(session) -> None:
    session.add_all(
        [
            User(
                id=7,
                username="guest-7",
                password_hash="hash",
                role=UserRole.GUEST,
            ),
            User(
                id=8,
                username="guest-8",
                password_hash="hash",
                role=UserRole.GUEST,
            ),
        ]
    )
    session.commit()



def video(title: str, owner_user_id: int | None) -> Video:
    return Video(
        title=title,
        page_url=f"https://example.test/{title}",
        video_url=f"https://cdn.example.test/{title}.mp4",
        owner_user_id=owner_user_id,
    )


def test_lists_only_owned_media_when_owner_filter_is_given(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'ownership.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        repository = VideoRepository(session)
        create_users(session)

        repository.create(video("mine", owner_user_id=7))
        repository.create(video("other", owner_user_id=8))
        repository.create(video("legacy", owner_user_id=None))

        items, total = repository.list(
            offset=0,
            limit=20,
            owner_user_id=7,
        )

        assert total == 1
        assert [item.title for item in items] == ["mine"]

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_lists_all_media_without_owner_filter(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'ownership.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine)() as session:
        repository = VideoRepository(session)
        create_users(session)

        repository.create(video("mine", owner_user_id=7))
        repository.create(video("legacy", owner_user_id=None))

        _, total = repository.list(offset=0, limit=20)

        assert total == 2

    Base.metadata.drop_all(engine)
    engine.dispose()

