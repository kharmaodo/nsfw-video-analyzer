import secrets

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.auth import LoginResponse


class OAuthExchangeCodeStore:
    def __init__(self, settings: Settings, redis: Redis | None = None) -> None:
        self.settings = settings
        self.redis = redis

    async def issue(self, response: LoginResponse) -> str:
        client, close_after_use = self._client()
        try:
            while True:
                code = secrets.token_urlsafe(32)
                stored = await client.set(
                    self._key(code),
                    response.model_dump_json(),
                    ex=self.settings.oauth_exchange_code_ttl_seconds,
                    nx=True,
                )
                if stored:
                    return code
        finally:
            if close_after_use:
                await client.aclose()

    async def consume(self, code: str) -> LoginResponse | None:
        if not code or len(code) > 512:
            return None
        client, close_after_use = self._client()
        try:
            serialized = await client.getdel(self._key(code))
            if serialized is None:
                return None
            if isinstance(serialized, bytes):
                serialized = serialized.decode("utf-8")
            return LoginResponse.model_validate_json(serialized)
        finally:
            if close_after_use:
                await client.aclose()

    def _client(self) -> tuple[Redis, bool]:
        if self.redis is not None:
            return self.redis, False
        return Redis.from_url(self.settings.celery_result_backend), True

    @staticmethod
    def _key(code: str) -> str:
        return f"oauth:exchange:{code}"


