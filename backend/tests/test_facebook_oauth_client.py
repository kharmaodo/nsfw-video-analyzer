import pytest

from app.services.facebook_oauth_client import FacebookOAuthClient
from app.services.facebook_oauth_configuration import FacebookOAuthConfiguration
from app.services.oauth_identity_service import OAuthIdentityError


class FakeFacebookResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def json(self):
        return self.payload


class FakeFacebookRemote:
    def __init__(self, profile) -> None:
        self.profile = profile
        self.redirect_uri = None
        self.requested_fields = None

    async def authorize_redirect(self, request, redirect_uri):
        self.redirect_uri = redirect_uri
        return {"request": request, "redirect_uri": redirect_uri}

    async def authorize_access_token(self, request):
        return {"access_token": "facebook-token"}

    async def get(self, path, token, params):
        self.requested_fields = params
        return FakeFacebookResponse(self.profile)


def configuration() -> FacebookOAuthConfiguration:
    return FacebookOAuthConfiguration(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
        redirect_uri="http://localhost:8000/auth/oauth/facebook/callback",
        graph_api_version="v26.0",
        session_secret_key="0123456789abcdef0123456789abcdef",
    )


@pytest.mark.asyncio
async def test_reads_facebook_identity() -> None:
    remote = FakeFacebookRemote(
        {
            "id": "facebook-7",
            "name": "Facebook User",
            "email": "facebook@example.test",
        }
    )
    client = FacebookOAuthClient(configuration(), remote)

    identity = await client.fetch_identity(object())

    assert identity.provider == "facebook"
    assert identity.subject == "facebook-7"
    assert identity.email == "facebook@example.test"
    assert remote.requested_fields == {"fields": "id,name,email"}


@pytest.mark.asyncio
async def test_rejects_facebook_identity_without_id() -> None:
    client = FacebookOAuthClient(
        configuration(),
        FakeFacebookRemote({"name": "Facebook User"}),
    )

    with pytest.raises(OAuthIdentityError, match="Identifiant Facebook absent"):
        await client.fetch_identity(object())
