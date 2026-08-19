import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.core.config import Settings, get_settings


class MediaResolutionError(RuntimeError):
    """Erreur lors de la résolution d’une URL de plateforme."""


@dataclass(frozen=True)
class ResolvedMedia:
    source_url: str
    stream_url: str
    title: str


def is_youtube_url(url: str) -> bool:
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")

    return hostname in {
        "youtu.be",
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    }


class MediaResolver:
    """
    Résout une URL stable de plateforme vers une URL de flux exploitable.

    Les URL directes sont retournées sans modification.
    Les URL YouTube sont résolues avec yt-dlp.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def resolve(self, source_url: str) -> ResolvedMedia:
        if not is_youtube_url(source_url):
            return ResolvedMedia(
                source_url=source_url,
                stream_url=source_url,
                title="Vidéo distante",
            )

        return await asyncio.to_thread(
            self._resolve_youtube,
            source_url,
        )

    def _youtube_options(self) -> dict[str, object]:
        options: dict[str, object] = {
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 20,
            "js_runtimes": {
                "node": {},
            },
        }

        cookies_file = self.settings.ytdlp_cookies_file

        if cookies_file:
            cookie_path = Path(cookies_file).expanduser()

            if not cookie_path.is_file():
                raise MediaResolutionError(
                    f"Fichier de cookies YouTube introuvable : {cookie_path}"
                )

            options["cookiefile"] = str(cookie_path)

        return options

    def _resolve_youtube(self, source_url: str) -> ResolvedMedia:
        options = self._youtube_options()

        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(
                    source_url,
                    download=False,
                )
        except DownloadError as exc:
            raise MediaResolutionError(
                f"Impossible de résoudre la vidéo YouTube : {exc}"
            ) from exc

        stream_url = info.get("url") if info else None

        if (
            not isinstance(stream_url, str)
            or not stream_url.startswith(("http://", "https://"))
        ):
            raise MediaResolutionError(
                "YouTube n’a retourné aucun flux vidéo exploitable."
            )

        title = str(info.get("title") or "Vidéo YouTube")

        return ResolvedMedia(
            source_url=source_url,
            stream_url=stream_url,
            title=title[:500],
        )
