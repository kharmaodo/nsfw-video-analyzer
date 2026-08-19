from app.core.config import Settings


def test_content_types_can_be_configured_as_csv(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_ALLOWED_CONTENT_TYPES", "video/mp4, video/webm")

    settings = Settings()

    assert settings.video_allowed_content_types == ("video/mp4", "video/webm")
