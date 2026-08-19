from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.core.config import Settings
from app.services.url_security import UrlSecurityPolicy


class RemoteVideoError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteVideoMetadata:
    final_url: str
    content_type: str
    size_bytes: int
    accepts_ranges: bool


class RemoteVideoInspector:
    FALLBACK_STATUSES = {403, 405, 501}

    def __init__(
        self,
        settings: Settings,
        security: UrlSecurityPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.security = security or UrlSecurityPolicy()
        self.transport = transport

    async def inspect(self, initial_url: str) -> RemoteVideoMetadata:
        timeout = httpx.Timeout(
            connect=self.settings.scraper_connect_timeout_seconds,
            read=self.settings.scraper_read_timeout_seconds,
            write=self.settings.scraper_read_timeout_seconds,
            pool=self.settings.scraper_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            response, final_url = await self._request_with_redirects(client, "HEAD", initial_url)
            try:
                if response.status_code in self.FALLBACK_STATUSES:
                    await response.aclose()
                    response, final_url = await self._request_with_redirects(
                        client,
                        "GET",
                        initial_url,
                        headers={"Range": "bytes=0-0"},
                    )
                response.raise_for_status()
                return self._metadata_from_headers(final_url, response.headers)
            except httpx.HTTPError as exc:
                raise RemoteVideoError(f"Inspection distante impossible : {exc}") from exc
            finally:
                await response.aclose()

    async def _request_with_redirects(
        self,
        client: httpx.AsyncClient,
        method: str,
        initial_url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[httpx.Response, str]:
        current_url = initial_url
        for redirect_count in range(self.settings.scraper_max_redirects + 1):
            await self.security.validate(current_url)
            try:
                request = client.build_request(method, current_url, headers=headers)
                response = await client.send(request, stream=True)
            except httpx.HTTPError as exc:
                raise RemoteVideoError(f"Connexion à la vidéo impossible : {exc}") from exc

            if not response.is_redirect:
                return response, str(response.url)
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                raise RemoteVideoError("Redirection vidéo sans en-tête Location.")
            if redirect_count >= self.settings.scraper_max_redirects:
                raise RemoteVideoError("Nombre maximal de redirections vidéo dépassé.")
            current_url = urljoin(str(response.url), location)

        raise RemoteVideoError("Inspection distante impossible.")

    def _metadata_from_headers(
        self,
        final_url: str,
        headers: httpx.Headers,
    ) -> RemoteVideoMetadata:
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in self.settings.video_allowed_content_types:
            raise RemoteVideoError(f"Type de contenu vidéo interdit ou absent : {content_type or 'inconnu'}.")

        raw_size = headers.get("content-range") or headers.get("content-length")
        if not raw_size:
            raise RemoteVideoError("La taille de la vidéo n’est pas fournie par le serveur.")
        try:
            size_bytes = int(raw_size.rsplit("/", 1)[-1])
        except ValueError as exc:
            raise RemoteVideoError("La taille annoncée par le serveur est invalide.") from exc
        if size_bytes <= 0:
            raise RemoteVideoError("La taille annoncée doit être strictement positive.")
        if size_bytes > self.settings.video_max_size_bytes:
            raise RemoteVideoError(
                f"La vidéo dépasse la limite de {self.settings.video_max_size_bytes} octets."
            )

        accepts_ranges = headers.get("accept-ranges", "").lower() == "bytes" or "content-range" in headers
        if self.settings.video_require_range_requests and not accepts_ranges:
            raise RemoteVideoError("Le serveur ne supporte pas les requêtes HTTP Range.")

        return RemoteVideoMetadata(
            final_url=final_url,
            content_type=content_type,
            size_bytes=size_bytes,
            accepts_ranges=accepts_ranges,
        )

