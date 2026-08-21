import app.api.auth as auth_api

from app.core.config import Settings
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService


def test_user_can_update_own_account_and_receives_new_token(client, monkeypatch) -> None:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(auth_api, "get_settings", lambda: settings)

    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        user = UserRepository(session).create(
            User(
                username="before",
                password_hash=PasswordService(rounds=4).hash("current"),
            )
        )
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    token = JwtService(settings).create_access_token(user)
    response = client.patch(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "current",
            "username": "after",
            "new_password": "new-password",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "after"
    assert body["access_token"]

    current = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert current.status_code == 200
    assert current.json()["username"] == "after"

