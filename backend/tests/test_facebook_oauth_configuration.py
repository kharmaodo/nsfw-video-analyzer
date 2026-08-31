import pytest

from app.core.config import Settings
from app.services.facebook_oauth_configuration import (
    FacebookOAuthConfiguration,
    FacebookOAuthConfigurationError,
)


def test_rejects_incomplete_facebook_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_facebook_client_id="facebook-client-id",
        oauth_facebook_client_secret="",
        oauth_facebook_redirect_uri="",
    )

    with pytest.raises(
        FacebookOAuthConfigurationError,
        match="OAUTH_FACEBOOK_CLIENT_SECRET",
    ):
        FacebookOAuthConfiguration.from_settings(settings)


def test_reads_complete_facebook_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_facebook_client_id="facebook-client-id",
        oauth_facebook_client_secret="facebook-client-secret",
        oauth_facebook_redirect_uri="http://localhost:8000/auth/oauth/facebook/callback",
    )

    configuration = FacebookOAuthConfiguration.from_settings(settings)

    assert configuration.client_id == "facebook-client-id"
    assert configuration.graph_api_version == "v26.0"
    assert configuration.redirect_uri.endswith("/auth/oauth/facebook/callback")
