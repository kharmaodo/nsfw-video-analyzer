import app.api.auth as auth_api

from app.core.config import Settings
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


def test_login_success_is_audited(client, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: Settings(
            bcrypt_rounds=10,
            jwt_secret_key="0123456789abcdef0123456789abcdef",
        ),
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        user = UserRepository(session).create(
            User(
                username="audit-user",
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
        json={"username": "audit-user", "password": "mot-de-passe"},
    )

    assert response.status_code == 200

    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        entries = AuditLogRepository(session).list_by_actor(
            user.id,
            offset=0,
            limit=20,
        )
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    assert len(entries) == 1
    assert entries[0].action == "AUTH_LOGIN_SUCCESS"
    assert entries[0].ip_address == "testclient"

