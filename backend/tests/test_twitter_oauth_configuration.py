import pytest

from app.core.config import Settings
from app.services.twitter_oauth_configuration import (
    TwitterOAuthConfiguration,
    TwitterOAuthConfigurationError,
)


def test_rejects_incomplete_twitter_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_twitter_client_id="twitter-client-id",
    )

    with pytest.raises(
        TwitterOAuthConfigurationError,
        match="OAUTH_TWITTER_CLIENT_SECRET",
    ):
        TwitterOAuthConfiguration.from_settings(settings)


def test_reads_complete_twitter_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_twitter_client_id="twitter-client-id",
        oauth_twitter_client_secret="twitter-client-secret",
        oauth_twitter_redirect_uri="http://localhost:8000/auth/oauth/twitter/callback",
    )

    configuration = TwitterOAuthConfiguration.from_settings(settings)

    assert configuration.client_id == "twitter-client-id"
    assert configuration.redirect_uri.endswith("/auth/oauth/twitter/callback")
