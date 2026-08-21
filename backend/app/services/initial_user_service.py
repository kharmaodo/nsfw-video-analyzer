from app.core.config import Settings
from app.db.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class InitialUserConfigurationError(ValueError):
    pass


class InitialUserService:
    def __init__(
        self,
        settings: Settings,
        repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.password_service = password_service

    def ensure_super_power(self) -> User | None:
        username = (self.settings.initial_super_power_username or "").strip()
        password = self.settings.initial_super_power_password

        if not username and password is None:
            return None
        if not username or not password:
            raise InitialUserConfigurationError(
                "INITIAL_SUPER_POWER_USERNAME et INITIAL_SUPER_POWER_PASSWORD sont requis ensemble."
            )

        existing = self.repository.get_by_username(username)
        if existing is not None:
            return existing

        return self.repository.create(
            User(
                username=username,
                password_hash=self.password_service.hash(password),
                role=UserRole.SUPER_POWER,
            )
        )

