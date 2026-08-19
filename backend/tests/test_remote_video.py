import httpx
import pytest

from app.core.config import Settings
from app.services.remote_video import RemoteVideoError, RemoteVideoInspector


class AllowAll:
    async def validate(self, _url: str) -> None:
        return None


@pytest.mark.asyncio
async def test_head_inspection_returns_video_metadata() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={
                "content-type": "video/mp4",
                "content-length": "1048576",
                "accept-ranges": "bytes",
            },
        )
    )
    inspector = RemoteVideoInspector(
        Settings(), security=AllowAll(), transport=transport  # type: ignore[arg-type]
    )

    metadata = await inspector.inspect("https://cdn.example/video.mp4")

    assert metadata.size_bytes == 1048576
    assert metadata.content_type == "video/mp4"
    assert metadata.accepts_ranges is True


@pytest.mark.asyncio
async def test_falls_back_to_streaming_range_get_when_head_is_rejected() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(405)
        assert request.headers["range"] == "bytes=0-0"
        return httpx.Response(
            206,
            headers={
                "content-type": "video/webm",
                "content-range": "bytes 0-0/5000000",
            },
            content=b"x",
        )

    inspector = RemoteVideoInspector(
        Settings(),
        security=AllowAll(),  # type: ignore[arg-type]
        transport=httpx.MockTransport(handler),
    )
    metadata = await inspector.inspect("https://cdn.example/video.webm")

    assert methods == ["HEAD", "GET"]
    assert metadata.size_bytes == 5000000
    assert metadata.accepts_ranges is True


@pytest.mark.asyncio
async def test_rejects_video_without_range_support() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "video/mp4", "content-length": "1000"},
        )
    )
    inspector = RemoteVideoInspector(
        Settings(), security=AllowAll(), transport=transport  # type: ignore[arg-type]
    )

    with pytest.raises(RemoteVideoError, match="Range"):
        await inspector.inspect("https://cdn.example/video.mp4")


@pytest.mark.asyncio
async def test_rejects_oversized_video() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={
                "content-type": "video/mp4",
                "content-length": "2000",
                "accept-ranges": "bytes",
            },
        )
    )
    inspector = RemoteVideoInspector(
        Settings(video_max_size_bytes=1024),
        security=AllowAll(),  # type: ignore[arg-type]
        transport=transport,
    )

    with pytest.raises(RemoteVideoError, match="dépasse"):
        await inspector.inspect("https://cdn.example/video.mp4")

