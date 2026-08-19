from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.video_processor import (
    CommandResult,
    VideoProcessingError,
    VideoProcessor,
    calculate_central_window,
)


class AllowAll:
    async def validate(self, _url: str) -> None:
        return None


class FakeRunner:
    def __init__(self, temporary_directory: Path, duration: float = 1200) -> None:
        self.temporary_directory = temporary_directory
        self.duration = duration
        self.commands: list[list[str]] = []

    async def run(self, command: list[str], _timeout_seconds: float) -> CommandResult:
        self.commands.append(command)
        if command[0] == "ffprobe":
            return CommandResult(f'{{"format":{{"duration":"{self.duration}"}}}}', "")
        output_pattern = Path(command[-1])
        output_pattern.parent.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            (output_pattern.parent / f"frame-{index:05d}.jpg").write_bytes(b"jpeg")
        return CommandResult("", "")


def test_calculates_central_five_minute_window() -> None:
    window = calculate_central_window(1200, 300)
    assert window.start_seconds == 450
    assert window.duration_seconds == 300


def test_short_video_uses_its_whole_duration() -> None:
    window = calculate_central_window(90, 300)
    assert window.start_seconds == 0
    assert window.duration_seconds == 90


def test_rejects_invalid_duration() -> None:
    with pytest.raises(VideoProcessingError):
        calculate_central_window(0, 300)


@pytest.mark.asyncio
async def test_probes_and_extracts_frames(tmp_path) -> None:
    settings = Settings(video_temporary_directory=str(tmp_path))
    runner = FakeRunner(tmp_path)
    processor = VideoProcessor(
        settings,
        runner=runner,  # type: ignore[arg-type]
        security=AllowAll(),  # type: ignore[arg-type]
    )

    sample = await processor.extract_central_frames(7, "https://cdn.example/video.mp4")

    assert sample.source_duration_seconds == 1200
    assert sample.window.start_seconds == 450
    assert len(sample.frame_paths) == 3
    ffmpeg_command = runner.commands[1]
    assert ffmpeg_command[ffmpeg_command.index("-ss") + 1] == "450.000"
    assert ffmpeg_command[ffmpeg_command.index("-t") + 1] == "300.000"
    assert "fps=1/10,scale=384:-2" in ffmpeg_command


@pytest.mark.asyncio
async def test_rejects_invalid_ffprobe_output(tmp_path) -> None:
    class InvalidRunner:
        async def run(self, _command, _timeout):
            return CommandResult("{}", "")

    processor = VideoProcessor(
        Settings(video_temporary_directory=str(tmp_path)),
        runner=InvalidRunner(),  # type: ignore[arg-type]
        security=AllowAll(),  # type: ignore[arg-type]
    )
    with pytest.raises(VideoProcessingError, match="durée valide"):
        await processor.probe_duration("https://cdn.example/video.mp4")

