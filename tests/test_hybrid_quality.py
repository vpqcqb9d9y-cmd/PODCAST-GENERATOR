from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List
import wave

import numpy as np
import pytest
from moviepy.editor import ColorClip, VideoFileClip, concatenate_videoclips
from moviepy.video.VideoClip import ImageClip

from src.visuals.video_composer import VideoComposer
from src.utils.guardian import ProductionGuardian


def check_dependencies() -> Dict[str, bool]:
    results = {}
    for mod in ("cv2", "moviepy", "manim"):
        try:
            __import__(mod)
            results[mod] = True
        except Exception:
            results[mod] = False
    return results


def _make_silent_audio(seconds: float, path: Path) -> None:
    sample_rate = 44100
    total_samples = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        silence = (b"\x00\x00") * total_samples
        wf.writeframes(silence)


def _make_color_video(path: Path, color: tuple[int, int, int], duration: float) -> None:
    clip = ColorClip(size=(640, 360), color=color, duration=duration)
    clip.write_videofile(str(path), fps=24, codec="libx264", audio=False, logger=None)
    clip.close()


class DummyRunPaths:
    def __init__(self, base: Path) -> None:
        self.run_dir = base
        self.visuals_dir = base
        self.final_audio_path = base / "audio.wav"
        self.final_video_path = base / "final_video.mp4"

    def log(self, *_: object, **__: object) -> None:
        return


def _make_settings(preview: bool = True, image_count: int = 3) -> SimpleNamespace:
    return SimpleNamespace(preview_mode=preview, image_count=image_count)


def _dummy_dialogue(turns: int = 3) -> Dict:
    return {"dialogue": [{"speaker": "A", "text": f"Line {i}"} for i in range(turns)]}


def test_dependency_check():
    deps = check_dependencies()
    assert deps.get("moviepy") is True
    # cv2/manim may be optional in some envs; ensure keys exist
    assert "cv2" in deps and "manim" in deps


def test_asset_ordering_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = _make_settings()
    composer = VideoComposer(settings)
    run_paths = DummyRunPaths(tmp_path)
    _make_silent_audio(5.0, run_paths.final_audio_path)

    img1 = tmp_path / "img_01.png"
    img3 = tmp_path / "img_03.png"
    vid2 = tmp_path / "vid_02.mp4"
    for img in (img1, img3):
        data = (np.random.rand(900, 900, 3) * 255).astype("uint8")
        from PIL import Image

        Image.fromarray(data).save(img)
    _make_color_video(vid2, (255, 0, 0), 1.0)

    # Avoid strict image validation to focus on ordering logic
    monkeypatch.setattr(composer, "get_valid_images", lambda *args, **kwargs: [img1, img3])

    clips = composer.create_timeline(
        dialogue_json=_dummy_dialogue(),
        metadata={},
        audio_file=run_paths.final_audio_path,
        animations_dir=tmp_path,
        run_paths=run_paths,
        asset_paths=[img1, vid2, img3],
        adaptive_timeline=False,
        apply_ken_burns=False,
    )

    assert len(clips) == 3
    assert isinstance(clips[0], ImageClip)
    assert isinstance(clips[1], VideoFileClip)
    assert isinstance(clips[2], ImageClip)


def test_duration_calculation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = _make_settings()
    composer = VideoComposer(settings)
    run_paths = DummyRunPaths(tmp_path)
    _make_silent_audio(10.0, run_paths.final_audio_path)

    img1 = tmp_path / "img_01.png"
    img2 = tmp_path / "img_02.png"
    for img in (img1, img2):
        data = (np.random.rand(900, 900, 3) * 255).astype("uint8")
        from PIL import Image

        Image.fromarray(data).save(img)
    vid = tmp_path / "video_02.mp4"
    _make_color_video(vid, (0, 255, 0), 4.0)

    monkeypatch.setattr(composer, "get_valid_images", lambda *args, **kwargs: [img1, img2])

    clips = composer.create_timeline(
        dialogue_json=_dummy_dialogue(),
        metadata={},
        audio_file=run_paths.final_audio_path,
        animations_dir=tmp_path,
        run_paths=run_paths,
        asset_paths=[img1, img2, vid],
        adaptive_timeline=False,
        apply_ken_burns=False,
    )

    durations = [float(getattr(c, "duration", 0.0)) for c in clips]
    assert len(clips) == 3
    assert durations[1] == pytest.approx(4.0, abs=0.05)
    assert durations[0] == pytest.approx(3.0, abs=0.05)
    assert durations[2] == pytest.approx(3.0, abs=0.05)
    assert math.isclose(sum(durations), 10.0, rel_tol=1e-2, abs_tol=0.05)


@pytest.mark.skipif(not check_dependencies().get("cv2"), reason="cv2 is required for guardian validation")
def test_guardian_fade_in_allowance(tmp_path: Path):
    dummy_settings = _make_settings()
    dummy_report = SimpleNamespace(recommendations=[])
    run_paths = DummyRunPaths(tmp_path)
    guardian = ProductionGuardian(run_paths, dummy_settings, dummy_report)

    fade_video = tmp_path / "fade.mp4"
    black = ColorClip(size=(320, 240), color=(0, 0, 0), duration=1.0)
    bright = ColorClip(size=(320, 240), color=(255, 255, 255), duration=1.0)
    concat = concatenate_videoclips([black, bright])
    concat.write_videofile(str(fade_video), fps=24, codec="libx264", audio=False, logger=None)
    concat.close()
    black.close()
    bright.close()

    validated = guardian._validate_videos([fade_video])
    assert fade_video in validated
    assert fade_video.exists()

    full_black = tmp_path / "black.mp4"
    _make_color_video(full_black, (0, 0, 0), 1.0)
    validated_after = guardian._validate_videos([full_black])
    assert full_black not in validated_after
    assert not full_black.exists()


def test_full_hybrid_composition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = _make_settings(preview=True, image_count=2)
    composer = VideoComposer(settings)
    run_paths = DummyRunPaths(tmp_path)

    _make_silent_audio(5.0, run_paths.final_audio_path)

    img = tmp_path / "image_01.png"
    data = (np.random.rand(900, 900, 3) * 255).astype("uint8")
    from PIL import Image

    Image.fromarray(data).save(img)

    vid = tmp_path / "AzureScene2.mp4"
    _make_color_video(vid, (0, 0, 255), 2.0)

    monkeypatch.setattr(composer, "get_valid_images", lambda *args, **kwargs: [img])

    dialogue_json = _dummy_dialogue()
    metadata = {"topic": "Test"}

    composer.compose(
        dialogue_json=dialogue_json,
        metadata=metadata,
        run_paths=run_paths,
        asset_paths=[img, vid],
        adaptive_timeline=False,
        apply_ken_burns=False,
    )

    assert run_paths.final_video_path.exists()
    with VideoFileClip(str(run_paths.final_video_path)) as clip:
        assert clip.duration == pytest.approx(5.0, abs=0.25)
        assert clip.audio is not None

