from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.core.config import Settings
from app.db.base import Base
from app.db.session import build_engine
from app.repositories.user_repository import UserRepository


def test_startup_creates_configured_super_power(tmp_path, monkeypatch) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'startup.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        bcrypt_rounds=10,
        initial_super_power_username="admin",
        initial_super_power_password="mot-de-passe-initial",
    )

    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)

    with TestClient(main_module.app):
        pass

    with session_factory() as session:
        user = UserRepository(session).get_by_username("admin")

    assert user is not None
    assert user.role.value == "SUPER_POWER"

    Base.metadata.drop_all(engine)
    engine.dispose()

