from __future__ import annotations

"""
Minimal validation for VideoComposer fallbacks.

Scenarios:
1. Valid image
2. Valid animation video
3. Missing/corrupt animation triggers safe fallback (no blue screen)

Outputs a single composed MP4 and prints basic checks:
- resolution 1920x1080
- fps ~30
- audio present
- detects if sampled frames are near-uniform (heuristic)
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
from moviepy.editor import AudioFileClip, ColorClip, VideoFileClip
from PIL import Image

from src.visuals.video_composer import VideoComposer


@dataclass
class _FakeSettings:
    preview_mode: bool = False
    image_count: int = 1
    target_language: str = "he"
    visual_generator: str = "manim"
    auto_video_duration: bool = True


def _write_silent_wav(path: Path, seconds: float = 2.0, sample_rate: int = 44100) -> None:
    import wave
    import struct

    frames = int(seconds * sample_rate)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        silence = struct.pack("<h", 0)
        wav.writeframes(silence * frames)


def _make_valid_assets(base: Path) -> Dict[str, Path]:
    base.mkdir(parents=True, exist_ok=True)
    image_path = base / "image_01.png"
    # Generate a higher-entropy 1920x1080 image so validation (size/resolution) passes
    width, height = 1920, 1080
    img = Image.effect_noise((width, height), 12).convert("RGB")
    img.save(image_path, "PNG", optimize=False)

    video_path = base / "animation_01.mp4"
    clip = ColorClip(size=(1920, 1080), color=(40, 40, 40), duration=2.0).set_fps(30)
    clip.write_videofile(
        str(video_path),
        codec="libx264",
        audio=False,
        fps=30,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        logger=None,
        verbose=False,
    )
    clip.close()

    corrupt_path = base / "animation_02.mp4"
    corrupt_path.write_bytes(b"")  # intentionally invalid

    audio_path = base / "audio.wav"
    _write_silent_wav(audio_path, seconds=4.0)

    return {
        "image": image_path,
        "video": video_path,
        "corrupt": corrupt_path,
        "audio": audio_path,
    }


def _sample_uniformity(video_path: Path, samples: int = 5) -> float:
    with VideoFileClip(str(video_path)) as clip:
        durations = clip.duration or 0
        values: List[float] = []
        for idx in range(samples):
            t = min(durations, (idx + 1) * durations / (samples + 1))
            frame = clip.get_frame(t)
            values.append(float(np.std(frame)))
        return float(np.mean(values))


def main() -> None:
    tmp = Path(tempfile.gettempdir()) / "composer_validation"
    assets = _make_valid_assets(tmp)

    dialogue = {
        "dialogue": [
            {"speaker": "Tester", "text": "בדיקת וידאו", "start": 0.0, "end": 2.0},
            {"speaker": "Tester", "text": "קליפ שני", "start": 2.0, "end": 4.0},
        ]
    }
    metadata = {"topic": "Validation", "key_concepts": ["בדיקה"], "summary": "בדיקת וידאו"}
    settings = _FakeSettings()
    composer = VideoComposer(settings)

    assets_list = [assets["video"], assets["image"], assets["corrupt"]]
    clips = composer.create_timeline(
        dialogue_json=dialogue,
        metadata=metadata,
        audio_file=assets["audio"],
        animations_dir=tmp,
        run_paths=None,
        asset_paths=assets_list,
        adaptive_timeline=False,
        apply_ken_burns=False,
        segment_durations=[2.0, 2.0],
    )

    output_file = tmp / "validation_output.mp4"
    composer.render_final_video(
        clips=clips,
        audio_file=assets["audio"],
        output_file=output_file,
        dialogue_json=dialogue,
        segment_durations=[2.0, 2.0],
    )

    with VideoFileClip(str(output_file)) as out:
        has_audio = out.audio is not None
        resolution = (out.w, out.h)
        fps = out.fps
    uniformity = _sample_uniformity(output_file)

    print("Validation output:", output_file)
    print("Exists:", output_file.exists(), "size_mb:", round(output_file.stat().st_size / (1024 * 1024), 3))
    print("Resolution:", resolution, "fps:", fps, "audio:", has_audio)
    print("Frame stddev mean (higher is safer):", round(uniformity, 3))
    assert resolution == (1920, 1080), "Output must be 1920x1080"
    assert has_audio, "Output must contain audio track"
    assert uniformity > 0.5, "Frames look uniform (possible solid color)"
    print("[PASS] Validation completed (no blue screens detected)")


if __name__ == "__main__":
    main()

