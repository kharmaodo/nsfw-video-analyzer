from dataclasses import dataclass

from app.core.config import Settings


class TikTokOAuthConfigurationError(ValueError):
    """La configuration OAuth TikTok est absente ou partielle."""


@dataclass(frozen=True)
class TikTokOAuthConfiguration:
    client_key: str
    client_secret: str
    redirect_uri: str
    session_secret_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "TikTokOAuthConfiguration":
        values = {
            "OAUTH_SESSION_SECRET_KEY": settings.oauth_session_secret_key,
            "OAUTH_TIKTOK_CLIENT_KEY": settings.oauth_tiktok_client_key,
            "OAUTH_TIKTOK_CLIENT_SECRET": settings.oauth_tiktok_client_secret,
            "OAUTH_TIKTOK_REDIRECT_URI": settings.oauth_tiktok_redirect_uri,
        }
        missing = [
            key for key, value in values.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise TikTokOAuthConfigurationError(
                "Configuration TikTok OAuth incomplète : " + ", ".join(missing)
            )

        return cls(
            client_key=values["OAUTH_TIKTOK_CLIENT_KEY"].strip(),
            client_secret=values["OAUTH_TIKTOK_CLIENT_SECRET"].strip(),
            redirect_uri=values["OAUTH_TIKTOK_REDIRECT_URI"].strip(),
            session_secret_key=values["OAUTH_SESSION_SECRET_KEY"].strip(),
        )
