from collections.abc import Callable
from enum import Enum
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import Settings


class AsyncRedisClient(Protocol):
    async def get(self, name: str): ...
    async def incr(self, name: str): ...
    async def expire(self, name: str, time: int, nx: bool = False): ...
    async def set(self, name: str, value: str, ex: int): ...
    async def delete(self, *names: str): ...
    async def aclose(self): ...


class LoginRateLimitState(str, Enum):
    ALLOWED = "ALLOWED"
    IP_BLOCKED = "IP_BLOCKED"
    GLOBAL_BLOCKED = "GLOBAL_BLOCKED"


class LoginRateLimiterUnavailableError(RuntimeError):
    pass


class LoginRateLimiter:
    def __init__(
        self,
        redis_factory: Callable[[str], AsyncRedisClient] = Redis.from_url,
    ) -> None:
        self.redis_factory = redis_factory

    async def check(self, client_ip: str, settings: Settings) -> LoginRateLimitState:
        client = self.redis_factory(settings.celery_broker_url)
        try:
            if await client.get(self._blocked_key(client_ip)):
                return LoginRateLimitState.IP_BLOCKED

            count = int(await client.incr(self._global_key()))
            await client.expire(
                self._global_key(),
                settings.auth_global_window_seconds,
                nx=True,
            )
            if count > settings.auth_global_max_attempts:
                return LoginRateLimitState.GLOBAL_BLOCKED
            return LoginRateLimitState.ALLOWED
        except Exception as exc:
            raise LoginRateLimiterUnavailableError(
                "Le limiteur de connexion est indisponible."
            ) from exc
        finally:
            await client.aclose()

    async def record_failure(
        self,
        client_ip: str,
        settings: Settings,
    ) -> LoginRateLimitState:
        client = self.redis_factory(settings.celery_broker_url)
        try:
            failures_key = self._failures_key(client_ip)
            failures = int(await client.incr(failures_key))
            await client.expire(
                failures_key,
                settings.auth_login_window_seconds,
                nx=True,
            )
            if failures >= settings.auth_login_max_failures:
                await client.set(
                    self._blocked_key(client_ip),
                    "1",
                    ex=settings.auth_login_block_seconds,
                )
                return LoginRateLimitState.IP_BLOCKED
            return LoginRateLimitState.ALLOWED
        except Exception as exc:
            raise LoginRateLimiterUnavailableError(
                "Le limiteur de connexion est indisponible."
            ) from exc
        finally:
            await client.aclose()

    async def reset_failures(self, client_ip: str, settings: Settings) -> None:
        client = self.redis_factory(settings.celery_broker_url)
        try:
            await client.delete(
                self._failures_key(client_ip),
                self._blocked_key(client_ip),
            )
        except Exception as exc:
            raise LoginRateLimiterUnavailableError(
                "Le limiteur de connexion est indisponible."
            ) from exc
        finally:
            await client.aclose()

    @staticmethod
    def _global_key() -> str:
        return "auth:login:global"

    @staticmethod
    def _failures_key(client_ip: str) -> str:
        return f"auth:login:failures:{client_ip}"

    @staticmethod
    def _blocked_key(client_ip: str) -> str:
        return f"auth:login:blocked:{client_ip}"

