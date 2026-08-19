from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from app.core.config import Settings


class NsfwClassificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FramePrediction:
    path: Path
    nsfw_score: float


@dataclass(frozen=True)
class NsfwSummary:
    maximum_score: float
    average_score: float
    positive_frames: int
    total_frames: int
    is_nsfw: bool


def aggregate_predictions(
    predictions: list[FramePrediction],
    threshold: float,
    minimum_positive_frames: int,
) -> NsfwSummary:
    if not predictions:
        raise NsfwClassificationError("Aucune prédiction NSFW à agréger.")
    scores = [prediction.nsfw_score for prediction in predictions]
    if any(score < 0 or score > 1 for score in scores):
        raise NsfwClassificationError("Le modèle a retourné un score hors de l’intervalle [0, 1].")
    positive = sum(score >= threshold for score in scores)
    return NsfwSummary(
        maximum_score=max(scores),
        average_score=fmean(scores),
        positive_frames=positive,
        total_frames=len(scores),
        is_nsfw=positive >= minimum_positive_frames,
    )


class TransformersNsfwClassifier:
    def __init__(self, settings: Settings, pipeline_factory=None) -> None:  # type: ignore[no-untyped-def]
        self.settings = settings
        self.pipeline_factory = pipeline_factory
        self._pipeline = None

    @property
    def model_identifier(self) -> str:
        return f"{self.settings.nsfw_model_name}@{self.settings.nsfw_model_revision}"

    def _get_pipeline(self):  # type: ignore[no-untyped-def]
        if self._pipeline is None:
            factory = self.pipeline_factory
            if factory is None:
                try:
                    from transformers import pipeline
                except ImportError as exc:
                    raise NsfwClassificationError(
                        "Les dépendances ML ne sont pas installées. Utilisez pip install '.[ml]'."
                    ) from exc
                factory = pipeline
            try:
                self._pipeline = factory(
                    "image-classification",
                    model=self.settings.nsfw_model_name,
                    revision=self.settings.nsfw_model_revision,
                    device=self.settings.nsfw_device,
                    model_kwargs={"use_safetensors": True},
                )
            except Exception as exc:
                raise NsfwClassificationError(f"Chargement du modèle NSFW impossible : {exc}") from exc
        return self._pipeline

    def classify(self, frame_paths: tuple[Path, ...]) -> NsfwSummary:
        if not frame_paths:
            raise NsfwClassificationError("Aucune image à analyser.")
        missing = [str(path) for path in frame_paths if not path.is_file()]
        if missing:
            raise NsfwClassificationError(f"Image temporaire introuvable : {missing[0]}.")

        try:
            from PIL import Image
        except ImportError as exc:
            raise NsfwClassificationError(
                "Pillow n’est pas installé. Utilisez pip install '.[ml]'."
            ) from exc

        images = []
        try:
            for path in frame_paths:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            raw_results: list[list[dict[str, Any]]] = self._get_pipeline()(
                images,
                batch_size=self.settings.nsfw_batch_size,
            )
        except NsfwClassificationError:
            raise
        except Exception as exc:
            raise NsfwClassificationError(f"Inférence NSFW impossible : {exc}") from exc
        finally:
            for image in images:
                image.close()

        if len(raw_results) != len(frame_paths):
            raise NsfwClassificationError("Le modèle n’a pas retourné une prédiction par image.")
        predictions = [
            FramePrediction(path, self._extract_nsfw_score(result))
            for path, result in zip(frame_paths, raw_results, strict=True)
        ]
        return aggregate_predictions(
            predictions,
            threshold=self.settings.nsfw_threshold,
            minimum_positive_frames=self.settings.nsfw_min_positive_frames,
        )

    @staticmethod
    def _extract_nsfw_score(results: list[dict[str, Any]]) -> float:
        for result in results:
            if str(result.get("label", "")).strip().lower() == "nsfw":
                try:
                    return float(result["score"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise NsfwClassificationError("Score NSFW invalide.") from exc
        raise NsfwClassificationError("La classe 'nsfw' est absente de la sortie du modèle.")
