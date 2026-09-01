from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.api.auth import router as auth_router

from app.core.config import get_settings
from app.services.facebook_oauth_configuration import (
    FacebookOAuthConfiguration,
    FacebookOAuthConfigurationError,
)
from app.services.twitter_oauth_configuration import (
    TwitterOAuthConfiguration,
    TwitterOAuthConfigurationError,
)
from app.services.google_oidc_configuration import (
    GoogleOidcConfiguration,
    GoogleOidcConfigurationError,
)
from app.core.jwt_authentication_middleware import JwtAuthenticationMiddleware

from app.core.observability import ObservabilityMiddleware
from app.db.session import SessionLocal, engine
from app.repositories.user_repository import UserRepository
from app.services.initial_user_service import InitialUserService
from app.services.password_service import PasswordService


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as session:
        InitialUserService(
            settings,
            UserRepository(session),
            PasswordService(rounds=settings.bcrypt_rounds),
        ).ensure_super_power()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    lifespan=lifespan,

)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.api_cors_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(JwtAuthenticationMiddleware)

try:
    google_oidc_configuration = GoogleOidcConfiguration.from_settings(settings)
except GoogleOidcConfigurationError:
    google_oidc_configuration = None

try:
    facebook_oauth_configuration = FacebookOAuthConfiguration.from_settings(settings)
except FacebookOAuthConfigurationError:
    facebook_oauth_configuration = None

try:
    twitter_oauth_configuration = TwitterOAuthConfiguration.from_settings(settings)
except TwitterOAuthConfigurationError:
    twitter_oauth_configuration = None

oauth_session_configuration = (
    google_oidc_configuration or facebook_oauth_configuration or twitter_oauth_configuration
)
if oauth_session_configuration is not None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=oauth_session_configuration.session_secret_key,
        same_site="lax",
        https_only=settings.app_env not in {"development", "test"},
    )

app.add_middleware(ObservabilityMiddleware, settings=settings)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.api_allowed_hosts))
app.include_router(api_v1_router)
app.include_router(auth_router)



@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "application": settings.app_name,
        "environment": settings.app_env,
        "status": "UP",
    }


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return health()


@app.get("/health/ready", tags=["system"])
async def readiness(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {"database": "DOWN", "redis": "DOWN"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "UP"
    except Exception:
        pass

    redis = Redis.from_url(settings.celery_broker_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        await redis.ping()
        checks["redis"] = "UP"
    except Exception:
        pass
    finally:
        await redis.aclose()

    ready = all(value == "UP" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "UP" if ready else "DOWN", "checks": checks}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
