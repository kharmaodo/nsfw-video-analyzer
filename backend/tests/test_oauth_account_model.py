import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import OAuthAccount, User
from app.db.session import build_engine


def test_provider_subject_is_unique_across_users(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        first = User(username="first", password_hash="hash")
        second = User(username="second", password_hash="hash")
        session.add_all([first, second])
        session.commit()
        session.add(
            OAuthAccount(
                user_id=first.id,
                provider="google",
                provider_subject="google-subject-1",
                provider_email="first@example.test",
            )
        )
        session.commit()

        session.add(
            OAuthAccount(
                user_id=second.id,
                provider="google",
                provider_subject="google-subject-1",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    Base.metadata.drop_all(engine)
    engine.dispose()

