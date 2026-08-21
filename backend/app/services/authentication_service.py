from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.models import User
from app.repositories.user_repository import UserRepository
from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    access_token: str


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository,
        password_service: PasswordService,
        jwt_service: JwtService,
    ) -> None:
        self.repository = repository
        self.password_service = password_service
        self.jwt_service = jwt_service

    def authenticate(self, username: str, password: str) -> AuthenticationResult:
        user = self.repository.get_by_username(username.strip())
        if user is None or not user.is_active:
            raise AuthenticationError("Identifiants invalides.")
        if not self.password_service.verify(password, user.password_hash):
            raise AuthenticationError("Identifiants invalides.")

        user.last_login_at = datetime.now(UTC)
        user = self.repository.save(user)
        return AuthenticationResult(
            user=user,
            access_token=self.jwt_service.create_access_token(user),
        )

