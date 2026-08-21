import app.api.auth as auth_api

from app.core.config import Settings
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


def test_login_returns_bearer_token(client, monkeypatch) -> None:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(auth_api, "get_settings", lambda: settings)

    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        UserRepository(session).create(
            User(
                username="admin",
                password_hash=PasswordService(rounds=4).hash("mot-de-passe"),
            )
        )
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "mot-de-passe"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "admin"


def test_login_rejects_invalid_credentials(client, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            bcrypt_rounds=10,
            jwt_secret_key="0123456789abcdef0123456789abcdef",
        ),
    )

    response = client.post(
        "/auth/login",
        json={"username": "inconnu", "password": "mot-de-passe"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Identifiants invalides."}

