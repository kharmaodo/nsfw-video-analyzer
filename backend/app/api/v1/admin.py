from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authentication import SuperPowerDependency
from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserUpdate,
)
from app.services.admin_user_service import (
    AdminUserService,
    SelfAdministrationError,
    UserNotFoundError,
)
from app.services.audit_service import AuditService
from app.services.password_service import PasswordService

router = APIRouter(prefix="/admin/users", tags=["admin"])
DbSession = Annotated[Session, Depends(get_db)]


def get_admin_user_service(db: DbSession) -> AdminUserService:
    return AdminUserService(
        UserRepository(db),
        PasswordService(rounds=get_settings().bcrypt_rounds),
    )


AdminUserServiceDependency = Annotated[
    AdminUserService,
    Depends(get_admin_user_service),
]


def get_audit_service(db: DbSession) -> AuditService:
    return AuditService(AuditLogRepository(db))


AuditServiceDependency = Annotated[AuditService, Depends(get_audit_service)]


@router.post("", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    user: SuperPowerDependency,
    service: AdminUserServiceDependency,
    audit_service: AuditServiceDependency,
) -> AdminUserRead:
    try:
        created = service.create(
            username=payload.username,
            password=payload.password,
            role=payload.role,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d’utilisateur est déjà utilisé.",
        ) from exc
    audit_service.record(
        actor=user,
        action="ADMIN_USER_CREATED",
        target_type="user",
        target_id=str(created.id),
    )
    return AdminUserRead.model_validate(created)


@router.get("", response_model=AdminUserListResponse)
def list_users(
    user: SuperPowerDependency,
    service: AdminUserServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserListResponse:
    items, total = service.repository.list(
        offset=(page - 1) * size,
        limit=size,
    )
    return AdminUserListResponse(
        items=[AdminUserRead.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size) if total else 0,
    )


@router.patch("/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    user: SuperPowerDependency,
    service: AdminUserServiceDependency,
    audit_service: AuditServiceDependency,
) -> AdminUserRead:
    try:
        updated = service.update(
            actor=user,
            user_id=user_id,
            role=payload.role,
            is_active=payload.is_active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SelfAdministrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit_service.record(
        actor=user,
        action="ADMIN_USER_UPDATED",
        target_type="user",
        target_id=str(updated.id),
    )
    return AdminUserRead.model_validate(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    user: SuperPowerDependency,
    service: AdminUserServiceDependency,
    audit_service: AuditServiceDependency,
) -> Response:
    try:
        service.delete(actor=user, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SelfAdministrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit_service.record(
        actor=user,
        action="ADMIN_USER_DELETED",
        target_type="user",
        target_id=str(user_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

