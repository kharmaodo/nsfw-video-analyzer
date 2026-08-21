from app.db.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class UserNotFoundError(LookupError):
    pass


class SelfAdministrationError(ValueError):
    pass


class AdminUserService:
    def __init__(
        self,
        repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self.repository = repository
        self.password_service = password_service

    def create(
        self,
        *,
        username: str,
        password: str,
        role: UserRole,
    ) -> User:
        return self.repository.create(
            User(
                username=username.strip(),
                password_hash=self.password_service.hash(password),
                role=role,
            )
        )

    def update(
        self,
        *,
        actor: User,
        user_id: int,
        role: UserRole | None,
        is_active: bool | None,
    ) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise UserNotFoundError("Utilisateur introuvable.")
        if user.id == actor.id and (
            role not in {None, UserRole.SUPER_POWER}
            or is_active is False
        ):
            raise SelfAdministrationError(
                "Vous ne pouvez pas réduire ou désactiver votre propre compte."
            )
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        return self.repository.save(user)

    def delete(self, *, actor: User, user_id: int) -> None:
        user = self.repository.get(user_id)
        if user is None:
            raise UserNotFoundError("Utilisateur introuvable.")
        if user.id == actor.id:
            raise SelfAdministrationError(
                "Vous ne pouvez pas supprimer votre propre compte."
            )
        self.repository.delete(user)

