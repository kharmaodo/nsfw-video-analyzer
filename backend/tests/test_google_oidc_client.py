import pytest

from app.services.google_oidc_client import GoogleOidcClient
from app.services.google_oidc_configuration import GoogleOidcConfiguration
from app.services.oauth_identity_service import OAuthIdentityError


class FakeGoogleRemote:
    def __init__(self, token) -> None:
        self.token = token
        self.redirect_uri = None

    async def authorize_redirect(self, request, redirect_uri):
        self.redirect_uri = redirect_uri
        return {"request": request, "redirect_uri": redirect_uri}

    async def authorize_access_token(self, request):
        return self.token


def configuration() -> GoogleOidcConfiguration:
    return GoogleOidcConfiguration(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:8000/auth/oauth/google/callback",
        discovery_url="https://accounts.google.com/.well-known/openid-configuration",
        session_secret_key="0123456789abcdef0123456789abcdef",
    )


@pytest.mark.asyncio
async def test_reads_google_identity() -> None:
    client = GoogleOidcClient(
        configuration(),
        FakeGoogleRemote({"userinfo": {"sub": "google-7", "email": "a@example.test"}}),
    )

    identity = await client.fetch_identity(object())

    assert identity.provider == "google"
    assert identity.subject == "google-7"
    assert identity.email == "a@example.test"


@pytest.mark.asyncio
async def test_rejects_google_identity_without_subject() -> None:
    client = GoogleOidcClient(
        configuration(),
        FakeGoogleRemote({"userinfo": {"email": "a@example.test"}}),
    )

    with pytest.raises(OAuthIdentityError, match="Identifiant Google absent"):
        await client.fetch_identity(object())


