from app.core.config import Settings
from app.db.models import AuditLog, User, UserRole
from app.db.session import get_db
from app.main import app
from app.services.jwt_service import JwtService


def test_guest_sees_only_its_audit_logs(client) -> None:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        guest = User(
            id=700,
            username="audit-guest",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        other = User(
            id=701,
            username="audit-other",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        session.add_all([guest, other])
        session.commit()
        session.add_all(
            [
                AuditLog(actor_user_id=700, action="OWN_ACTION"),
                AuditLog(actor_user_id=701, action="OTHER_ACTION"),
            ]
        )
        session.commit()
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    token = JwtService(settings).create_access_token(guest)
    response = client.get(
        "/auth/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["action"] == "OWN_ACTION"

