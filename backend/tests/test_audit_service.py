from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User, UserRole
from app.db.session import build_engine
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.audit_service import AuditService


def test_records_and_filters_audit_entries_by_actor(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        actor = User(
            username="guest",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        other = User(
            username="other",
            password_hash="hash",
            role=UserRole.GUEST,
        )
        session.add_all([actor, other])
        session.commit()
        session.refresh(actor)
        session.refresh(other)

        service = AuditService(AuditLogRepository(session))
        service.record(
            actor=actor,
            action="AUTH_LOGIN_SUCCESS",
            target_type="user",
            target_id=str(actor.id),
            ip_address="203.0.113.10",
        )
        service.record(
            actor=other,
            action="AUTH_LOGIN_FAILURE",
            target_type="user",
            target_id=str(other.id),
        )

        own_entries = service.repository.list_by_actor(
            actor.id,
            offset=0,
            limit=20,
        )
        all_entries = service.repository.list_by_actor(
            None,
            offset=0,
            limit=20,
        )

        assert len(own_entries) == 1
        assert own_entries[0].action == "AUTH_LOGIN_SUCCESS"
        assert len(all_entries) == 2

    Base.metadata.drop_all(engine)
    engine.dispose()

