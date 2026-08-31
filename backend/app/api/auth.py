from urllib.parse import quote






from math import ceil

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.authentication import CurrentUserDependency

from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.oauth_account_repository import OAuthAccountRepository
from app.repositories.audit_log_repository import AuditLogRepository

from app.schemas.auth import (
    AccountUpdateRequest,
    AuthenticatedUserRead,
    LoginRequest,
    LoginResponse,
)
from app.schemas.audit import AuditLogListResponse, AuditLogRead

from app.services.authentication_service import AuthenticationError, AuthenticationService
from app.services.audit_service import AuditService
from app.services.account_service import (
    AccountService,
    CurrentPasswordInvalidError,
    UsernameAlreadyExistsError,
)


from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService
from app.services.google_oidc_client import GoogleOidcClient
from app.services.google_oidc_configuration import (
    GoogleOidcConfiguration,
    GoogleOidcConfigurationError,
)
from app.services.oauth_exchange_code_store import OAuthExchangeCodeStore
from app.services.oauth_identity_service import (
    OAuthIdentityError,
    OAuthIdentityService,
)
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





def get_account_service(db: Annotated[Session, Depends(get_db)]) -> AccountService:
    settings = get_settings()
    return AccountService(
        UserRepository(db),
        PasswordService(rounds=settings.bcrypt_rounds),
    )


AccountServiceDependency = Annotated[AccountService, Depends(get_account_service)]


def get_audit_service(db: Annotated[Session, Depends(get_db)]) -> AuditService:
    return AuditService(AuditLogRepository(db))


AuditServiceDependency = Annotated[AuditService, Depends(get_audit_service)]

AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


def get_google_oidc_client() -> GoogleOidcClient:
    try:
        configuration = GoogleOidcConfiguration.from_settings(get_settings())
    except GoogleOidcConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connexion Google non configurée.",
        ) from exc
    return GoogleOidcClient(configuration)


def get_oauth_identity_service(
    db: Annotated[Session, Depends(get_db)],
) -> OAuthIdentityService:
    settings = get_settings()
    return OAuthIdentityService(
        UserRepository(db),
        OAuthAccountRepository(db),
        PasswordService(rounds=settings.bcrypt_rounds),
    )


def get_oauth_exchange_code_store() -> OAuthExchangeCodeStore:
    return OAuthExchangeCodeStore(get_settings())


GoogleOidcClientDependency = Annotated[
    GoogleOidcClient,
    Depends(get_google_oidc_client),
]
OAuthIdentityServiceDependency = Annotated[
    OAuthIdentityService,
    Depends(get_oauth_identity_service),
]
OAuthExchangeCodeStoreDependency = Annotated[
    OAuthExchangeCodeStore,
    Depends(get_oauth_exchange_code_store),
]


def oauth_login_response(user, settings) -> LoginResponse:
    return LoginResponse(
        access_token=JwtService(settings).create_access_token(user),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=AuthenticatedUserRead(
            id=user.id,
            username=user.username,
            role=user.role,
        ),
    )


def oauth_frontend_callback_url(settings, code: str) -> str:
    separator = "&" if "?" in settings.oauth_frontend_success_url else "?"
    return "{}{}oauth_code={}".format(
        settings.oauth_frontend_success_url,
        separator,
        quote(code),
    )


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



@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    user: CurrentUserDependency,
    audit_service: AuditServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogListResponse:
    actor_user_id = (
        None
        if user.role.value == "SUPER_POWER"
        else user.id
    )
    repository = audit_service.repository
    total = repository.count_by_actor(actor_user_id)
    items = repository.list_by_actor(
        actor_user_id,
        offset=(page - 1) * size,
        limit=size,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size) if total else 0,
    )



@router.patch("/me", response_model=LoginResponse)
def update_current_user(
    payload: AccountUpdateRequest,
    user: CurrentUserDependency,
    service: AccountServiceDependency,
    audit_service: AuditServiceDependency,
) -> LoginResponse:
    try:
        updated = service.update(
            user,
            current_password=payload.current_password,
            username=payload.username,
            new_password=payload.new_password,
        )
    except CurrentPasswordInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel invalide.",
        ) from exc
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    changed = []
    if payload.username is not None:
        changed.append("username")
    if payload.new_password is not None:
        changed.append("password")
    audit_service.record(
        actor=updated,
        action="AUTH_ACCOUNT_UPDATED",
        target_type="user",
        target_id=str(updated.id),
        details=",".join(changed),
    )

    settings = get_settings()
    return LoginResponse(
        access_token=JwtService(settings).create_access_token(updated),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=AuthenticatedUserRead(
            id=updated.id,
            username=updated.username,
            role=updated.role,
        ),
    )

