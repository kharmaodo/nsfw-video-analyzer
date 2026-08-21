from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OAuthAccount


class OAuthAccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, account: OAuthAccount) -> OAuthAccount:
        self.session.add(account)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(account)
        return account

    def get_by_provider_subject(
        self,
        provider: str,
        provider_subject: str,
    ) -> OAuthAccount | None:
        return self.session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_subject == provider_subject,
            )
        )

    def get_by_user_provider(
        self,
        user_id: int,
        provider: str,
    ) -> OAuthAccount | None:
        return self.session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        )


