from app.api.auth import get_login_rate_limiter
from app.main import app
from app.services.login_rate_limiter import LoginRateLimitState


class GlobalLockedLoginRateLimiter:
    async def check(self, _client_ip, _settings):
        return LoginRateLimitState.GLOBAL_BLOCKED

    async def record_failure(self, _client_ip, _settings):
        return LoginRateLimitState.GLOBAL_BLOCKED

    async def reset_failures(self, _client_ip, _settings):
        return None


def test_login_returns_429_when_global_lock_is_active(client) -> None:
    app.dependency_overrides[get_login_rate_limiter] = (
        lambda: GlobalLockedLoginRateLimiter()
    )

    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "mot-de-passe"},
    )

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Trop de tentatives de connexion. Réessayez plus tard."
    }

