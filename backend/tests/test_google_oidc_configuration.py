import pytest

from app.core.config import Settings
from app.services.google_oidc_configuration import (
    GoogleOidcConfiguration,
    GoogleOidcConfigurationError,
)


def test_rejects_incomplete_google_oidc_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="",
        oauth_google_client_secret="",
        oauth_google_redirect_uri="",
        oauth_google_client_id="google-client-id",
    )

    with pytest.raises(GoogleOidcConfigurationError, match="OAUTH_SESSION_SECRET_KEY"):
        GoogleOidcConfiguration.from_settings(settings)


def test_reads_complete_google_oidc_configuration() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_google_client_id="google-client-id",
        oauth_google_client_secret="google-client-secret",
        oauth_google_redirect_uri="http://localhost:8000/auth/oauth/google/callback",
    )

    configuration = GoogleOidcConfiguration.from_settings(settings)

    assert configuration.client_id == "google-client-id"
    assert configuration.redirect_uri.endswith("/auth/oauth/google/callback")


