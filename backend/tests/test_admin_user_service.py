import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User, UserRole
from app.db.session import build_engine
from app.repositories.user_repository import UserRepository
from app.services.admin_user_service import (
    AdminUserService,
    SelfAdministrationError,
)
from app.services.password_service import PasswordService


def build_service(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    passwords = PasswordService(rounds=4)
    repository = UserRepository(session)
    admin = repository.create(
        User(
            username="admin",
            password_hash=passwords.hash("admin-password"),
            role=UserRole.SUPER_POWER,
        )
    )
    return engine, session, repository, passwords, admin, AdminUserService(repository, passwords)


def test_admin_creates_and_updates_user(tmp_path) -> None:
    engine, session, _repository, passwords, admin, service = build_service(tmp_path)

    user = service.create(
        username="guest",
        password="guest-password",
        role=UserRole.GUEST,
    )
    updated = service.update(
        actor=admin,
        user_id=user.id,
        role=UserRole.SUPER_POWER,
        is_active=False,
    )

    assert updated.role == UserRole.SUPER_POWER
    assert updated.is_active is False
    assert passwords.verify("guest-password", updated.password_hash)

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_admin_cannot_deactivate_or_delete_itself(tmp_path) -> None:
    engine, session, _repository, _passwords, admin, service = build_service(tmp_path)

    with pytest.raises(SelfAdministrationError, match="désactiver"):
        service.update(
            actor=admin,
            user_id=admin.id,
            role=None,
            is_active=False,
        )
    with pytest.raises(SelfAdministrationError, match="supprimer"):
        service.delete(actor=admin, user_id=admin.id)

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()

