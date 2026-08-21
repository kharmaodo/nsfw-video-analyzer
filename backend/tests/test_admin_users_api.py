from app.core.config import Settings
from app.db.models import User, UserRole
from app.db.session import get_db
from app.main import app
from app.services.jwt_service import JwtService


def test_super_power_can_manage_users(client) -> None:
    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "managed-user",
            "password": "managed-password",
            "role": "GUEST",
        },
    )

    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get("/api/v1/admin/users?page=1&size=20")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    updated = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "SUPER_POWER", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "SUPER_POWER"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/admin/users/{user_id}")
    assert deleted.status_code == 204


def test_guest_cannot_access_user_administration(client) -> None:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        guest = User(
            id=800,
            username="admin-denied-guest",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        session.add(guest)
        session.commit()
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    token = JwtService(settings).create_access_token(guest)
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Privilège SUPER_POWER requis."}

