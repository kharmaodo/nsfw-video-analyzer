from urllib.parse import quote






from math import ceil

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from authlib.integrations.base_client import OAuthError
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
    OAuthExchangeRequest,
    OAuthProviderRead,
    OAuthLinkStartResponse,
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
from app.services.facebook_oauth_client import FacebookOAuthClient
from app.services.twitter_oauth_client import TwitterOAuthClient
from app.services.google_oidc_configuration import (
    GoogleOidcConfiguration,
    GoogleOidcConfigurationError,
)
from app.services.oauth_exchange_code_store import OAuthExchangeCodeStore
from app.services.oauth_link_code_store import OAuthLinkCodeStore
from app.services.facebook_oauth_configuration import (
    FacebookOAuthConfiguration,
    FacebookOAuthConfigurationError,
)
from app.services.twitter_oauth_configuration import (
    TwitterOAuthConfiguration,
    TwitterOAuthConfigurationError,
)
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


def get_facebook_oauth_client() -> FacebookOAuthClient:
    try:
        configuration = FacebookOAuthConfiguration.from_settings(get_settings())
    except FacebookOAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connexion Facebook non configurée.",
        ) from exc
    return FacebookOAuthClient(configuration)



def get_twitter_oauth_client() -> TwitterOAuthClient:
    try:
        configuration = TwitterOAuthConfiguration.from_settings(get_settings())
    except TwitterOAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connexion X/Twitter non configurée.",
        ) from exc
    return TwitterOAuthClient(configuration)



def get_oauth_identity_service(
    db: Annotated[Session, Depends(get_db)],
) -> OAuthIdentityService:
    settings = get_settings()
    return OAuthIdentityService(
        UserRepository(db),
        OAuthAccountRepository(db),
        PasswordService(rounds=settings.bcrypt_rounds),
    )


def get_oauth_link_code_store() -> OAuthLinkCodeStore:
    return OAuthLinkCodeStore(get_settings())



def get_oauth_exchange_code_store() -> OAuthExchangeCodeStore:
    return OAuthExchangeCodeStore(get_settings())


GoogleOidcClientDependency = Annotated[
    GoogleOidcClient,
    Depends(get_google_oidc_client),
]
FacebookOAuthClientDependency = Annotated[
    FacebookOAuthClient,
    Depends(get_facebook_oauth_client),
]


TwitterOAuthClientDependency = Annotated[
    TwitterOAuthClient,
    Depends(get_twitter_oauth_client),
]



OAuthIdentityServiceDependency = Annotated[
    OAuthIdentityService,
    Depends(get_oauth_identity_service),
]
OAuthLinkCodeStoreDependency = Annotated[
    OAuthLinkCodeStore,
    Depends(get_oauth_link_code_store),
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


def oauth_frontend_link_url(
    settings,
    provider: str,
    outcome: str,
) -> str:
    separator = "&" if "?" in settings.oauth_frontend_link_success_url else "?"
    return "{}{}oauth_link={}&provider={}".format(
        settings.oauth_frontend_link_success_url,
        separator,
        quote(outcome),
        quote(provider),
    )



def oauth_frontend_error_url(settings, error: str) -> str:
    separator = "&" if "?" in settings.oauth_frontend_success_url else "?"
    return "{}{}oauth_error={}".format(
        settings.oauth_frontend_success_url,
        separator,
        quote(error),
    )



def oauth_frontend_callback_url(settings, code: str) -> str:
    separator = "&" if "?" in settings.oauth_frontend_success_url else "?"
    return "{}{}oauth_code={}".format(
        settings.oauth_frontend_success_url,
        separator,
        quote(code),
    )


def enabled_oauth_providers() -> list[OAuthProviderRead]:
    settings = get_settings()
    providers: list[OAuthProviderRead] = []

    try:
        GoogleOidcConfiguration.from_settings(settings)
        providers.append(OAuthProviderRead(provider="google"))
    except GoogleOidcConfigurationError:
        pass

    try:
        FacebookOAuthConfiguration.from_settings(settings)
        providers.append(OAuthProviderRead(provider="facebook"))
    except FacebookOAuthConfigurationError:
        pass

    try:
        TwitterOAuthConfiguration.from_settings(settings)
        providers.append(OAuthProviderRead(provider="twitter"))
    except TwitterOAuthConfigurationError:
        pass

    return providers


@router.get("/oauth/providers", response_model=list[OAuthProviderRead])
def list_oauth_providers() -> list[OAuthProviderRead]:
    return enabled_oauth_providers()



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



async def issue_oauth_link_code(
    provider: str,
    user: CurrentUserDependency,
    store: OAuthLinkCodeStore,
) -> OAuthLinkStartResponse:
    try:
        code = await store.issue(user_id=user.id, provider=provider)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Liaison OAuth temporairement indisponible.",
        ) from exc
    return OAuthLinkStartResponse(code=code)


@router.post("/oauth/google/link", response_model=OAuthLinkStartResponse)
async def create_google_link_code(
    user: CurrentUserDependency,
    store: OAuthLinkCodeStoreDependency,
) -> OAuthLinkStartResponse:
    return await issue_oauth_link_code("google", user, store)


@router.post("/oauth/facebook/link", response_model=OAuthLinkStartResponse)
async def create_facebook_link_code(
    user: CurrentUserDependency,
    store: OAuthLinkCodeStoreDependency,
) -> OAuthLinkStartResponse:
    return await issue_oauth_link_code("facebook", user, store)



@router.post("/oauth/twitter/link", response_model=OAuthLinkStartResponse)
async def create_twitter_link_code(
    user: CurrentUserDependency,
    store: OAuthLinkCodeStoreDependency,
) -> OAuthLinkStartResponse:
    return await issue_oauth_link_code("twitter", user, store)



async def begin_oauth_link(
    provider: str,
    request: Request,
    code: str,
    client: Any,
    store: OAuthLinkCodeStore,
):
    try:
        intent = await store.consume(code)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Liaison OAuth temporairement indisponible.",
        ) from exc

    if intent is None or intent.provider != provider:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code de liaison OAuth invalide ou expiré.",
        )

    request.session["oauth_link"] = {
        "user_id": intent.user_id,
        "provider": provider,
    }
    return await client.authorize_redirect(request)



async def complete_oauth_login(
    provider: str,
    request: Request,
    client: Any,
    identity_service: OAuthIdentityService,
    exchange_store: OAuthExchangeCodeStore,
    audit_service: AuditService,
) -> RedirectResponse:
    settings = get_settings()
    link_context = request.session.pop("oauth_link", None)
    link_user_id: int | None = None

    if link_context is not None:
        if not isinstance(link_context, dict):
            return RedirectResponse(
                oauth_frontend_link_url(settings, provider, "error")
            )
        try:
            context_provider = str(link_context["provider"]).strip().lower()
            link_user_id = int(link_context["user_id"])
        except (KeyError, TypeError, ValueError):
            return RedirectResponse(
                oauth_frontend_link_url(settings, provider, "error")
            )
        if context_provider != provider or link_user_id <= 0:
            return RedirectResponse(
                oauth_frontend_link_url(settings, provider, "error")
            )

    try:
        identity = await client.fetch_identity(request)
        user = (
            identity_service.link_by_user_id(link_user_id, identity)
            if link_user_id is not None
            else identity_service.resolve(identity)
        )
    except (OAuthError, OAuthIdentityError):
        if link_user_id is not None:
            return RedirectResponse(
                oauth_frontend_link_url(settings, provider, "error")
            )
        return RedirectResponse(
            oauth_frontend_error_url(
                settings,
                f"{provider}_auth_failed",
            )
        )

    client_ip = request.client.host if request.client else "unknown"
    if link_user_id is not None:
        audit_service.record(
            actor=user,
            action=f"AUTH_OAUTH_{provider.upper()}_LINK_SUCCESS",
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip,
        )
        return RedirectResponse(
            oauth_frontend_link_url(settings, provider, "success")
        )

    response = oauth_login_response(user, settings)
    try:
        code = await exchange_store.issue(response)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentification temporairement indisponible.",
        ) from exc

    audit_service.record(
        actor=user,
        action=f"AUTH_OAUTH_{provider.upper()}_SUCCESS",
        target_type="user",
        target_id=str(user.id),
        ip_address=client_ip,
    )
    return RedirectResponse(oauth_frontend_callback_url(settings, code))



@router.get("/oauth/google/login")
async def start_google_login(
    request: Request,
    client: GoogleOidcClientDependency,
):
    return await client.authorize_redirect(request)




@router.get("/oauth/google/callback")
async def complete_google_login(
    request: Request,
    client: GoogleOidcClientDependency,
    identity_service: OAuthIdentityServiceDependency,
    exchange_store: OAuthExchangeCodeStoreDependency,
    audit_service: AuditServiceDependency,
) -> RedirectResponse:
    return await complete_oauth_login(
        "google",
        request,
        client,
        identity_service,
        exchange_store,
        audit_service,
    )


@router.post("/oauth/exchange", response_model=LoginResponse)
async def exchange_oauth_code(
    payload: OAuthExchangeRequest,
    exchange_store: OAuthExchangeCodeStoreDependency,
) -> LoginResponse:
    try:
        response = await exchange_store.consume(payload.code)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentification temporairement indisponible.",
        ) from exc

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code OAuth invalide ou expiré.",
        )
    return response


@router.get("/oauth/facebook/login")
async def start_facebook_login(
    request: Request,
    client: FacebookOAuthClientDependency,
):
    return await client.authorize_redirect(request)


@router.get("/oauth/facebook/callback")
async def complete_facebook_login(
    request: Request,
    client: FacebookOAuthClientDependency,
    identity_service: OAuthIdentityServiceDependency,
    exchange_store: OAuthExchangeCodeStoreDependency,
    audit_service: AuditServiceDependency,
) -> RedirectResponse:
    return await complete_oauth_login(
        "facebook",
        request,
        client,
        identity_service,
        exchange_store,
        audit_service,
    )


@router.get("/oauth/google/link/start")
async def start_google_link(
    request: Request,
    code: Annotated[str, Query(min_length=20, max_length=512)],
    client: GoogleOidcClientDependency,
    store: OAuthLinkCodeStoreDependency,
):
    return await begin_oauth_link("google", request, code, client, store)


@router.get("/oauth/facebook/link/start")
async def start_facebook_link(
    request: Request,
    code: Annotated[str, Query(min_length=20, max_length=512)],
    client: FacebookOAuthClientDependency,
    store: OAuthLinkCodeStoreDependency,
):
    return await begin_oauth_link("facebook", request, code, client, store)


@router.get("/oauth/twitter/login")
async def start_twitter_login(
    request: Request,
    client: TwitterOAuthClientDependency,
):
    return await client.authorize_redirect(request)


@router.get("/oauth/twitter/callback")
async def complete_twitter_login(
    request: Request,
    client: TwitterOAuthClientDependency,
    identity_service: OAuthIdentityServiceDependency,
    exchange_store: OAuthExchangeCodeStoreDependency,
    audit_service: AuditServiceDependency,
) -> RedirectResponse:
    return await complete_oauth_login(
        "twitter",
        request,
        client,
        identity_service,
        exchange_store,
        audit_service,
    )


@router.get("/oauth/twitter/link/start")
async def start_twitter_link(
    request: Request,
    code: Annotated[str, Query(min_length=20, max_length=512)],
    client: TwitterOAuthClientDependency,
    store: OAuthLinkCodeStoreDependency,
):
    return await begin_oauth_link("twitter", request, code, client, store)
