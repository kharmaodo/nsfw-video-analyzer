import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.models import UserRole
from app.db.session import build_engine
from app.repositories.user_repository import UserRepository
from app.services.initial_user_service import (
    InitialUserConfigurationError,
    InitialUserService,
)
from app.services.password_service import PasswordService


def test_creates_initial_super_power_once(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        repository = UserRepository(session)
        service = InitialUserService(
            Settings(
                bcrypt_rounds=10,
                initial_super_power_username="admin",
                initial_super_power_password="mot-de-passe-initial",
            ),
            repository,
            PasswordService(rounds=4),
        )
        created = service.ensure_super_power()
        repeated = service.ensure_super_power()

        assert created is not None
        assert created.role == UserRole.SUPER_POWER
        assert repeated is not None
        assert repeated.id == created.id
        assert PasswordService(rounds=4).verify(
            "mot-de-passe-initial",
            created.password_hash,
        )

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_does_nothing_without_initial_credentials(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine)() as session:
        service = InitialUserService(
            Settings(bcrypt_rounds=10),
            UserRepository(session),
            PasswordService(rounds=4),
        )
        assert service.ensure_super_power() is None

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_rejects_partial_initial_credentials(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine)() as session:
        service = InitialUserService(
            Settings(
                bcrypt_rounds=10,
                initial_super_power_username="admin",
            ),
            UserRepository(session),
            PasswordService(rounds=4),
        )
        with pytest.raises(InitialUserConfigurationError, match="requis ensemble"):
            service.ensure_super_power()

    Base.metadata.drop_all(engine)
    engine.dispose()

