from app.db.models import User
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class CurrentPasswordInvalidError(ValueError):
    pass


class UsernameAlreadyExistsError(ValueError):
    pass


class AccountService:
    def __init__(
        self,
        repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self.repository = repository
        self.password_service = password_service

    def update(
        self,
        user: User,
        *,
        current_password: str,
        username: str | None,
        new_password: str | None,
    ) -> User:
        if not self.password_service.verify(
            current_password,
            user.password_hash,
        ):
            raise CurrentPasswordInvalidError("Mot de passe actuel invalide.")

        if username is not None:
            normalized_username = username.strip()
            if normalized_username != user.username:
                existing = self.repository.get_by_username(normalized_username)
                if existing is not None and existing.id != user.id:
                    raise UsernameAlreadyExistsError(
                        "Ce nom d’utilisateur est déjà utilisé."
                    )
                user.username = normalized_username

        if new_password is not None:
            user.password_hash = self.password_service.hash(new_password)

        return self.repository.save(user)

