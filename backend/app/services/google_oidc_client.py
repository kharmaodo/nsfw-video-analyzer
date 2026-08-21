from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.services.google_oidc_configuration import GoogleOidcConfiguration
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError


class GoogleOidcClient:
    def __init__(
        self,
        configuration: GoogleOidcConfiguration,
        remote: Any | None = None,
    ) -> None:
        self.configuration = configuration
        self.remote = remote or self._build_remote(configuration)

    async def authorize_redirect(self, request: Any) -> Any:
        return await self.remote.authorize_redirect(
            request,
            self.configuration.redirect_uri,
        )

    async def fetch_identity(self, request: Any) -> OAuthIdentity:
        token = await self.remote.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, dict):
            raise OAuthIdentityError("Informations utilisateur Google absentes.")

        subject = userinfo.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise OAuthIdentityError("Identifiant Google absent.")

        email = userinfo.get("email")
        name = userinfo.get("name") or userinfo.get("preferred_username")
        return OAuthIdentity(
            provider="google",
            subject=subject,
            email=email if isinstance(email, str) else None,
            preferred_username=name if isinstance(name, str) else None,
        )

    @staticmethod
    def _build_remote(configuration: GoogleOidcConfiguration) -> Any:
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=configuration.client_id,
            client_secret=configuration.client_secret,
            server_metadata_url=configuration.discovery_url,
            client_kwargs={"scope": "openid profile email"},
        )
        return oauth.create_client("google")


