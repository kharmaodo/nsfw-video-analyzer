import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.models import User, UserRole
from app.db.session import build_engine
from app.repositories.user_repository import UserRepository
from app.services.authentication_service import AuthenticationError, AuthenticationService
from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService


def build_service(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    passwords = PasswordService(rounds=4)
    repository = UserRepository(session)
    service = AuthenticationService(
        repository,
        passwords,
        JwtService(Settings(jwt_secret_key="0123456789abcdef0123456789abcdef")),
    )
    return engine, session, repository, passwords, service


def test_authenticates_active_user_and_updates_login(tmp_path) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    user = repository.create(
        User(
            username="admin",
            password_hash=passwords.hash("mot-de-passe"),
            role=UserRole.SUPER_POWER,
        )
    )

    result = service.authenticate(" admin ", "mot-de-passe")

    assert result.user.id == user.id
    assert result.user.last_login_at is not None
    assert JwtService(
        Settings(jwt_secret_key="0123456789abcdef0123456789abcdef")
    ).decode_access_token(result.access_token).user_id == user.id

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.parametrize("username,password", [("inconnu", "secret"), ("admin", "incorrect")])
def test_rejects_invalid_credentials(tmp_path, username: str, password: str) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    repository.create(
        User(username="admin", password_hash=passwords.hash("secret"))
    )

    with pytest.raises(AuthenticationError, match="Identifiants invalides"):
        service.authenticate(username, password)

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_rejects_inactive_user(tmp_path) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    repository.create(
        User(
            username="inactive",
            password_hash=passwords.hash("secret"),
            is_active=False,
        )
    )

    with pytest.raises(AuthenticationError, match="Identifiants invalides"):
        service.authenticate("inactive", "secret")

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()

