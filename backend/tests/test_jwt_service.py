from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.db.models import User, UserRole
from app.services.jwt_service import (
    InvalidAccessTokenError,
    JwtConfigurationError,
    JwtService,
)


def jwt_settings() -> Settings:
    return Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        jwt_access_token_expire_minutes=30,
    )


def test_creates_and_decodes_access_token() -> None:
    service = JwtService(jwt_settings())
    user = User(
        id=42,
        username="admin",
        password_hash="$2b$fake-hash",
        role=UserRole.SUPER_POWER,
    )

    token = service.create_access_token(user)
    claims = service.decode_access_token(token)

    assert claims.user_id == 42
    assert claims.username == "admin"
    assert claims.role == "SUPER_POWER"
    assert claims.expires_at > datetime.now(UTC)


def test_rejects_expired_access_token() -> None:
    settings = jwt_settings()
    token = jwt.encode(
        {
            "sub": "42",
            "username": "admin",
            "role": "SUPER_POWER",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidAccessTokenError, match="invalide ou expiré"):
        JwtService(settings).decode_access_token(token)


def test_rejects_missing_or_short_secret() -> None:
    user = User(id=1, username="guest", password_hash="hash", role=UserRole.GUEST)

    with pytest.raises(JwtConfigurationError, match="32 caractères"):
        JwtService(Settings(jwt_secret_key="trop-court")).create_access_token(user)

