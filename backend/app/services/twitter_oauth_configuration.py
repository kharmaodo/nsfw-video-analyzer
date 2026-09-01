from dataclasses import dataclass

from app.core.config import Settings


class TwitterOAuthConfigurationError(ValueError):
    """La configuration OAuth X/Twitter est absente ou partielle."""


@dataclass(frozen=True)
class TwitterOAuthConfiguration:
    client_id: str
    client_secret: str
    redirect_uri: str
    session_secret_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "TwitterOAuthConfiguration":
        values = {
            "OAUTH_SESSION_SECRET_KEY": settings.oauth_session_secret_key,
            "OAUTH_TWITTER_CLIENT_ID": settings.oauth_twitter_client_id,
            "OAUTH_TWITTER_CLIENT_SECRET": settings.oauth_twitter_client_secret,
            "OAUTH_TWITTER_REDIRECT_URI": settings.oauth_twitter_redirect_uri,
        }
        missing = [
            key for key, value in values.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise TwitterOAuthConfigurationError(
                "Configuration X/Twitter OAuth incomplète : " + ", ".join(missing)
            )

        return cls(
            client_id=values["OAUTH_TWITTER_CLIENT_ID"].strip(),
            client_secret=values["OAUTH_TWITTER_CLIENT_SECRET"].strip(),
            redirect_uri=values["OAUTH_TWITTER_REDIRECT_URI"].strip(),
            session_secret_key=values["OAUTH_SESSION_SECRET_KEY"].strip(),
        )
