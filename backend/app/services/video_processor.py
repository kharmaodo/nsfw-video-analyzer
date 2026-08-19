import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.services.url_security import UrlSecurityPolicy


class VideoProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str


class AsyncCommandRunner:
    async def run(self, command: list[str], timeout_seconds: float) -> CommandResult:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise VideoProcessingError(f"Exécutable indisponible : {command[0]}.") from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise VideoProcessingError(
                f"La commande {command[0]} a dépassé le délai autorisé."
            ) from exc

        decoded_stdout = stdout.decode("utf-8", errors="replace")
        decoded_stderr = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0:
            detail = decoded_stderr.strip()[-1000:] or "erreur inconnue"
            raise VideoProcessingError(f"Échec de {command[0]} : {detail}")
        return CommandResult(decoded_stdout, decoded_stderr)


@dataclass(frozen=True)
class SampleWindow:
    start_seconds: float
    duration_seconds: float


@dataclass(frozen=True)
class VideoSample:
    source_duration_seconds: float
    window: SampleWindow
    frame_paths: tuple[Path, ...]


def calculate_central_window(
    source_duration_seconds: float,
    maximum_duration_seconds: float = 300,
) -> SampleWindow:
    if source_duration_seconds <= 0:
        raise VideoProcessingError("La durée de la vidéo doit être positive.")
    duration = min(source_duration_seconds, maximum_duration_seconds)
    start = max(0.0, (source_duration_seconds - duration) / 2)
    return SampleWindow(start_seconds=start, duration_seconds=duration)


class VideoProcessor:
    PROTOCOL_WHITELIST = "http,https,tcp,tls,crypto"

    def __init__(
        self,
        settings: Settings,
        runner: AsyncCommandRunner | None = None,
        security: UrlSecurityPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or AsyncCommandRunner()
        self.security = security or UrlSecurityPolicy()

    async def probe_duration(self, url: str) -> float:
        await self.security.validate(url)
        command = [
            self.settings.ffprobe_binary,
            "-v",
            "error",
            "-protocol_whitelist",
            self.PROTOCOL_WHITELIST,
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            url,
        ]
        result = await self.runner.run(command, self.settings.video_process_timeout_seconds)
        try:
            duration = float(json.loads(result.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VideoProcessingError("ffprobe n’a pas retourné une durée valide.") from exc
        if duration <= 0:
            raise VideoProcessingError("ffprobe a retourné une durée non positive.")
        return duration

    async def extract_central_frames(self, video_id: int, url: str) -> VideoSample:
        duration = await self.probe_duration(url)
        window = calculate_central_window(
            duration,
            self.settings.video_clip_duration_seconds,
        )
        output_directory = Path(self.settings.video_temporary_directory) / f"video-{video_id}"
        output_directory.mkdir(parents=True, exist_ok=True)
        for stale_frame in output_directory.glob("frame-*.jpg"):
            stale_frame.unlink()

        output_pattern = output_directory / "frame-%05d.jpg"
        command = [
            self.settings.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-protocol_whitelist",
            self.PROTOCOL_WHITELIST,
            "-ss",
            f"{window.start_seconds:.3f}",
            "-i",
            url,
            "-t",
            f"{window.duration_seconds:.3f}",
            "-vf",
            f"fps=1/{self.settings.video_frame_interval_seconds:g},scale={self.settings.video_frame_width}:-2",
            "-an",
            "-fps_mode",
            "vfr",
            "-y",
            str(output_pattern),
        ]
        await self.runner.run(command, self.settings.video_process_timeout_seconds)
        frames = tuple(sorted(output_directory.glob("frame-*.jpg")))
        if not frames:
            raise VideoProcessingError("FFmpeg n’a extrait aucune image.")
        return VideoSample(duration, window, frames)

