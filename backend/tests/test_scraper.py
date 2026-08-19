import pytest
import httpx

from app.core.config import Settings
from app.services.scraper import HtmlVideoExtractor, PageFetcher, PageTooLargeError
from app.services.url_security import UnsafeUrlError, UrlSecurityPolicy


def test_extracts_resolves_and_deduplicates_video_links() -> None:
    html = """
    <html><head><title>Catalogue</title></head><body>
      <a href="/media/demo.mp4?token=abc">Cours vidéo</a>
      <video src="https://cdn.example/movie.webm"></video>
      <source src="https://cdn.example/movie.webm" type="video/webm">
      <source src="/streams/no-extension" type="video/mp4">
      <a href="/document.pdf">Document</a>
    </body></html>
    """

    videos = HtmlVideoExtractor().extract(html, "https://media.example/catalogue/page.html")

    assert [video.video_url for video in videos] == [
        "https://media.example/media/demo.mp4?token=abc",
        "https://cdn.example/movie.webm",
        "https://media.example/streams/no-extension",
    ]
    assert videos[0].title == "Cours vidéo"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "ftp://example.com/video.mp4",
        "http://localhost/video.mp4",
    ],
)
@pytest.mark.asyncio
async def test_ssrf_policy_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        await UrlSecurityPolicy().validate(url)


@pytest.mark.asyncio
async def test_ssrf_policy_accepts_public_resolution() -> None:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return ["93.184.216.34"]

    await UrlSecurityPolicy(resolver=resolver).validate("https://example.com/catalogue")


@pytest.mark.asyncio
async def test_page_fetcher_follows_validated_redirect() -> None:
    validated: list[str] = []

    class SecuritySpy:
        async def validate(self, url: str) -> None:
            validated.append(url)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "start.example":
            return httpx.Response(302, headers={"location": "https://final.example/catalogue"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body>OK</body></html>",
        )

    fetcher = PageFetcher(
        Settings(),
        security=SecuritySpy(),  # type: ignore[arg-type]
        transport=httpx.MockTransport(handler),
    )
    html, final_url = await fetcher.fetch_html("https://start.example")

    assert html == "<html><body>OK</body></html>"
    assert final_url == "https://final.example/catalogue"
    assert validated == ["https://start.example", "https://final.example/catalogue"]


@pytest.mark.asyncio
async def test_page_fetcher_rejects_declared_oversized_page() -> None:
    class AllowAll:
        async def validate(self, _url: str) -> None:
            return None

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "2048"},
            content=b"small",
        )
    )
    fetcher = PageFetcher(
        Settings(scraper_max_html_bytes=1024),
        security=AllowAll(),  # type: ignore[arg-type]
        transport=transport,
    )

    with pytest.raises(PageTooLargeError):
        await fetcher.fetch_html("https://public.example")
