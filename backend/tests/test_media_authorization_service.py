import pytest

from app.db.models import User, UserRole, Video
from app.services.media_authorization_service import (
    MediaAccessDeniedError,
    MediaAuthorizationService,
)


def user(user_id: int, role: UserRole = UserRole.GUEST) -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        password_hash="hash",
        role=role,
    )


def media(owner_user_id: int | None) -> Video:
    return Video(
        id=10,
        title="Média",
        page_url="https://example.test/page",
        video_url="https://example.test/video.mp4",
        owner_user_id=owner_user_id,
    )


def test_guest_sees_only_its_owner_identifier() -> None:
    assert MediaAuthorizationService.visible_owner_id(user(7)) == 7


def test_super_power_has_no_owner_filter() -> None:
    assert MediaAuthorizationService.visible_owner_id(
        user(1, UserRole.SUPER_POWER)
    ) is None


def test_guest_can_access_its_media() -> None:
    MediaAuthorizationService.require_access(user(7), media(7))


@pytest.mark.parametrize("owner_user_id", [None, 8])
def test_guest_cannot_access_other_or_legacy_media(owner_user_id: int | None) -> None:
    with pytest.raises(MediaAccessDeniedError, match="introuvable"):
        MediaAuthorizationService.require_access(user(7), media(owner_user_id))


def test_super_power_can_access_any_media() -> None:
    MediaAuthorizationService.require_access(
        user(1, UserRole.SUPER_POWER),
        media(owner_user_id=None),
    )

