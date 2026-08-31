from types import SimpleNamespace

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.auth import (
    get_audit_service,
    get_facebook_oauth_client,
    get_oauth_exchange_code_store,
    get_oauth_identity_service,
)
from app.core.config import get_settings
from app.db.models import UserRole
from app.main import app
from app.services.oauth_identity_service import OAuthIdentity


class FakeFacebookClient:
    async def authorize_redirect(self, request):
        return JSONResponse({"provider": "facebook"})

    async def fetch_identity(self, request):
        return OAuthIdentity(
            provider="facebook",
            subject="facebook-user-7",
            email="facebook@example.test",
            preferred_username="facebook-user",
        )


class FakeIdentityService:
    def resolve(self, identity):
        return SimpleNamespace(
            id=7,
            username="facebook-user",
            role=UserRole.GUEST,
        )


class FakeExchangeStore:
    def __init__(self) -> None:
        self.response = None

    async def issue(self, response):
        self.response = response
        return "f" * 32

    async def consume(self, code):
        if code != "f" * 32:
            return None
        response = self.response
        self.response = None
        return response


class FakeAuditService:
    def record(self, **kwargs):
        return None


def test_facebook_oauth_routes_and_one_time_exchange(monkeypatch) -> None:
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setenv(
        "OAUTH_FRONTEND_SUCCESS_URL",
        "http://localhost:5173/login",
    )
    get_settings.cache_clear()

    store = FakeExchangeStore()
    app.dependency_overrides[get_facebook_oauth_client] = lambda: FakeFacebookClient()
    app.dependency_overrides[get_oauth_identity_service] = lambda: FakeIdentityService()
    app.dependency_overrides[get_oauth_exchange_code_store] = lambda: store
    app.dependency_overrides[get_audit_service] = lambda: FakeAuditService()

    try:
        with TestClient(app) as client:
            start = client.get("/auth/oauth/facebook/login")
            assert start.status_code == 200
            assert start.json() == {"provider": "facebook"}

            callback = client.get(
                "/auth/oauth/facebook/callback",
                follow_redirects=False,
            )
            assert callback.status_code == 307
            assert callback.headers["location"].endswith(
                "oauth_code=" + ("f" * 32)
            )

            exchanged = client.post(
                "/auth/oauth/exchange",
                json={"code": "f" * 32},
            )
            assert exchanged.status_code == 200
            assert exchanged.json()["user"]["username"] == "facebook-user"

            reused = client.post(
                "/auth/oauth/exchange",
                json={"code": "f" * 32},
            )
            assert reused.status_code == 401
            assert reused.json()["detail"] == "Code OAuth invalide ou expiré."
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
