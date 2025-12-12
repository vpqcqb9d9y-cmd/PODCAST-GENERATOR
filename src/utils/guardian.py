from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pydub import AudioSegment

from .logging import get_logger
from .quality_checker import QualityReport
from . import RunPaths, Settings

import numpy as np

try:  # pragma: no cover - optional dependency
    import cv2  # type: ignore
except Exception:  # pragma: no cover - headless fallback
    cv2 = None


@dataclass
class GuardianResult:
    """Result of the guardian healing pass."""

    assets: List[Path]
    adaptive_timeline: bool = False
    ken_burns: bool = True
    audio_normalized: bool = False


class ProductionGuardian:
    """
    Final safeguard layer before video composition.

    Responsibilities:
    - Validate and heal visual assets (remove corrupt/black frames, regenerate once if possible).
    - Decide whether to run in adaptive timeline mode (stretch existing frames, no placeholders).
    - Normalize final audio loudness to avoid clipping/quiet renders.
    """

    def __init__(self, run_paths: RunPaths, settings: Settings, quality_report: QualityReport) -> None:
        self.run_paths = run_paths
        self.settings = settings
        self.quality_report = quality_report
        self.logger = get_logger(self.__class__.__name__)

    def optimize_and_fix(
        self,
        metadata: Optional[Dict] = None,
        visual_metadata: Optional[Dict] = None,
        extra_assets: Optional[List[Path]] = None,
    ) -> GuardianResult:
        visuals_dir = self.run_paths.visuals_dir
        visuals_dir.mkdir(parents=True, exist_ok=True)

        expected_images = self._expected_image_count()

        extra_assets = extra_assets or []
        image_candidates = list(visuals_dir.glob("*.png")) + list(visuals_dir.glob("*.jpg")) + list(visuals_dir.glob("*.jpeg"))
        image_candidates.extend([p for p in extra_assets if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
        valid_images = self._validate_images(image_candidates)

        video_candidates = list(visuals_dir.glob("*.mp4")) + list(visuals_dir.glob("*.mov")) + list(visuals_dir.glob("*.webm"))
        video_candidates.extend([p for p in extra_assets if p.suffix.lower() in {".mp4", ".mov", ".webm"}])
        video_assets: List[Path] = sorted(set(video_candidates))

        # One retry: attempt regeneration when we have fewer images than requested.
        if len(valid_images) < expected_images:
            missing = expected_images - len(valid_images)
            regenerated = self._attempt_regeneration(missing, metadata or {}, visual_metadata or {})
            if regenerated:
                # Re-validate including the regenerated assets
                valid_images = self._validate_images(valid_images + regenerated)

        adaptive = False
        if len(valid_images) < max(1, expected_images):
            adaptive = True
            self.quality_report.recommendations.append(
                f"Adaptive timeline enabled: using {len(valid_images)} of {expected_images} requested visuals."
            )

        audio_normalized = self._normalize_audio()

        return GuardianResult(
            assets=sorted(set(valid_images + video_assets)),
            adaptive_timeline=adaptive,
            ken_burns=True,
            audio_normalized=audio_normalized,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _expected_image_count(self) -> int:
        try:
            count = int(getattr(self.settings, "image_count", 0) or 0)
        except Exception:
            count = 0
        return max(1, count or 5)

    def _validate_images(self, images: List[Path]) -> List[Path]:
        """Filter out unreadable/black images and delete corrupt ones."""
        valid: List[Path] = []
        for image_path in images:
            try:
                if not image_path.exists():
                    continue
                if cv2 is None:
                    valid.append(image_path)
                    continue

                # Use numpy.fromfile + cv2.imdecode to handle Unicode paths on Windows
                stream = np.fromfile(str(image_path), dtype=np.uint8)
                img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
                if img is None:
                    self.logger.warning("Discarding unreadable image: %s", image_path.name)
                    image_path.unlink(missing_ok=True)
                    continue

                # Detect near-black/corrupt frames
                mean_intensity = float(cv2.mean(img)[0])
                if mean_intensity < 2.5:
                    self.logger.warning("Discarding black frame: %s (mean=%.2f)", image_path.name, mean_intensity)
                    image_path.unlink(missing_ok=True)
                    continue

                valid.append(image_path)
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.warning("Error validating %s: %s", image_path.name, exc)
        return sorted(valid)

    def _attempt_regeneration(
        self,
        missing: int,
        metadata: Dict,
        visual_metadata: Dict,
    ) -> List[Path]:
        """Best-effort regeneration using Google Imagen when available."""
        outputs: List[Path] = []
        if missing <= 0:
            return outputs

        topic = metadata.get("topic") or metadata.get("summary") or "learning content"
        topic_slug = self._slugify(topic)

        try:
            from ..visuals.google_ai_visuals import GoogleAIVisualGenerator  # type: ignore
        except Exception:
            self.logger.info("GoogleAIVisualGenerator unavailable; skipping regeneration.")
            return outputs

        try:
            generator = GoogleAIVisualGenerator(self.settings)
        except Exception as exc:
            self.logger.warning("Could not initialize GoogleAIVisualGenerator: %s", exc)
            return outputs

        if not getattr(generator, "is_available", False):
            self.logger.info("Google AI visuals not available; skipping regeneration.")
            return outputs

        for idx in range(missing):
            out_path = self.run_paths.visuals_dir / f"guardian_regen_{idx+1:02d}_{topic_slug}.png"
            try:
                prompt_source = visual_metadata.get("images", [{}])[idx % max(len(visual_metadata.get("images", [])), 1)]
                concept = prompt_source.get("prompt") or topic
            except Exception:
                concept = topic

            result = generator.generate_concept_illustration(concept=concept, context=topic, output_path=out_path)
            if result and result.exists():
                self.logger.info("Regenerated visual: %s", result.name)
                outputs.append(result)

        return outputs

    def _normalize_audio(self) -> bool:
        """Normalize final audio loudness to avoid clipping/quiet renders."""
        audio_path = self.run_paths.final_audio_path
        if not audio_path.exists():
            return False

        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as exc:  # pragma: no cover - runtime only
            self.logger.warning("Audio normalization skipped (load failed): %s", exc)
            return False

        try:
            current_lufs = audio.dBFS
            peak_db = audio.max_dBFS
        except Exception:
            current_lufs = audio.dBFS
            peak_db = -1.0

        target_lufs = -16.0
        needs_raise = current_lufs < -20.0
        needs_trim = peak_db > -1.0

        if not needs_raise and not needs_trim:
            return False

        gain_db = 0.0
        if needs_raise:
            gain_db = target_lufs - current_lufs
        if needs_trim:
            headroom = -1.0 - peak_db
            gain_db = min(gain_db, headroom) if gain_db else headroom

        if gain_db == 0.0:
            return False

        normalized = audio.apply_gain(gain_db)
        format_hint = audio_path.suffix.replace(".", "") or "mp3"
        normalized.export(audio_path, format=format_hint)
        self.logger.info(
            "Audio normalized by %.2fdB (LUFS %.2f -> %.2f, peak %.2f dBFS)",
            gain_db,
            current_lufs,
            normalized.dBFS,
            normalized.max_dBFS,
        )
        self.quality_report.recommendations.append(
            f"Audio normalized by {gain_db:.2f}dB to target loudness."
        )
        return True

    @staticmethod
    def _slugify(value: str) -> str:
        clean = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
        return clean.strip("_")[:80] or "visual"

