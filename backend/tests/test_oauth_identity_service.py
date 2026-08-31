import pytest

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import OAuthAccount, User, UserRole
from app.db.session import build_engine
from app.repositories.oauth_account_repository import OAuthAccountRepository
from app.repositories.user_repository import UserRepository
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError, OAuthIdentityService
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


def test_explicitly_links_identity_to_authenticated_user_only(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth-link.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        owner = User(username="owner", password_hash="unused")
        other_user = User(username="other-user", password_hash="unused")
        session.add_all([owner, other_user])
        session.commit()

        service = OAuthIdentityService(
            UserRepository(session),
            OAuthAccountRepository(session),
            PasswordService(rounds=10),
        )
        identity = OAuthIdentity(
            provider="google",
            subject="google-subject-owner",
            email="owner@example.test",
        )

        linked = service.link(owner, identity)
        repeated = service.link(owner, identity)

        assert linked.id == owner.id
        assert repeated.id == owner.id
        account = OAuthAccountRepository(session).get_by_provider_subject(
            "google",
            "google-subject-owner",
        )
        assert account is not None
        assert account.user_id == owner.id

        with pytest.raises(
            OAuthIdentityError,
            match="déjà liée à un autre compte",
        ):
            service.link(other_user, identity)

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_rejects_link_for_unknown_authenticated_user(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'oauth-link-missing-user.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        service = OAuthIdentityService(
            UserRepository(session),
            OAuthAccountRepository(session),
            PasswordService(rounds=10),
        )

        with pytest.raises(
            OAuthIdentityError,
            match="Utilisateur cible de la liaison OAuth introuvable",
        ):
            service.link_by_user_id(
                999,
                OAuthIdentity(
                    provider="facebook",
                    subject="facebook-subject-unknown",
                ),
            )

    Base.metadata.drop_all(engine)
    engine.dispose()
