import pytest

from app.services.oauth_identity_service import OAuthIdentityError
from app.services.twitter_oauth_client import TwitterOAuthClient
from app.services.twitter_oauth_configuration import TwitterOAuthConfiguration


class FakeRequest:
    def __init__(self) -> None:
        self.session: dict[str, str] = {}


class FakeTwitterResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def json(self):
        return self.payload


class FakeTwitterRemote:
    def __init__(self, profile) -> None:
        self.profile = profile
        self.redirect_arguments = None
        self.code_verifier = None

    async def authorize_redirect(self, request, redirect_uri, **kwargs):
        self.redirect_arguments = (redirect_uri, kwargs)
        return {"redirect_uri": redirect_uri}

    async def authorize_access_token(self, request, code_verifier):
        self.code_verifier = code_verifier
        return {"access_token": "twitter-token"}

    async def get(self, path, token):
        assert path == "users/me"
        return FakeTwitterResponse(self.profile)


def configuration() -> TwitterOAuthConfiguration:
    return TwitterOAuthConfiguration(
        client_id="twitter-client-id",
        client_secret="twitter-client-secret",
        redirect_uri="http://localhost:8000/auth/oauth/twitter/callback",
        session_secret_key="0123456789abcdef0123456789abcdef",
    )


@pytest.mark.asyncio
async def test_reads_twitter_identity_with_pkce() -> None:
    remote = FakeTwitterRemote(
        {"data": {"id": "twitter-7", "username": "twitter_user"}}
    )
    client = TwitterOAuthClient(configuration(), remote)
    request = FakeRequest()

    await client.authorize_redirect(request)
    identity = await client.fetch_identity(request)

    redirect_uri, arguments = remote.redirect_arguments
    assert redirect_uri == configuration().redirect_uri
    assert arguments["code_challenge_method"] == "S256"
    assert remote.code_verifier is not None
    assert arguments["code_challenge"] == client._code_challenge(
        remote.code_verifier
    )
    assert identity.provider == "twitter"
    assert identity.subject == "twitter-7"
    assert identity.preferred_username == "twitter_user"


@pytest.mark.asyncio
async def test_rejects_twitter_identity_without_id() -> None:
    client = TwitterOAuthClient(
        configuration(),
        FakeTwitterRemote({"data": {"username": "twitter_user"}}),
    )
    request = FakeRequest()

    await client.authorize_redirect(request)

    with pytest.raises(OAuthIdentityError, match="Identifiant X/Twitter absent"):
        await client.fetch_identity(request)
