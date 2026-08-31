from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import OAuthAccount, User, UserRole
from app.db.session import build_engine
from app.repositories.oauth_account_repository import OAuthAccountRepository
from app.repositories.user_repository import UserRepository
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityService
from app.services.password_service import PasswordService


def test_creates_guest_and_reuses_existing_oauth_identity(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth-identity.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        service = OAuthIdentityService(
            UserRepository(session),
            OAuthAccountRepository(session),
            PasswordService(rounds=10),
        )
        identity = OAuthIdentity(
            provider="google",
            subject="subject-123",
            email="maodo@example.test",
        )

        created = service.resolve(identity)
        resolved = service.resolve(identity)

        assert created.id == resolved.id
        assert created.role == UserRole.GUEST
        assert created.username == "maodo"
        assert session.scalar(select(func.count(User.id))) == 1
        assert session.scalar(select(func.count(OAuthAccount.id))) == 1

    Base.metadata.drop_all(engine)
    engine.dispose()




def test_does_not_merge_users_from_different_providers_sharing_an_email(
    tmp_path,
) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth-email-isolation.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as session:
        service = OAuthIdentityService(
            UserRepository(session),
            OAuthAccountRepository(session),
            PasswordService(rounds=10),
        )

        google_user = service.resolve(
            OAuthIdentity(
                provider="google",
                subject="google-subject-1",
                email="shared@example.test",
            )
        )
        facebook_user = service.resolve(
            OAuthIdentity(
                provider="facebook",
                subject="facebook-subject-1",
                email="shared@example.test",
            )
        )

        assert google_user.id != facebook_user.id
        assert google_user.username == "shared"
        assert facebook_user.username == "shared-2"
        assert session.scalar(select(func.count(User.id))) == 2
        assert session.scalar(select(func.count(OAuthAccount.id))) == 2

    Base.metadata.drop_all(engine)
    engine.dispose()
