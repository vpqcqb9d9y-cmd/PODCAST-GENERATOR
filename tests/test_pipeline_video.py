import json
from pathlib import Path

import pytest

from src.pipeline import runner as runner_module
from src.pipeline.runner import LecturePipeline
from src.utils.config import Settings
from src.utils.quality_checker import CheckResult, QualityReport


class DummyDialogueGenerator:
    def generate(self, transcript_text, metadata, run_paths, force=False):
        dialogue = {
            "dialogue": [
                {"speaker": "Roee", "text": "שלום, זה ניסוי."},
                {"speaker": "Noa", "text": "בדיקה קצרה לווידאו."},
            ]
        }
        run_paths.dialogue_path.write_text(
            json.dumps(dialogue, ensure_ascii=False), encoding="utf-8"
        )
        return run_paths.dialogue_path


class DummyMetadataIngestor:
    def enrich(self, metadata, materials, urls, run_paths):
        return metadata


class DummyTTSSynthesizer:
    def synthesize(self, dialogue_path, run_paths, force=False):
        data = json.loads(dialogue_path.read_text(encoding="utf-8"))
        segment_paths = []
        for idx, entry in enumerate(data["dialogue"], start=1):
            target = run_paths.audio_dir / f"{idx:04d}_{entry['speaker'].lower()}.wav"
            target.write_bytes(b"wavdata")
            segment_paths.append(target)
        return segment_paths


class DummyStitcher:
    def build(self, segments, metadata, run_paths):
        run_paths.final_audio_path.write_bytes(b"audio")
        return run_paths.final_audio_path


class DummyManimGenerator:
    def build_scenes(self, dialogue_json, run_paths):
        scene = run_paths.visuals_dir / "scene_001.mp4"
        scene.write_bytes(b"scene")
        return [scene]


class DummyGoogleAIGenerator:
    def build_visuals_for_dialogue(
        self,
        dialogue_json,
        metadata,
        run_paths,
        generate_images=True,
        generate_videos=False,
        image_count=3,
        visual_metadata=None,
    ):
        files = []
        for idx in range(1, image_count + 1):
            img = run_paths.visuals_dir / f"image_{idx:02d}.png"
            img.write_bytes(b"img")
            files.append(img)
        return files


class DummyVideoComposer:
    def compose(self, dialogue_json, metadata, run_paths):
        run_paths.final_video_path.write_bytes(b"video")


class DummyQualityChecker:
    def run_preflight_checks(self, **kwargs):
        report = QualityReport()
        report.add_preflight(CheckResult("api_keys", "PASS", "ok"))
        return report

    def run_postprocess_checks(self, **kwargs):
        report = QualityReport()
        report.add_postprocess(CheckResult("final_video", "PASS", "ok"))
        return report

    def get_summary(self):
        return "All checks green"


class DummyDeckExporter:
    def export(self, metadata, dialogue_json, path: Path):
        path.write_text("ppt", encoding="utf-8")


class DummyStoryExporter:
    def export(self, metadata, dialogue_json, run_dir: Path):
        story = run_dir / "story.md"
        story.write_text("# Story", encoding="utf-8")
        return story


@pytest.mark.parametrize("tts_provider", ["elevenlabs", "azure"])
def test_pipeline_creates_video_with_dummy_components(tmp_path, monkeypatch, tts_provider):
    transcript_path = tmp_path / "lecture.txt"
    transcript_path.write_text("Sample transcript line.", encoding="utf-8")

    metadata_path = tmp_path / "metadata.json"
    metadata = {"topic": "Test Lecture", "date": "2025-12-04"}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    settings = Settings(
        openai_endpoint="https://example.com",
        openai_api_key="fake",
        openai_deployment="gpt",
        openai_api_version="2024-12-01-preview",
        speech_key="fake-speech",
        speech_region="westeurope",
        elevenlabs_api_key="fake-eleven",
        default_tts_provider=tts_provider,
        output_base_dir=tmp_path / "outputs",
    )

    pipeline = LecturePipeline(settings=settings, dry_run=False)
    pipeline.dialogue = DummyDialogueGenerator()
    pipeline.metadata_ingestor = DummyMetadataIngestor()
    pipeline.stitcher = DummyStitcher()
    pipeline.manim = DummyManimGenerator()
    pipeline.google_ai = DummyGoogleAIGenerator()
    pipeline.video = DummyVideoComposer()
    pipeline.quality_checker = DummyQualityChecker()
    pipeline.deck_exporter = DummyDeckExporter()
    pipeline.story_exporter = DummyStoryExporter()

    dummy_tts = DummyTTSSynthesizer()
    monkeypatch.setattr(
        runner_module,
        "create_tts_synthesizer",
        lambda *args, **kwargs: dummy_tts,
    )

    run_paths = pipeline.run(
        transcript_path,
        metadata_path,
        output_dir=settings.output_base_dir,
        skip_visuals=False,
        tts_provider=tts_provider,
    )

    assert run_paths.final_video_path.exists(), "Video composer did not produce output file."
    log_text = run_paths.log_path.read_text(encoding="utf-8")
    assert "Video composition completed" in log_text
    visual_metadata_path = run_paths.run_dir / "visual_metadata.json"
    assert visual_metadata_path.exists(), "visual_metadata.json was not created automatically."
    visual_payload = json.loads(visual_metadata_path.read_text(encoding="utf-8"))
    assert visual_payload.get("images"), "Auto-generated visual metadata is missing image prompts."

