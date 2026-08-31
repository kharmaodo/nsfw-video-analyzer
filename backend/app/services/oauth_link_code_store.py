import json
import secrets
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

from app.core.config import Settings


@dataclass(frozen=True)
class OAuthLinkIntent:
    user_id: int
    provider: str


class OAuthLinkCodeStore:
    def __init__(self, settings: Settings, redis: Redis | None = None) -> None:
        self.settings = settings
        self.redis = redis

    async def issue(self, *, user_id: int, provider: str) -> str:
        normalized_provider = provider.strip().lower()
        if user_id <= 0 or not normalized_provider:
            raise ValueError("Intention de liaison OAuth invalide.")

        client, close_after_use = self._client()
        try:
            while True:
                code = secrets.token_urlsafe(32)
                stored = await client.set(
                    self._key(code),
                    json.dumps(
                        asdict(
                            OAuthLinkIntent(
                                user_id=user_id,
                                provider=normalized_provider,
                            )
                        )
                    ),
                    ex=self.settings.oauth_link_code_ttl_seconds,
                    nx=True,
                )
                if stored:
                    return code
        finally:
            if close_after_use:
                await client.aclose()

    async def consume(self, code: str) -> OAuthLinkIntent | None:
        if not code or len(code) > 512:
            return None

        client, close_after_use = self._client()
        try:
            serialized = await client.getdel(self._key(code))
            if serialized is None:
                return None
            if isinstance(serialized, bytes):
                serialized = serialized.decode("utf-8")

            payload = json.loads(serialized)
            intent = OAuthLinkIntent(
                user_id=int(payload["user_id"]),
                provider=str(payload["provider"]).strip().lower(),
            )
            if intent.user_id <= 0 or not intent.provider:
                return None
            return intent
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        finally:
            if close_after_use:
                await client.aclose()

    def _client(self) -> tuple[Redis, bool]:
        if self.redis is not None:
            return self.redis, False
        return Redis.from_url(self.settings.celery_result_backend), True

    @staticmethod
    def _key(code: str) -> str:
        return f"oauth:link:{code}"
