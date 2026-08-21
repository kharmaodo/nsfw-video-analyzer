import pytest

from app.core.config import Settings
from app.services.login_rate_limiter import (
    LoginRateLimiter,
    LoginRateLimitState,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str):
        return self.values.get(name)

    async def incr(self, name: str):
        value = int(self.values.get(name, "0")) + 1
        self.values[name] = str(value)
        return value

    async def expire(self, name: str, time: int, nx: bool = False):
        return True

    async def set(self, name: str, value: str, ex: int):
        self.values[name] = value
        return True

    async def delete(self, *names: str):
        for name in names:
            self.values.pop(name, None)
        return len(names)

    async def aclose(self):
        return None


def settings() -> Settings:
    return Settings(
        auth_login_max_failures=2,
        auth_login_window_seconds=60,
        auth_login_block_seconds=60,
        auth_global_max_attempts=2,
        auth_global_window_seconds=60,
    )


@pytest.mark.asyncio
async def test_blocks_ip_after_configured_failed_attempts() -> None:
    redis = FakeRedis()
    limiter = LoginRateLimiter(redis_factory=lambda _url: redis)

    assert await limiter.record_failure("203.0.113.10", settings()) == LoginRateLimitState.ALLOWED
    assert await limiter.record_failure("203.0.113.10", settings()) == LoginRateLimitState.IP_BLOCKED
    assert await limiter.check("203.0.113.10", settings()) == LoginRateLimitState.IP_BLOCKED


@pytest.mark.asyncio
async def test_applies_global_lock_after_rate_is_exceeded() -> None:
    redis = FakeRedis()
    limiter = LoginRateLimiter(redis_factory=lambda _url: redis)

    assert await limiter.check("203.0.113.10", settings()) == LoginRateLimitState.ALLOWED
    assert await limiter.check("203.0.113.11", settings()) == LoginRateLimitState.ALLOWED
    assert await limiter.check("203.0.113.12", settings()) == LoginRateLimitState.GLOBAL_BLOCKED


@pytest.mark.asyncio
async def test_successful_login_can_reset_ip_failures() -> None:
    redis = FakeRedis()
    limiter = LoginRateLimiter(redis_factory=lambda _url: redis)

    await limiter.record_failure("203.0.113.10", settings())
    await limiter.reset_failures("203.0.113.10", settings())

    assert await limiter.check("203.0.113.10", settings()) == LoginRateLimitState.ALLOWED

