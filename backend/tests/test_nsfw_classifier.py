from pathlib import Path

import pytest
from PIL import Image

from app.core.config import Settings
from app.services.nsfw_classifier import (
    FramePrediction,
    NsfwClassificationError,
    TransformersNsfwClassifier,
    aggregate_predictions,
)


def test_aggregates_scores_with_minimum_positive_frames() -> None:
    predictions = [
        FramePrediction(Path("a.jpg"), 0.20),
        FramePrediction(Path("b.jpg"), 0.85),
        FramePrediction(Path("c.jpg"), 0.70),
    ]

    summary = aggregate_predictions(predictions, threshold=0.60, minimum_positive_frames=2)

    assert summary.maximum_score == 0.85
    assert summary.average_score == pytest.approx(0.583333, rel=1e-5)
    assert summary.positive_frames == 2
    assert summary.total_frames == 3
    assert summary.is_nsfw is True


def test_requires_enough_positive_frames() -> None:
    predictions = [
        FramePrediction(Path("a.jpg"), 0.80),
        FramePrediction(Path("b.jpg"), 0.10),
    ]
    summary = aggregate_predictions(predictions, threshold=0.60, minimum_positive_frames=2)
    assert summary.is_nsfw is False


def test_rejects_empty_or_invalid_predictions() -> None:
    with pytest.raises(NsfwClassificationError):
        aggregate_predictions([], 0.60, 1)
    with pytest.raises(NsfwClassificationError):
        aggregate_predictions([FramePrediction(Path("a.jpg"), 1.2)], 0.60, 1)


def test_extracts_nsfw_label_case_insensitively() -> None:
    score = TransformersNsfwClassifier._extract_nsfw_score(
        [{"label": "normal", "score": 0.2}, {"label": "NSFW", "score": 0.8}]
    )
    assert score == 0.8


def test_rejects_output_without_nsfw_label() -> None:
    with pytest.raises(NsfwClassificationError, match="absente"):
        TransformersNsfwClassifier._extract_nsfw_score(
            [{"label": "normal", "score": 1.0}]
        )


def test_transformers_adapter_batches_real_image_files(tmp_path) -> None:
    paths = (tmp_path / "a.jpg", tmp_path / "b.jpg")
    for path in paths:
        Image.new("RGB", (32, 32), color="white").save(path)

    received: dict[str, object] = {}

    def factory(task: str, **kwargs):
        received["task"] = task
        received["kwargs"] = kwargs

        def classify(images, batch_size: int):
            received["batch_size"] = batch_size
            received["images"] = len(images)
            return [
                [{"label": "normal", "score": 0.9}, {"label": "nsfw", "score": 0.1}],
                [{"label": "normal", "score": 0.2}, {"label": "nsfw", "score": 0.8}],
            ]

        return classify

    settings = Settings(nsfw_threshold=0.6, nsfw_min_positive_frames=1, nsfw_batch_size=2)
    classifier = TransformersNsfwClassifier(settings, pipeline_factory=factory)

    summary = classifier.classify(paths)

    assert summary.is_nsfw is True
    assert summary.maximum_score == 0.8
    assert received["task"] == "image-classification"
    assert received["batch_size"] == 2
    assert received["images"] == 2
    assert received["kwargs"]["model_kwargs"] == {"use_safetensors": True}  # type: ignore[index]
