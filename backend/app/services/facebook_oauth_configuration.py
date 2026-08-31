from dataclasses import dataclass

from app.core.config import Settings


class FacebookOAuthConfigurationError(ValueError):
    """La configuration OAuth Facebook est absente ou partielle."""


@dataclass(frozen=True)
class FacebookOAuthConfiguration:
    client_id: str
    client_secret: str
    redirect_uri: str
    graph_api_version: str
    session_secret_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "FacebookOAuthConfiguration":
        values = {
            "OAUTH_SESSION_SECRET_KEY": settings.oauth_session_secret_key,
            "OAUTH_FACEBOOK_CLIENT_ID": settings.oauth_facebook_client_id,
            "OAUTH_FACEBOOK_CLIENT_SECRET": settings.oauth_facebook_client_secret,
            "OAUTH_FACEBOOK_REDIRECT_URI": settings.oauth_facebook_redirect_uri,
        }
        missing = [
            key
            for key, value in values.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise FacebookOAuthConfigurationError(
                "Configuration Facebook OAuth incomplète : "
                + ", ".join(missing)
            )

        return cls(
            client_id=values["OAUTH_FACEBOOK_CLIENT_ID"].strip(),
            client_secret=values["OAUTH_FACEBOOK_CLIENT_SECRET"].strip(),
            redirect_uri=values["OAUTH_FACEBOOK_REDIRECT_URI"].strip(),
            graph_api_version=settings.oauth_facebook_graph_api_version.strip(),
            session_secret_key=values["OAUTH_SESSION_SECRET_KEY"].strip(),
        )
