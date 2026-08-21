from datetime import UTC, datetime, timedelta

import jwt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.core.jwt_authentication_middleware as jwt_authentication_middleware
import app.core.authentication as authentication_module

from app.core.config import Settings

from app.db.base import Base
from app.db.models import User, UserRole

from app.api.auth import get_login_rate_limiter
from app.services.login_rate_limiter import LoginRateLimitState

from app.db.session import build_engine, get_db
from app.main import app


class AllowLoginRateLimiter:
    async def check(self, _client_ip, _settings):
        return LoginRateLimitState.ALLOWED

    async def record_failure(self, _client_ip, _settings):
        return LoginRateLimitState.ALLOWED

    async def reset_failures(self, _client_ip, _settings):
        return None



@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    engine = build_engine(f"sqlite:///{tmp_path / 'api.db'}")
    auth_settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(

        jwt_authentication_middleware,
        "get_settings",
        lambda: auth_settings,
    )
    monkeypatch.setattr(authentication_module, "get_settings", lambda: auth_settings)


    access_token = jwt.encode(
        {
            "sub": "999999",
            "username": "test-user",
            "role": "SUPER_POWER",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        auth_settings.jwt_secret_key,
        algorithm=auth_settings.jwt_algorithm,
    )

    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        session.add(
            User(
                id=999999,
                username="test-user",
                password_hash="not-used-by-jwt-tests",
                role=UserRole.SUPER_POWER,
            )
        )
        session.commit()


    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_login_rate_limiter] = lambda: AllowLoginRateLimiter()

    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {access_token}"

        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()

