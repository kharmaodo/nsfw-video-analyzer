from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.services.facebook_oauth_configuration import FacebookOAuthConfiguration
from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError


class FacebookOAuthClient:
    def __init__(
        self,
        configuration: FacebookOAuthConfiguration,
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
        response = await self.remote.get(
            "me",
            token=token,
            params={"fields": "id,name,email"},
        )
        profile = response.json()
        if not isinstance(profile, dict):
            raise OAuthIdentityError("Informations utilisateur Facebook absentes.")

        subject = profile.get("id")
        if not isinstance(subject, str) or not subject.strip():
            raise OAuthIdentityError("Identifiant Facebook absent.")

        email = profile.get("email")
        name = profile.get("name")
        return OAuthIdentity(
            provider="facebook",
            subject=subject,
            email=email if isinstance(email, str) else None,
            preferred_username=name if isinstance(name, str) else None,
        )

    @staticmethod
    def _build_remote(configuration: FacebookOAuthConfiguration) -> Any:
        graph_base_url = (
            f"https://graph.facebook.com/{configuration.graph_api_version}/"
        )
        oauth = OAuth()
        oauth.register(
            name="facebook",
            client_id=configuration.client_id,
            client_secret=configuration.client_secret,
            authorize_url=(
                f"https://www.facebook.com/"
                f"{configuration.graph_api_version}/dialog/oauth"
            ),
            access_token_url=f"{graph_base_url}oauth/access_token",
            api_base_url=graph_base_url,
            client_kwargs={"scope": "email,public_profile"},
        )
        return oauth.create_client("facebook")
