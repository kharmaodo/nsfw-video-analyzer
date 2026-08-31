from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_lists_only_configured_oauth_providers(monkeypatch) -> None:
    monkeypatch.setenv(
        "OAUTH_SESSION_SECRET_KEY",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv(
        "OAUTH_GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/oauth/google/callback",
    )
    monkeypatch.setenv("OAUTH_FACEBOOK_CLIENT_ID", "facebook-client-id")
    monkeypatch.setenv(
        "OAUTH_FACEBOOK_CLIENT_SECRET",
        "facebook-client-secret",
    )
    monkeypatch.setenv(
        "OAUTH_FACEBOOK_REDIRECT_URI",
        "http://localhost:8000/auth/oauth/facebook/callback",
    )
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            response = client.get("/auth/oauth/providers")

        assert response.status_code == 200
        assert response.json() == [
            {"provider": "google"},
            {"provider": "facebook"},
        ]
    finally:
        get_settings.cache_clear()


def test_returns_empty_list_when_no_oauth_provider_is_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OAUTH_SESSION_SECRET_KEY", "")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "")
    monkeypatch.setenv("OAUTH_FACEBOOK_CLIENT_ID", "")
    monkeypatch.setenv("OAUTH_FACEBOOK_CLIENT_SECRET", "")
    monkeypatch.setenv("OAUTH_FACEBOOK_REDIRECT_URI", "")
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            response = client.get("/auth/oauth/providers")

        assert response.status_code == 200
        assert response.json() == []
    finally:
        get_settings.cache_clear()
