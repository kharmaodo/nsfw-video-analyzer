import logging
import time
import uuid

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import Settings

logger = logging.getLogger("app.http")

HTTP_REQUESTS = Counter(
    "nsfw_http_requests_total",
    "Nombre de requêtes HTTP",
    ("method", "path", "status"),
)
HTTP_DURATION = Histogram(
    "nsfw_http_request_duration_seconds",
    "Durée des requêtes HTTP",
    ("method", "path"),
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        content_length = request.headers.get("content-length")
        is_media_upload = (
            request.method == "POST"
            and request.url.path.rstrip("/") == "/api/v1/media/uploads"
        )
        maximum_request_bytes = (
            self.settings.media_upload_max_total_bytes
            if is_media_upload
            else self.settings.api_max_request_bytes
        )
        try:
            oversized = bool(content_length) and int(content_length) > maximum_request_bytes
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "En-tête Content-Length invalide."},
                headers={"X-Request-ID": request_id},
            )
        if oversized:
            return JSONResponse(
                status_code=413,
                content={"detail": "Corps de requête trop volumineux."},
                headers={"X-Request-ID": request_id},
            )

        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, path).observe(duration)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        logger.info(
            "request_complete method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            path,
            response.status_code,
            duration * 1000,
            request_id,
        )
        return response
