from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import Settings
from app.services.url_security import UrlSecurityPolicy


class ScrapingError(RuntimeError):
    pass


class PageTooLargeError(ScrapingError):
    pass


@dataclass(frozen=True)
class DiscoveredVideo:
    title: str
    video_url: str


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"}


class PageFetcher:
    def __init__(
        self,
        settings: Settings,
        security: UrlSecurityPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.security = security or UrlSecurityPolicy()
        self.transport = transport

    async def fetch_html(self, initial_url: str) -> tuple[str, str]:
        timeout = httpx.Timeout(
            connect=self.settings.scraper_connect_timeout_seconds,
            read=self.settings.scraper_read_timeout_seconds,
            write=self.settings.scraper_read_timeout_seconds,
            pool=self.settings.scraper_connect_timeout_seconds,
        )
        current_url = initial_url
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            for redirect_count in range(self.settings.scraper_max_redirects + 1):
                await self.security.validate(current_url)
                try:
                    async with client.stream("GET", current_url) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise ScrapingError("Redirection sans en-tête Location.")
                            if redirect_count >= self.settings.scraper_max_redirects:
                                raise ScrapingError("Nombre maximal de redirections dépassé.")
                            current_url = urljoin(str(response.url), location)
                            continue

                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                            raise ScrapingError("La ressource distante n’est pas une page HTML.")

                        declared_size = int(response.headers.get("content-length", "0") or 0)
                        if declared_size > self.settings.scraper_max_html_bytes:
                            raise PageTooLargeError("La page dépasse la taille maximale autorisée.")

                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > self.settings.scraper_max_html_bytes:
                                raise PageTooLargeError("La page dépasse la taille maximale autorisée.")
                        return body.decode(response.encoding or "utf-8", errors="replace"), str(response.url)
                except httpx.HTTPError as exc:
                    raise ScrapingError(f"Impossible de récupérer la page : {exc}") from exc

        raise ScrapingError("Impossible de récupérer la page distante.")


class HtmlVideoExtractor:
    def extract(self, html: str, page_url: str) -> list[DiscoveredVideo]:
        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.get_text(" ", strip=True) if soup.title else "Vidéo sans titre"
        found: dict[str, DiscoveredVideo] = {}

        candidates = [
            *((node, node.get("href")) for node in soup.select("a[href]")),
            *((node, node.get("src")) for node in soup.select("video[src], source[src]")),
        ]
        for node, raw_url in candidates:
            if not raw_url:
                continue
            absolute_url = urljoin(page_url, raw_url.strip())
            if not self._is_video(node.get("type"), absolute_url):
                continue
            canonical_url = absolute_url.split("#", 1)[0]
            if canonical_url in found:
                continue
            title = self._title(node, canonical_url, page_title)
            found[canonical_url] = DiscoveredVideo(title=title[:500], video_url=canonical_url)
        return list(found.values())

    @staticmethod
    def _is_video(declared_type: str | None, url: str) -> bool:
        if declared_type and declared_type.lower().startswith("video/"):
            return True
        suffix = PurePosixPath(urlsplit(url).path.lower()).suffix
        return suffix in VIDEO_EXTENSIONS

    @staticmethod
    def _title(node, url: str, page_title: str) -> str:  # type: ignore[no-untyped-def]
        explicit = node.get("title") or node.get("aria-label")
        text = node.get_text(" ", strip=True)
        filename = unquote(PurePosixPath(urlsplit(url).path).stem).replace("-", " ").replace("_", " ")
        return (explicit or text or filename or page_title).strip()


class Scraper:
    def __init__(self, fetcher: PageFetcher, extractor: HtmlVideoExtractor | None = None) -> None:
        self.fetcher = fetcher
        self.extractor = extractor or HtmlVideoExtractor()

    async def discover(self, page_url: str) -> tuple[str, list[DiscoveredVideo]]:
        html, final_url = await self.fetcher.fetch_html(page_url)
        return final_url, self.extractor.extract(html, final_url)
