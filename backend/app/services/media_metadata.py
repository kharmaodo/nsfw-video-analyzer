from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import exifread


@dataclass(frozen=True)
class ExtractedMediaMetadata:
    title: str | None = None
    media_created_at: datetime | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None


def normalize_title(value: object | None) -> str | None:
    if value is None:
        return None
    title = str(value).replace("\x00", "").strip()
    return title[:500] or None


def parse_media_created_at(value: object | None) -> datetime | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, pattern)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract_image_metadata(path: Path) -> ExtractedMediaMetadata:
    try:
        with path.open("rb") as source:
            tags = exifread.process_file(source, details=False)
    except (OSError, ValueError):
        return ExtractedMediaMetadata()

    title = next(
        (
            normalize_title(tags.get(key))
            for key in (
                "Image ImageDescription",
                "Image XPTitle",
                "EXIF UserComment",
            )
            if normalize_title(tags.get(key))
        ),
        None,
    )
    created_at = next(
        (
            parse_media_created_at(tags.get(key))
            for key in (
                "EXIF DateTimeOriginal",
                "EXIF DateTimeDigitized",
                "Image DateTime",
            )
            if parse_media_created_at(tags.get(key))
        ),
        None,
    )

    latitude = _gps_coordinate(
        tags.get("GPS GPSLatitude"),
        tags.get("GPS GPSLatitudeRef"),
    )
    longitude = _gps_coordinate(
        tags.get("GPS GPSLongitude"),
        tags.get("GPS GPSLongitudeRef"),
    )

    return ExtractedMediaMetadata(
        title=title,
        media_created_at=created_at,
        gps_latitude=latitude,
        gps_longitude=longitude,
    )


def _gps_coordinate(value: object | None, reference: object | None) -> float | None:
    if value is None or reference is None:
        return None

    values = getattr(value, "values", value)
    try:
        degrees, minutes, seconds = list(values)[:3]
        coordinate = (
            float(degrees)
            + float(minutes) / 60
            + float(seconds) / 3600
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    if str(reference).strip().upper() in {"S", "W"}:
        coordinate *= -1
    return coordinate
