import pytest

from app.core.config import Settings
from app.services.tiktok_oauth_configuration import (
    TikTokOAuthConfiguration,
    TikTokOAuthConfigurationError,
)


def test_rejects_incomplete_tiktok_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_tiktok_client_key="tiktok-client-key",
    )

    with pytest.raises(
        TikTokOAuthConfigurationError,
        match="OAUTH_TIKTOK_CLIENT_SECRET",
    ):
        TikTokOAuthConfiguration.from_settings(settings)


def test_reads_complete_tiktok_oauth_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_tiktok_client_key="tiktok-client-key",
        oauth_tiktok_client_secret="tiktok-client-secret",
        oauth_tiktok_redirect_uri="http://localhost:8000/auth/oauth/tiktok/callback",
    )

    configuration = TikTokOAuthConfiguration.from_settings(settings)

    assert configuration.client_key == "tiktok-client-key"
    assert configuration.redirect_uri.endswith("/auth/oauth/tiktok/callback")
