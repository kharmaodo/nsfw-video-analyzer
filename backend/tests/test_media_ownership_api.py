from app.core.config import Settings
from app.db.models import User, UserRole, Video
from app.db.session import get_db
from app.main import app
from app.services.jwt_service import JwtService


def test_guest_cannot_read_or_list_another_users_media(client) -> None:
    settings = Settings(
        bcrypt_rounds=10,
        jwt_secret_key="0123456789abcdef0123456789abcdef",
    )
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        guest = User(
            id=7,
            username="guest-7",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        owner = User(
            id=8,
            username="guest-8",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        media = Video(
            title="privé",
            page_url="https://example.test/private",
            video_url="https://cdn.example.test/private.mp4",
            owner_user_id=8,
        )
        session.add_all([guest, owner, media])
        session.commit()
        session.refresh(media)
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    guest_token = JwtService(settings).create_access_token(guest)
    headers = {"Authorization": f"Bearer {guest_token}"}

    detail = client.get(f"/api/v1/media/{media.id}", headers=headers)
    listing = client.get("/api/v1/media", headers=headers)

    assert detail.status_code == 404
    assert listing.status_code == 200
    assert listing.json()["items"] == []


def test_super_power_can_read_any_media(client) -> None:
    session_generator = app.dependency_overrides[get_db]()
    session = next(session_generator)
    try:
        owner = User(
            id=8,
            username="guest-8",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        media = Video(
            title="privé",
            page_url="https://example.test/private",
            video_url="https://cdn.example.test/private.mp4",
            owner_user_id=8,
        )
        session.add_all([owner, media])
        session.commit()
        session.refresh(media)
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass

    response = client.get(f"/api/v1/media/{media.id}")

    assert response.status_code == 200
    assert response.json()["title"] == "privé"

