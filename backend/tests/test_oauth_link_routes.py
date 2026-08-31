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

from types import SimpleNamespace

from app.core.config import Settings
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError


class FakeCallbackRequest:
    def __init__(self, session) -> None:
        self.session = session
        self.client = SimpleNamespace(host="testclient")


class FakeCallbackClient:
    async def fetch_identity(self, request):
        return OAuthIdentity(
            provider="google",
            subject="google-linked-subject",
            email="linked@example.test",
        )


class FakeCallbackIdentityService:
    def __init__(self) -> None:
        self.linked_user_id = None

    def resolve(self, identity):
        raise AssertionError("Une liaison ne doit pas créer de compte invité.")

    def link_by_user_id(self, user_id, identity):
        self.linked_user_id = user_id
        return SimpleNamespace(id=user_id, username="linked-user")


class RejectingCallbackIdentityService(FakeCallbackIdentityService):
    def link_by_user_id(self, user_id, identity):
        raise OAuthIdentityError("Identité déjà liée.")


class FakeExchangeStore:
    async def issue(self, response):
        raise AssertionError("Une liaison ne doit pas créer de JWT.")


class FakeAuditService:
    def __init__(self) -> None:
        self.calls = []

    def record(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_callback_links_identity_to_user_saved_in_session(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="0123456789abcdef0123456789abcdef",
            oauth_frontend_link_success_url="http://localhost:5173/settings",
        ),
    )
    identity_service = FakeCallbackIdentityService()
    audit_service = FakeAuditService()
    request = FakeCallbackRequest(
        {"oauth_link": {"user_id": 7, "provider": "google"}}
    )

    response = await auth_api.complete_oauth_login(
        "google",
        request,
        FakeCallbackClient(),
        identity_service,
        FakeExchangeStore(),
        audit_service,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://localhost:5173/settings"
        "?oauth_link=success&provider=google"
    )
    assert identity_service.linked_user_id == 7
    assert request.session == {}
    assert audit_service.calls[0]["action"] == "AUTH_OAUTH_GOOGLE_LINK_SUCCESS"


@pytest.mark.asyncio
async def test_callback_redirects_to_settings_when_link_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="0123456789abcdef0123456789abcdef",
            oauth_frontend_link_success_url="http://localhost:5173/settings",
        ),
    )
    request = FakeCallbackRequest(
        {"oauth_link": {"user_id": 7, "provider": "google"}}
    )

    response = await auth_api.complete_oauth_login(
        "google",
        request,
        FakeCallbackClient(),
        RejectingCallbackIdentityService(),
        FakeExchangeStore(),
        FakeAuditService(),
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://localhost:5173/settings"
        "?oauth_link=error&provider=google"
    )
    assert request.session == {}

from types import SimpleNamespace

from app.core.config import Settings
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError


class FakeCallbackRequest:
    def __init__(self, session) -> None:
        self.session = session
        self.client = SimpleNamespace(host="testclient")


class FakeCallbackClient:
    async def fetch_identity(self, request):
        return OAuthIdentity(
            provider="google",
            subject="google-linked-subject",
            email="linked@example.test",
        )


class FakeCallbackIdentityService:
    def __init__(self) -> None:
        self.linked_user_id = None

    def resolve(self, identity):
        raise AssertionError("Une liaison ne doit pas créer de compte invité.")

    def link_by_user_id(self, user_id, identity):
        self.linked_user_id = user_id
        return SimpleNamespace(id=user_id, username="linked-user")


class RejectingCallbackIdentityService(FakeCallbackIdentityService):
    def link_by_user_id(self, user_id, identity):
        raise OAuthIdentityError("Identité déjà liée.")


class FakeExchangeStore:
    async def issue(self, response):
        raise AssertionError("Une liaison ne doit pas créer de JWT.")


class FakeAuditService:
    def __init__(self) -> None:
        self.calls = []

    def record(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_callback_links_identity_to_user_saved_in_session(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="0123456789abcdef0123456789abcdef",
            oauth_frontend_link_success_url="http://localhost:5173/settings",
        ),
    )
    identity_service = FakeCallbackIdentityService()
    audit_service = FakeAuditService()
    request = FakeCallbackRequest(
        {"oauth_link": {"user_id": 7, "provider": "google"}}
    )

    response = await auth_api.complete_oauth_login(
        "google",
        request,
        FakeCallbackClient(),
        identity_service,
        FakeExchangeStore(),
        audit_service,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://localhost:5173/settings"
        "?oauth_link=success&provider=google"
    )
    assert identity_service.linked_user_id == 7
    assert request.session == {}
    assert audit_service.calls[0]["action"] == "AUTH_OAUTH_GOOGLE_LINK_SUCCESS"


@pytest.mark.asyncio
async def test_callback_redirects_to_settings_when_link_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            jwt_secret_key="0123456789abcdef0123456789abcdef",
            oauth_frontend_link_success_url="http://localhost:5173/settings",
        ),
    )
    request = FakeCallbackRequest(
        {"oauth_link": {"user_id": 7, "provider": "google"}}
    )

    response = await auth_api.complete_oauth_login(
        "google",
        request,
        FakeCallbackClient(),
        RejectingCallbackIdentityService(),
        FakeExchangeStore(),
        FakeAuditService(),
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://localhost:5173/settings"
        "?oauth_link=error&provider=google"
    )
    assert request.session == {}
