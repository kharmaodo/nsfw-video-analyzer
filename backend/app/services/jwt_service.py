from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings
from app.db.models import User


class JwtConfigurationError(ValueError):
    pass


class InvalidAccessTokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    username: str
    role: str
    expires_at: datetime


class JwtService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_access_token(self, user: User) -> str:
        key = self._secret_key()
        now = datetime.now(UTC)
        expires_at = now + timedelta(
            minutes=self.settings.jwt_access_token_expire_minutes
        )
        return jwt.encode(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "iat": now,
                "exp": expires_at,
            },
            key,
            algorithm=self.settings.jwt_algorithm,
        )

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key(),
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["sub", "username", "role", "exp"]},
            )
            expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
            return AccessTokenClaims(
                user_id=int(payload["sub"]),
                username=str(payload["username"]),
                role=str(payload["role"]),
                expires_at=expires_at,
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError("Jeton d’accès invalide ou expiré.") from exc

    def _secret_key(self) -> str:
        key = self.settings.jwt_secret_key
        if not key or len(key) < 32:
            raise JwtConfigurationError(
                "JWT_SECRET_KEY doit contenir au moins 32 caractères."
            )
        return key

