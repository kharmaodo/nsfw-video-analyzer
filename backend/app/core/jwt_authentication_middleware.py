from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.services.jwt_service import (
    InvalidAccessTokenError,
    JwtConfigurationError,
    JwtService,
)

PUBLIC_ENDPOINTS = {
    ("GET", "/health"),
    ("POST", "/auth/login"),
        ("GET", "/auth/oauth/google/login"),
        ("GET", "/auth/oauth/google/callback"),
        ("POST", "/auth/oauth/exchange"),
}


class JwtAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        endpoint = (request.method, request.url.path.rstrip("/") or "/")
        if endpoint in PUBLIC_ENDPOINTS:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return self._unauthorized()

        try:
            request.state.access_token_claims = JwtService(
                get_settings()
            ).decode_access_token(token.strip())
        except (InvalidAccessTokenError, JwtConfigurationError):
            return self._unauthorized()

        return await call_next(request)

    @staticmethod
    def _unauthorized() -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "Session expirée."},
            headers={"WWW-Authenticate": "Bearer"},
        )

