from pathlib import Path
import os

from src.utils import Settings
from src.visuals.video_composer import VideoComposer
from moviepy.editor import ColorClip


def main() -> None:
    settings = Settings.load()
    composer = VideoComposer(settings)
    output = Path("test_subs.mp4")
    srt = Path("test.srt")
    srt.write_text("1\n00:00:00,000 --> 00:00:05,000\nבדיקת כתוביות בעברית\n", encoding="utf-8")

    clip = ColorClip(size=(1280, 720), color=(0, 0, 255), duration=5)
    clip.fps = 24
    clip.write_videofile("temp_clean.mp4", logger=None)

    try:
        print("Attempting FFmpeg burn...")
        composer._burn_subtitles_ffmpeg(Path("temp_clean.mp4"), srt, output)
        if output.exists() and output.stat().st_size > 1000:
            print("SUCCESS: Video generated with subtitles.")
        else:
            print("FAILURE: Output file missing or empty.")
    except Exception as e:  # noqa: BLE001
        print(f"CRASH: {e}")
    finally:
        for path in [Path("temp_clean.mp4"), srt]:
            if path.exists():
                try:
                    os.remove(path)
                except OSError:
                    pass


if __name__ == "__main__":
    main()

