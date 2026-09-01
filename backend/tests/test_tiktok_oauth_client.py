import pytest

from app.services.oauth_identity_service import OAuthIdentityError
from app.services.tiktok_oauth_client import TikTokOAuthClient
from app.services.tiktok_oauth_configuration import TikTokOAuthConfiguration


class FakeRequest:
    def __init__(self) -> None:
        self.session: dict[str, str] = {}
        self.query_params: dict[str, str] = {}


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.token_data = None
        self.profile_headers = None
        self.profile_params = None

    async def post(self, url, data):
        self.token_data = (url, data)
        return FakeResponse({"access_token": "tiktok-token"})

    async def get(self, url, headers, params):
        self.profile_headers = headers
        self.profile_params = params
        return FakeResponse(
            {"data": {"user": {"open_id": "tiktok-7", "display_name": "TikTok User"}}}
        )


def configuration() -> TikTokOAuthConfiguration:
    return TikTokOAuthConfiguration(
        client_key="tiktok-client-key",
        client_secret="tiktok-client-secret",
        redirect_uri="http://localhost:8000/auth/oauth/tiktok/callback",
        session_secret_key="0123456789abcdef0123456789abcdef",
    )


@pytest.mark.asyncio
async def test_reads_tiktok_identity_after_state_validation() -> None:
    http_client = FakeHttpClient()
    client = TikTokOAuthClient(configuration(), http_client)
    request = FakeRequest()

    redirect = await client.authorize_redirect(request)
    state = request.session["oauth_tiktok_state"]
    request.query_params = {"state": state, "code": "authorization-code"}

    identity = await client.fetch_identity(request)

    assert redirect.status_code == 307
    assert "client_key=tiktok-client-key" in redirect.headers["location"]
    assert identity.provider == "tiktok"
    assert identity.subject == "tiktok-7"
    assert identity.preferred_username == "TikTok User"
    assert request.session == {}
    assert http_client.token_data[1]["grant_type"] == "authorization_code"
    assert http_client.profile_headers == {"Authorization": "Bearer tiktok-token"}
    assert http_client.profile_params == {"fields": "open_id,display_name"}


@pytest.mark.asyncio
async def test_rejects_tiktok_callback_with_invalid_state() -> None:
    client = TikTokOAuthClient(configuration(), FakeHttpClient())
    request = FakeRequest()

    await client.authorize_redirect(request)
    request.query_params = {"state": "wrong", "code": "authorization-code"}

    with pytest.raises(OAuthIdentityError, match="Réponse OAuth TikTok invalide"):
        await client.fetch_identity(request)
