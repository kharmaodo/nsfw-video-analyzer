from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import OAuthAccount, User
from app.db.session import build_engine
from app.repositories.oauth_account_repository import OAuthAccountRepository


def test_creates_and_reads_oauth_account(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        user = User(username="oauth-user", password_hash="unused")
        session.add(user)
        session.commit()

        repository = OAuthAccountRepository(session)
        created = repository.create(
            OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_subject="google-subject-123",
                provider_email="oauth@example.test",
            )
        )

        by_subject = repository.get_by_provider_subject(
            "google",
            "google-subject-123",
        )
        by_user = repository.get_by_user_provider(user.id, "google")

        assert created.id is not None
        assert by_subject is not None
        assert by_subject.id == created.id
        assert by_user is not None
        assert by_user.id == created.id

    Base.metadata.drop_all(engine)
    engine.dispose()


