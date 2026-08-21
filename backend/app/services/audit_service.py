from app.db.models import AuditLog, User
from app.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    def record(
        self,
        *,
        actor: User | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        details: str | None = None,
    ) -> AuditLog:
        return self.repository.create(
            AuditLog(
                actor_user_id=actor.id if actor is not None else None,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip_address=ip_address,
                details=details,
            )
        )

