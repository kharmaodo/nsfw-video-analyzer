from app.core.config import Settings


def test_google_oauth_configuration_is_optional() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_google_client_id=None,
        oauth_google_client_secret=None,
        oauth_google_redirect_uri=None,
    )

    assert settings.oauth_google_client_id is None
    assert settings.oauth_google_discovery_url == (
        "https://accounts.google.com/.well-known/openid-configuration"
    )


def test_google_oauth_configuration_accepts_required_values() -> None:
    settings = Settings(
        jwt_secret_key="0123456789abcdef0123456789abcdef",
        oauth_session_secret_key="0123456789abcdef0123456789abcdef",
        oauth_google_client_id="google-client-id",
        oauth_google_client_secret="google-client-secret",
        oauth_google_redirect_uri="http://localhost:8000/auth/oauth/google/callback",
    )

    assert settings.oauth_google_client_id == "google-client-id"
    assert settings.oauth_google_redirect_uri is not None


