import pytest

from app.core.config import Settings
from app.services.oauth_link_code_store import OAuthLinkCodeStore


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


@pytest.mark.asyncio
async def test_issues_and_consumes_link_code_once() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_link_code_ttl_seconds=300,
    )
    store = OAuthLinkCodeStore(settings, redis=FakeRedis())

    code = await store.issue(user_id=7, provider="Google")
    first = await store.consume(code)
    second = await store.consume(code)

    assert first is not None
    assert first.user_id == 7
    assert first.provider == "google"
    assert second is None


@pytest.mark.asyncio
async def test_rejects_invalid_link_intent() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    store = OAuthLinkCodeStore(settings, redis=FakeRedis())

    with pytest.raises(ValueError, match="invalide"):
        await store.issue(user_id=0, provider="google")
