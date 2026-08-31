import pytest
from fastapi.responses import JSONResponse

import app.api.auth as auth_api
from app.services.oauth_link_code_store import OAuthLinkIntent


class FakeLinkStore:
    def __init__(self, intent: OAuthLinkIntent | None = None) -> None:
        self.intent = intent
        self.issued: tuple[int, str] | None = None

    async def issue(self, *, user_id: int, provider: str) -> str:
        self.issued = (user_id, provider)
        return "l" * 32

    async def consume(self, code: str) -> OAuthLinkIntent | None:
        if code != "l" * 32:
            return None
        intent = self.intent
        self.intent = None
        return intent


class FakeRequest:
    def __init__(self) -> None:
        self.session: dict[str, object] = {}


class FakeOAuthClient:
    async def authorize_redirect(self, request):
        return JSONResponse({"redirected": True})


def test_authenticated_user_can_create_google_link_code(client) -> None:
    store = FakeLinkStore()
    client.app.dependency_overrides[
        auth_api.get_oauth_link_code_store
    ] = lambda: store

    response = client.post("/auth/oauth/google/link")

    assert response.status_code == 200
    assert response.json() == {"code": "l" * 32}
    assert store.issued == (999999, "google")


def test_link_code_requires_authenticated_user(client) -> None:
    client.headers["Authorization"] = ""

    response = client.post("/auth/oauth/facebook/link")

    assert response.status_code == 401
    assert response.json() == {"detail": "Session expirée."}


@pytest.mark.asyncio
async def test_begin_link_consumes_code_and_stores_signed_session_context() -> None:
    request = FakeRequest()
    store = FakeLinkStore(
        OAuthLinkIntent(user_id=7, provider="google"),
    )

    response = await auth_api.begin_oauth_link(
        "google",
        request,
        "l" * 32,
        FakeOAuthClient(),
        store,
    )

    assert response.status_code == 200
    assert request.session == {
        "oauth_link": {
            "user_id": 7,
            "provider": "google",
        }
    }
    assert await store.consume("l" * 32) is None


@pytest.mark.asyncio
async def test_rejects_expired_or_wrong_provider_link_code() -> None:
    request = FakeRequest()
    store = FakeLinkStore(
        OAuthLinkIntent(user_id=7, provider="facebook"),
    )

    with pytest.raises(Exception) as exc_info:
        await auth_api.begin_oauth_link(
            "google",
            request,
            "l" * 32,
            FakeOAuthClient(),
            store,
        )

    assert getattr(exc_info.value, "status_code", None) == 401
    assert request.session == {}
