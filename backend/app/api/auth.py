from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.authentication import CurrentUserDependency

from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.audit_log_repository import AuditLogRepository

from app.schemas.auth import AuthenticatedUserRead, LoginRequest, LoginResponse
from app.services.authentication_service import AuthenticationError, AuthenticationService
from app.services.audit_service import AuditService

from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService
from app.services.login_rate_limiter import (
    LoginRateLimiter,
    LoginRateLimiterUnavailableError,
    LoginRateLimitState,
)


router = APIRouter(prefix="/auth", tags=["auth"])
login_rate_limiter = LoginRateLimiter()



def get_authentication_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticationService:
    settings = get_settings()
    return AuthenticationService(
        UserRepository(db),
        PasswordService(rounds=settings.bcrypt_rounds),
        JwtService(settings),
    )




def get_login_rate_limiter() -> LoginRateLimiter:
    return login_rate_limiter


LoginRateLimiterDependency = Annotated[
    LoginRateLimiter,
    Depends(get_login_rate_limiter),
]



def get_audit_service(db: Annotated[Session, Depends(get_db)]) -> AuditService:
    return AuditService(AuditLogRepository(db))


AuditServiceDependency = Annotated[AuditService, Depends(get_audit_service)]

AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,

    service: AuthenticationServiceDependency,
    limiter: LoginRateLimiterDependency,
    audit_service: AuditServiceDependency,


) -> LoginResponse:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    try:
        limit_state = await limiter.check(client_ip, settings)
    except LoginRateLimiterUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentification temporairement indisponible.",
        ) from exc
    if limit_state != LoginRateLimitState.ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion. Réessayez plus tard.",
        )


    try:
        result = service.authenticate(payload.username, payload.password)
    except AuthenticationError as exc:
        audit_service.record(
            actor=None,
            action="AUTH_LOGIN_FAILURE",
            target_type="auth",
            ip_address=client_ip,
        )

        try:
            failure_state = await limiter.record_failure(client_ip, settings)
        except LoginRateLimiterUnavailableError as limiter_exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentification temporairement indisponible.",
            ) from limiter_exc
        if failure_state != LoginRateLimitState.ALLOWED:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de tentatives de connexion. Réessayez plus tard.",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    settings = get_settings()
    try:
        await limiter.reset_failures(client_ip, settings)
    except LoginRateLimiterUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentification temporairement indisponible.",
        ) from exc


    audit_service.record(
        actor=result.user,
        action="AUTH_LOGIN_SUCCESS",
        target_type="user",
        target_id=str(result.user.id),
        ip_address=client_ip,
    )


    return LoginResponse(
        access_token=result.access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=AuthenticatedUserRead(
            id=result.user.id,
            username=result.user.username,
            role=result.user.role,
        ),
    )



@router.get("/me", response_model=AuthenticatedUserRead)
def current_user(user: CurrentUserDependency) -> AuthenticatedUserRead:
    return AuthenticatedUserRead(
        id=user.id,
        username=user.username,
        role=user.role,
    )

