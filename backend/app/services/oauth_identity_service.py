import re
import secrets
from dataclasses import dataclass

from app.db.models import OAuthAccount, User, UserRole
from app.repositories.oauth_account_repository import OAuthAccountRepository
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class OAuthIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str | None = None
    preferred_username: str | None = None


class OAuthIdentityService:
    def __init__(
        self,
        users: UserRepository,
        oauth_accounts: OAuthAccountRepository,
        passwords: PasswordService,
    ) -> None:
        self.users = users
        self.oauth_accounts = oauth_accounts
        self.passwords = passwords

    def resolve(self, identity: OAuthIdentity) -> User:
        provider = identity.provider.strip().lower()
        subject = identity.subject.strip()
        if not provider or not subject:
            raise OAuthIdentityError("Fournisseur OAuth ou identifiant externe invalide.")

        existing = self.oauth_accounts.get_by_provider_subject(provider, subject)
        if existing is not None:
            user = self.users.get(existing.user_id)
            if user is None:
                raise OAuthIdentityError("Compte OAuth lié à un utilisateur introuvable.")
            return user

        user = User(
            username=self._available_username(identity, provider, subject),
            password_hash=self.passwords.hash(secrets.token_urlsafe(32)),
            role=UserRole.GUEST,
        )
        session = self.users.session
        try:
            session.add(user)
            session.flush()
            session.add(
                OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_subject=subject,
                    provider_email=identity.email,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        session.refresh(user)
        return user

    def _available_username(
        self,
        identity: OAuthIdentity,
        provider: str,
        subject: str,
    ) -> str:
        email_prefix = (identity.email or "").split("@", 1)[0]
        source = identity.preferred_username or email_prefix or f"{provider}-{subject}"
        base = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-") or "oauth-user"
        base = base[:100]
        candidate = base
        number = 2

        while self.users.get_by_username(candidate) is not None:
            suffix = f"-{number}"
            candidate = f"{base[:100 - len(suffix)]}{suffix}"
            number += 1
        return candidate


