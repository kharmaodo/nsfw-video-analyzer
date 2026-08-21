from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_by_actor(
        self,
        actor_user_id: int | None,
        *,
        offset: int,
        limit: int,
    ) -> list[AuditLog]:
        query = select(AuditLog)
        if actor_user_id is not None:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        return list(
            self.session.scalars(
                query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )



    def count_by_actor(self, actor_user_id: int | None) -> int:
        query = select(func.count(AuditLog.id))
        if actor_user_id is not None:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        return self.session.scalar(query) or 0

