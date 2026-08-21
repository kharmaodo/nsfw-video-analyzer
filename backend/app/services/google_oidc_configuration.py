from dataclasses import dataclass

from app.core.config import Settings


class GoogleOidcConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class GoogleOidcConfiguration:
    client_id: str
    client_secret: str
    redirect_uri: str
    discovery_url: str
    session_secret_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "GoogleOidcConfiguration":
        values = {
            "OAUTH_SESSION_SECRET_KEY": settings.oauth_session_secret_key,
            "OAUTH_GOOGLE_CLIENT_ID": settings.oauth_google_client_id,
            "OAUTH_GOOGLE_CLIENT_SECRET": settings.oauth_google_client_secret,
            "OAUTH_GOOGLE_REDIRECT_URI": settings.oauth_google_redirect_uri,
        }
        missing = [name for name, value in values.items() if not value or not value.strip()]
        if missing:
            raise GoogleOidcConfigurationError(
                "Configuration Google OAuth incomplète : " + ", ".join(missing)
            )

        return cls(
            client_id=values["OAUTH_GOOGLE_CLIENT_ID"].strip(),
            client_secret=values["OAUTH_GOOGLE_CLIENT_SECRET"].strip(),
            redirect_uri=values["OAUTH_GOOGLE_REDIRECT_URI"].strip(),
            discovery_url=settings.oauth_google_discovery_url,
            session_secret_key=values["OAUTH_SESSION_SECRET_KEY"].strip(),
        )


