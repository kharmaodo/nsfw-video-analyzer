from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

import httpx
from starlette.responses import RedirectResponse

from app.services.oauth_identity_service import OAuthIdentity, OAuthIdentityError
from app.services.tiktok_oauth_configuration import TikTokOAuthConfiguration


class TikTokOAuthClient:
    _state_session_key = "oauth_tiktok_state"
    _authorize_url = "https://www.tiktok.com/v2/auth/authorize/"
    _token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    _user_info_url = "https://open.tiktokapis.com/v2/user/info/"

    def __init__(
        self,
        configuration: TikTokOAuthConfiguration,
        http_client: Any | None = None,
    ) -> None:
        self.configuration = configuration
        self.http_client = http_client

    async def authorize_redirect(self, request: Any) -> RedirectResponse:
        state = token_urlsafe(32)
        request.session[self._state_session_key] = state
        query = urlencode({
            "client_key": self.configuration.client_key,
            "response_type": "code",
            "scope": "user.info.basic",
            "redirect_uri": self.configuration.redirect_uri,
            "state": state,
        })
        return RedirectResponse(f"{self._authorize_url}?{query}")

    async def fetch_identity(self, request: Any) -> OAuthIdentity:
        expected_state = request.session.pop(self._state_session_key, None)
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if (
            not isinstance(expected_state, str)
            or not expected_state
            or state != expected_state
            or not isinstance(code, str)
            or not code
        ):
            raise OAuthIdentityError("Réponse OAuth TikTok invalide.")

        try:
            token, profile = await self._fetch_token_and_profile(code)
        except httpx.HTTPError as exc:
            raise OAuthIdentityError("Échange OAuth TikTok impossible.") from exc

        user = (
            profile.get("data", {}).get("user")
            if isinstance(profile, dict) and isinstance(profile.get("data"), dict)
            else None
        )
        if not isinstance(user, dict):
            raise OAuthIdentityError("Informations utilisateur TikTok absentes.")

        subject = user.get("open_id")
        if not isinstance(subject, str) or not subject.strip():
            raise OAuthIdentityError("Identifiant TikTok absent.")

        display_name = user.get("display_name")
        return OAuthIdentity(
            provider="tiktok",
            subject=subject,
            preferred_username=(
                display_name if isinstance(display_name, str) else None
            ),
        )

    async def _fetch_token_and_profile(self, code: str) -> tuple[Any, Any]:
        token_data = {
            "client_key": self.configuration.client_key,
            "client_secret": self.configuration.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.configuration.redirect_uri,
        }
        if self.http_client is not None:
            return await self._request_token_and_profile(self.http_client, token_data)

        async with httpx.AsyncClient(timeout=10) as client:
            return await self._request_token_and_profile(client, token_data)

    async def _request_token_and_profile(
        self,
        client: Any,
        token_data: dict[str, str],
    ) -> tuple[Any, Any]:
        token_response = await client.post(self._token_url, data=token_data)
        token = token_response.json()
        access_token = (
            token.get("access_token") if isinstance(token, dict) else None
        )
        if not isinstance(access_token, str) or not access_token:
            return token, {}

        profile_response = await client.get(
            self._user_info_url,
            headers={"Authorization": "Bearer " + access_token},
            params={"fields": "open_id,display_name"},
        )
        return token, profile_response.json()
