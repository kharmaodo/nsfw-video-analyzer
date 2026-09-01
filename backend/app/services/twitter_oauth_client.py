from base64 import urlsafe_b64encode
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError
from app.services.twitter_oauth_configuration import TwitterOAuthConfiguration


class TwitterOAuthClient:
    _pkce_session_key = "oauth_twitter_pkce_verifier"

    def __init__(
        self,
        configuration: TwitterOAuthConfiguration,
        remote: Any | None = None,
    ) -> None:
        self.configuration = configuration
        self.remote = remote or self._build_remote(configuration)

    async def authorize_redirect(self, request: Any) -> Any:
        verifier = token_urlsafe(64)
        request.session[self._pkce_session_key] = verifier
        return await self.remote.authorize_redirect(
            request,
            self.configuration.redirect_uri,
            code_challenge=self._code_challenge(verifier),
            code_challenge_method="S256",
        )

    async def fetch_identity(self, request: Any) -> OAuthIdentity:
        verifier = request.session.pop(self._pkce_session_key, None)
        if not isinstance(verifier, str) or not verifier:
            raise OAuthIdentityError("Session PKCE X/Twitter invalide.")

        token = await self.remote.authorize_access_token(
            request,
            code_verifier=verifier,
        )
        response = await self.remote.get("users/me", token=token)
        profile = response.json()
        data = profile.get("data") if isinstance(profile, dict) else None
        if not isinstance(data, dict):
            raise OAuthIdentityError("Informations utilisateur X/Twitter absentes.")

        subject = data.get("id")
        if not isinstance(subject, str) or not subject.strip():
            raise OAuthIdentityError("Identifiant X/Twitter absent.")

        username = data.get("username")
        name = data.get("name")
        preferred_username = (
            username if isinstance(username, str)
            else name if isinstance(name, str) else None
        )
        return OAuthIdentity(
            provider="twitter",
            subject=subject,
            preferred_username=preferred_username,
        )

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        return urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(
            b"="
        ).decode()

    @staticmethod
    def _build_remote(configuration: TwitterOAuthConfiguration) -> Any:
        oauth = OAuth()
        oauth.register(
            name="twitter",
            client_id=configuration.client_id,
            client_secret=configuration.client_secret,
            authorize_url="https://x.com/i/oauth2/authorize",
            access_token_url="https://api.x.com/2/oauth2/token",
            api_base_url="https://api.x.com/2/",
            client_kwargs={"scope": "users.read tweet.read"},
        )
        return oauth.create_client("twitter")
