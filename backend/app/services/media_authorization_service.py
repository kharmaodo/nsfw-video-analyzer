from app.db.models import User, UserRole, Video


class MediaAccessDeniedError(PermissionError):
    pass


class MediaAuthorizationService:
    @staticmethod
    def visible_owner_id(user: User) -> int | None:
        return None if user.role == UserRole.SUPER_POWER else user.id

    @staticmethod
    def require_access(user: User, media: Video) -> None:
        if user.role == UserRole.SUPER_POWER:
            return
        if media.owner_user_id == user.id:
            return
        raise MediaAccessDeniedError("Média introuvable.")

