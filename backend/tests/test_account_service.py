import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User
from app.db.session import build_engine
from app.repositories.user_repository import UserRepository
from app.services.account_service import (
    AccountService,
    CurrentPasswordInvalidError,
    UsernameAlreadyExistsError,
)
from app.services.password_service import PasswordService


def build_service(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'account.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    passwords = PasswordService(rounds=4)
    repository = UserRepository(session)
    return engine, session, repository, passwords, AccountService(repository, passwords)


def test_updates_username_and_password_when_current_password_is_valid(tmp_path) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    user = repository.create(
        User(username="before", password_hash=passwords.hash("current"))
    )

    updated = service.update(
        user,
        current_password="current",
        username="after",
        new_password="new-password",
    )

    assert updated.username == "after"
    assert passwords.verify("new-password", updated.password_hash)

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_rejects_invalid_current_password(tmp_path) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    user = repository.create(
        User(username="user", password_hash=passwords.hash("current"))
    )

    with pytest.raises(CurrentPasswordInvalidError, match="actuel invalide"):
        service.update(
            user,
            current_password="wrong",
            username="after",
            new_password=None,
        )

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_rejects_existing_username(tmp_path) -> None:
    engine, session, repository, passwords, service = build_service(tmp_path)
    user = repository.create(
        User(username="user", password_hash=passwords.hash("current"))
    )
    repository.create(User(username="taken", password_hash=passwords.hash("other")))

    with pytest.raises(UsernameAlreadyExistsError, match="déjà utilisé"):
        service.update(
            user,
            current_password="current",
            username="taken",
            new_password=None,
        )

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()

