import pytest

from app.core.config import Settings
from app.schemas.auth import AuthenticatedUserRead, LoginResponse
from app.db.models import UserRole
from app.services.oauth_exchange_code_store import OAuthExchangeCodeStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key, value, ex, nx):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def getdel(self, key):
        return self.values.pop(key, None)


def login_response() -> LoginResponse:
    return LoginResponse(
        access_token="internal-jwt",
        expires_in=1800,
        user=AuthenticatedUserRead(
            id=7,
            username="oauth-user",
            role=UserRole.GUEST,
        ),
    )


@pytest.mark.asyncio

async def test_exchanges_code_once() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_exchange_code_ttl_seconds=60,
    )
    store = OAuthExchangeCodeStore(settings, redis=FakeRedis())

    code = await store.issue(login_response())
    first = await store.consume(code)
    second = await store.consume(code)

    assert first is not None
    assert first.access_token == "internal-jwt"
    assert second is None


