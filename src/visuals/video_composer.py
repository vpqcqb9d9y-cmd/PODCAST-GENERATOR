from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TypeVar
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont
# MoviePy 2.0 compatible imports
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from moviepy.video.tools.subtitles import SubtitlesClip
import arabic_reshaper
from bidi.algorithm import get_display
from ..utils import RunPaths, Settings, get_logger
from .subtitle_generator import generate_srt_from_dialogue


T = TypeVar("T")


@dataclass
class VideoComposer:
    """Combine audio, animations, and slides into final video."""

    settings: Settings
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
    MIN_IMAGE_DURATION = 4.0

    def __post_init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    def apply_ken_burns(self, clip: VideoClip, zoom_factor: float = 1.04) -> VideoClip:
        """
        Apply a gentle Ken Burns pan/zoom to a static clip.
        """
        duration = max(getattr(clip, "duration", 0.0) or 0.0, 0.001)

        def _scale(t: float) -> float:
            return 1.0 + (zoom_factor - 1.0) * (t / duration)

        zoomed = clip.fx(vfx.resize, _scale)
        return zoomed.fx(
            vfx.crop,
            width=clip.w,
            height=clip.h,
            x_center=clip.w / 2,
            y_center=clip.h / 2,
        )

    def _load_cv2(self):
        try:
            import cv2  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency issue
            self.logger.error("OpenCV (cv2) is required for visual validation: %s", exc)
            return None
        return cv2

    def _create_placeholder_slides(
        self,
        count: int,
        output_dir: Path,
        metadata: Dict[str, Any],
        start_index: int = 1,
    ) -> List[Path]:
        """
        Generate simple Hebrew placeholder slides when real images are missing.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        font_title, font_body = self._load_fonts()
        topic = metadata.get("topic") or metadata.get("summary") or "תוכן חזותי"
        concepts = metadata.get("key_concepts") or []

        palettes = [
            ((15, 23, 42), (79, 70, 229), (244, 114, 182)),
            ((32, 19, 53), (190, 24, 93), (248, 250, 252)),
            ((20, 83, 45), (74, 222, 128), (248, 250, 252)),
            ((67, 56, 202), (147, 51, 234), (253, 224, 71)),
        ]

        placeholders: List[Path] = []
        width, height = 1920, 1080

        for idx in range(count):
            palette = palettes[(start_index + idx - 1) % len(palettes)]
            bg_start, bg_end, accent = palette
            image = Image.new("RGB", (width, height), color=bg_start)
            draw = ImageDraw.Draw(image)

            for y in range(height):
                ratio = y / max(height - 1, 1)
                r = int(bg_start[0] * (1 - ratio) + bg_end[0] * ratio)
                g = int(bg_start[1] * (1 - ratio) + bg_end[1] * ratio)
                b = int(bg_start[2] * (1 - ratio) + bg_end[2] * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            draw.rectangle([(0, 0), (width, 12)], fill=accent)
            draw.rectangle([(0, height - 12), (width, height)], fill=accent)

            concept_text = ""
            if concepts:
                concept_text = concepts[(start_index + idx - 1) % len(concepts)]

            headline = "תמונת פלייסהולדר"
            subline = f"{topic}" if topic else "תוכן חזותי"
            caption = concept_text or "ויזואל זמני עד ליצירת תמונה מותאמת"

            draw.text((120, 200), headline, font=font_title, fill=(255, 255, 255))
            draw.text((120, 320), subline, font=font_body, fill=(240, 240, 240))
            draw.text((120, 420), caption, font=font_body, fill=(220, 220, 220))

            badge_text = "AI · Hebrew · Placeholder"
            draw.rectangle([(120, 500), (700, 560)], fill=(0, 0, 0, 120), outline=None)
            draw.text((140, 515), badge_text, font=font_body, fill=(255, 255, 255))

            filename = f"placeholder_{start_index + idx:02d}.png"
            path = output_dir / filename
            image.save(path, quality=95)
            placeholders.append(path)
            self.logger.info("Generated placeholder slide: %s", path.name)

        return placeholders

    def validate_image(self, image_path: Path) -> bool:
        """
        Validate that an image exists, is readable, and meets basic quality requirements.
        """
        cv2 = self._load_cv2()
        if cv2 is None:
            return False

        try:
            if not image_path.exists():
                self.logger.warning("Image missing: %s", image_path)
                return False

            file_size_kb = image_path.stat().st_size / 1024
            if file_size_kb < 100:
                self.logger.warning("Image too small (%.1fKB): %s", file_size_kb, image_path.name)
                return False

            img = cv2.imread(str(image_path))
            if img is None:
                self.logger.warning("Failed to read image: %s", image_path.name)
                return False

            height, width = img.shape[:2]
            if width < 800 or height < 600:
                self.logger.warning(
                    "Image resolution too low (%dx%d): %s", width, height, image_path.name
                )
                return False

            return True
        except Exception as exc:
            self.logger.error("Image validation error for %s: %s", image_path.name, exc)
            return False

    def get_valid_images(
        self,
        image_dir: Path,
        required_count: int,
        candidates: Optional[Iterable[Path]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        allow_placeholders: bool = True,
    ) -> List[Path]:
        """
        Validate images from directory and return high-quality assets.

        Args:
            image_dir: Directory containing generated visuals.
            required_count: Desired number of image assets.
            candidates: Optional iterable of pre-discovered image paths.
        """
        if required_count <= 0:
            required_count = 1

        if candidates is None:
            candidate_paths: List[Path] = []
            for ext in self.IMAGE_EXTENSIONS:
                candidate_paths.extend(image_dir.glob(f"*{ext}"))
        else:
            candidate_paths = list(candidates)

        unique_candidates = sorted(set(candidate_paths))
        valid_images: List[Path] = []

        for img_path in unique_candidates:
            if self.validate_image(img_path):
                valid_images.append(img_path)
            else:
                self.logger.debug("Discarded invalid image: %s", img_path.name)

        if not valid_images:
            self.logger.warning("No valid images found in %s", image_dir)

        if len(valid_images) >= required_count:
            return valid_images[:required_count]

        placeholders_needed = required_count - len(valid_images)
        if placeholders_needed > 0 and allow_placeholders:
            self.logger.warning(
                "Only %d valid image(s) available, generating %d placeholder slide(s).",
                len(valid_images),
                placeholders_needed,
            )
            placeholders = self._create_placeholder_slides(
                count=placeholders_needed,
                output_dir=image_dir,
                metadata=metadata or {},
                start_index=len(valid_images) + 1,
            )
            valid_images.extend(placeholders)
        elif placeholders_needed > 0 and not allow_placeholders:
            self.logger.warning(
                "Only %d valid image(s) available; placeholders disabled (adaptive timeline).",
                len(valid_images),
            )

        return valid_images[:required_count]

    def _prioritize_real_images(self, image_paths: List[Path]) -> List[Path]:
        """
        Group visuals by slide index and prefer real assets over placeholders.

        If a real image exists for an index, placeholders for that index are ignored
        (not deleted). Otherwise, placeholders are used as a fallback.
        """
        real_pattern = re.compile(r"image_(\d+)", re.IGNORECASE)
        placeholder_pattern = re.compile(r"placeholder_(\d+)", re.IGNORECASE)

        real_by_index: Dict[int, List[Path]] = {}
        placeholders_by_index: Dict[int, List[Path]] = {}
        unmatched: List[Path] = []

        for path in image_paths:
            name = path.name
            real_match = real_pattern.search(name)
            placeholder_match = placeholder_pattern.search(name)

            if real_match:
                idx = int(real_match.group(1))
                real_by_index.setdefault(idx, []).append(path)
            elif placeholder_match:
                idx = int(placeholder_match.group(1))
                placeholders_by_index.setdefault(idx, []).append(path)
            else:
                unmatched.append(path)

        prioritized: List[Path] = []
        all_indices = sorted(set(real_by_index.keys()) | set(placeholders_by_index.keys()))
        for idx in all_indices:
            real_assets = sorted(real_by_index.get(idx, []))
            placeholder_assets = sorted(placeholders_by_index.get(idx, []))

            if real_assets:
                if placeholder_assets:
                    self.logger.info(
                        "[VideoComposer] Index %d: Using Real Image (ignoring placeholder).",
                        idx,
                    )
                prioritized.extend(real_assets)
            elif placeholder_assets:
                prioritized.extend(placeholder_assets)

        prioritized.extend(sorted(unmatched))
        return prioritized


    @staticmethod
    def _apply_duration(clip: VideoClip, duration: float) -> VideoClip:
        if hasattr(clip, "with_duration"):
            return clip.with_duration(duration)
        return clip.set_duration(duration)

    @staticmethod
    def _apply_start(clip: VideoClip, start: float) -> VideoClip:
        if hasattr(clip, "with_start"):
            return clip.with_start(start)
        return clip.set_start(start)

    def create_timeline(
        self,
        dialogue_json: Dict,
        metadata: Dict,
        audio_file: Path,
        animations_dir: Path,
        run_paths: Optional[RunPaths] = None,
        asset_paths: Optional[List[Path]] = None,
        adaptive_timeline: bool = False,
        apply_ken_burns: bool = True,
    ) -> List[VideoClip]:
        """
        Build video timeline aligned with the final audio.
        """
        audio_clip = AudioFileClip(str(audio_file))
        total_duration = audio_clip.duration
        audio_clip.close()
        turn_count = max(len(dialogue_json.get("dialogue", [])), 1)

        # More robust file detection
        video_files: List[Path] = []
        image_files: List[Path] = []
        raw_image_files: List[Path] = []
        prioritized_images: List[Path] = []

        allow_placeholders = not adaptive_timeline

        if asset_paths is not None:
            existing = [p for p in asset_paths if p and p.exists()]
            video_files = [p for p in existing if p.suffix.lower() in self.VIDEO_EXTENSIONS]
            prioritized_images = [p for p in existing if p.suffix.lower() in self.IMAGE_EXTENSIONS]
            raw_image_files = list(prioritized_images)
        else:
            for ext in self.VIDEO_EXTENSIONS:
                video_files.extend(list(animations_dir.glob(f"*{ext}")))
            for ext in self.IMAGE_EXTENSIONS:
                image_files.extend(list(animations_dir.glob(f"*{ext}")))

            video_files = sorted(list(set(video_files)))  # Remove duplicates
            raw_image_files = sorted(list(set(image_files)))  # Remove duplicates

            # Group by index and prefer real images over placeholders without deleting files
            prioritized_images = self._prioritize_real_images(raw_image_files)
            real_count = sum(1 for p in prioritized_images if "placeholder" not in p.name.lower())
            placeholder_count = sum(1 for p in prioritized_images if "placeholder" in p.name.lower())
            self.logger.info(
                "Prioritized images: %d real, %d placeholder (post-filter).",
                real_count,
                placeholder_count,
            )

        # Validate images before composing to avoid corrupted assets.
        if asset_paths is not None:
            raw_image_count = getattr(self.settings, "image_count", 1)
            try:
                parsed_count = int(raw_image_count)
            except Exception:
                parsed_count = 1
            required_image_count = len(prioritized_images) or max(1, parsed_count)
        else:
            raw_image_count = getattr(self.settings, "image_count", len(prioritized_images) or 5)
            try:
                parsed_count = int(raw_image_count)
            except Exception:
                parsed_count = len(prioritized_images) or 5
            required_image_count = max(len(prioritized_images), parsed_count)

        image_files = self.get_valid_images(
            animations_dir,
            required_count=required_image_count,
            candidates=prioritized_images,
            metadata=metadata,
            allow_placeholders=allow_placeholders,
        )

        # Surface missing visuals explicitly when images were requested
        if required_image_count > 0 and len(image_files) == 0:
            warn_msg = (
                f"No generated images available (requested {required_image_count}). "
                "Falling back to slide-style visuals."
            )
            self.logger.warning(warn_msg)
            if run_paths:
                run_paths.log(f"⚠ {warn_msg}")

        if adaptive_timeline and run_paths:
            run_paths.log("Adaptive timeline: stretching available visuals (no placeholders).")

        visual_summary = (
            "Visual assets detected: "
            f"{len(video_files)} video(s), {len(image_files)} image(s) for {turn_count} turns."
        )
        self.logger.info(visual_summary)
        if run_paths:
            run_paths.log(visual_summary)

        # Log detailed file information for debugging
        if video_files:
            self.logger.info("Video files found: %s", [p.name for p in video_files])
        if image_files:
            self.logger.info("Image files found: %s", [p.name for p in image_files])
        if raw_image_files and len(image_files) < len(raw_image_files):
            removed = set(p.name for p in raw_image_files) - set(p.name for p in image_files)
            self.logger.warning("Discarded %d invalid image(s): %s", len(removed), list(removed))

        if not video_files and not image_files:
            fallback_msg = "No rendered visuals found; generating slide-style video."
            self.logger.warning(fallback_msg)
            if run_paths:
                run_paths.log(fallback_msg)
            return self._build_slide_clips(dialogue_json, metadata, total_duration)

        asset_files = sorted(video_files + image_files)
        assets: List[Tuple[str, Path]] = []
        for path in asset_files:
            suffix = path.suffix.lower()
            if suffix in self.VIDEO_EXTENSIONS:
                assets.append(("video", path))
            elif suffix in self.IMAGE_EXTENSIONS:
                assets.append(("image", path))

        total_assets = len(assets)
        base_slot = total_duration / total_assets if total_assets else total_duration
        clips: List[VideoClip] = []
        current_start = 0.0
        remaining = total_duration

        for asset_type, media in assets:
            if remaining <= 0:
                break

            try:
                if asset_type == "video":
                    clip = VideoFileClip(str(media))
                    duration = min(clip.duration, remaining)
                    if duration <= 0:
                        clip.close()
                        continue
                    clip = clip.subclipped(0, duration)
                    clip = self._apply_start(clip, current_start)
                    self.logger.info("Added video clip %s (%.2fs)", media.name, duration)
                else:
                    duration = min(max(base_slot, self.MIN_IMAGE_DURATION), remaining)
                    # Ensure image is properly loaded and resized for video
                    try:
                        from PIL import Image
                        img = Image.open(str(media))
                        # Resize to fit video dimensions while maintaining aspect ratio
                        img_width, img_height = img.size
                        video_width, video_height = 1920, 1080
                        ratio = min(video_width / img_width, video_height / img_height)
                        new_width = int(img_width * ratio)
                        new_height = int(img_height * ratio)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        # Create new image with black background
                        bg = Image.new('RGB', (video_width, video_height), (0, 0, 0))
                        x = (video_width - new_width) // 2
                        y = (video_height - new_height) // 2
                        bg.paste(img, (x, y))
                        # Save temporary resized image
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            bg.save(tmp.name)
                            temp_path = tmp.name
                        clip = ImageClip(temp_path)
                        clip = self._apply_duration(clip, duration)
                        if apply_ken_burns:
                            clip = self.apply_ken_burns(clip)
                        clip = self._apply_start(clip, current_start)
                        self.logger.info("Added image clip %s (%.2fs) - resized to %dx%d", media.name, duration, new_width, new_height)
                    except Exception as img_err:
                        self.logger.warning("Failed to process image %s: %s, using fallback", media.name, img_err)
                        # Fallback: create a colored clip
                        clip = ColorClip(size=(1920, 1080), color=(64, 64, 64), duration=duration)
                        clip = self._apply_start(clip, current_start)
                clips.append(clip)
                current_start += duration
                remaining -= duration
            except Exception as e:
                self.logger.error("Failed to process asset %s: %s", media.name, e)
                continue

        if remaining > 0 and clips:
            last_clip = clips[-1]
            extended_duration = max(getattr(last_clip, "duration", 0) + remaining, 0)
            clips[-1] = self._apply_duration(last_clip, extended_duration)
            remaining = 0
        elif remaining > 0:
            tail = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=remaining)
            tail = self._apply_start(tail, current_start)
            clips.append(tail)

        return clips

    def render_final_video(
        self,
        clips: Sequence[VideoClip],
        audio_file: Path,
        output_file: Path,
        dialogue_json: Optional[Dict] = None,
    ) -> Path:
        """
        Composite all clips, set audio track, export MP4 (1080p, 30fps, H.264).
        
        Critical: Ensures video duration matches audio duration to prevent
        silent video output.
        """
        clip_list = list(clips)
        
        # Load audio first to get the authoritative duration
        audio = AudioFileClip(str(audio_file))
        audio_duration = audio.duration
        self.logger.info("Audio duration: %.2f seconds", audio_duration)
        
        # Concatenate video clips
        base = concatenate_videoclips(clip_list, method="compose")
        video_duration = base.duration
        self.logger.info("Video duration before sync: %.2f seconds", video_duration)
        
        # CRITICAL FIX: Ensure video duration matches audio duration exactly
        # Use with_duration to satisfy tests and keep alignment simple.
        branch = "none"
        if abs(video_duration - audio_duration) > 0.05:
            branch = "with_duration"
            base = self._apply_duration(base, audio_duration)

        video_duration = base.duration
        # Always (re)generate SRT captions alongside the video
        captions_path = output_file.parent / "captions.srt"
        if dialogue_json:
            try:
                self._write_srt(dialogue_json, audio_duration, captions_path)
            except Exception as exc:
                self.logger.error("Failed to write captions.srt: %s", exc)

        # Burn subtitles (RTL-safe shaping for Hebrew)
        final_video = base
        if captions_path.exists():
            def _text_factory(txt: str) -> TextClip:
                shaped = arabic_reshaper.reshape(txt)
                bidi_text = get_display(shaped)
                return TextClip(
                    bidi_text,
                    fontsize=55,
                    font="Arial",
                    color="white",
                    stroke_color="black",
                    stroke_width=2,
                    method="caption",
                    size=(int(base.w * 0.9), None),
                    align="center",
                )

            try:
                subs = SubtitlesClip(str(captions_path), _text_factory).set_position(
                    ("center", "bottom")
                )
                subs = subs.set_duration(audio_duration)
                final_video = CompositeVideoClip([base, subs])
            except Exception as exc:
                self.logger.error("Failed to overlay subtitles: %s", exc)
                final_video = base

        # Create composite audio and attach to video
        audio_mix = CompositeAudioClip([audio])
        
        # Attach audio track (MoviePy 2.x compatible)
        attach_fn = getattr(final_video, "with_audio", None) or getattr(final_video, "set_audio", None)
        attached_clip = attach_fn(audio_mix) if attach_fn else final_video.set_audio(audio_mix)
        if getattr(attached_clip, "audio", None) is None:
            self.logger.error("CRITICAL: Audio failed to attach to video!")
            raise RuntimeError("Failed to attach audio to video. Audio track is None.")
        final = attached_clip.set_duration(audio_duration)
        
        # Verify audio is attached
        if final.audio is None:
            self.logger.error("CRITICAL: Audio failed to attach to video!")
            raise RuntimeError("Failed to attach audio to video. Audio track is None.")
        self.logger.info(
            "Final video ready: duration=%.2fs, has_audio=%s",
            final.duration,
            final.audio is not None
        )
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Use system temp directory to avoid issues with Hebrew/Unicode characters in path
        # FFMPEG on Windows has issues with non-ASCII paths
        temp_dir = tempfile.gettempdir()
        temp_audio_path = Path(temp_dir) / f"mbs_temp_audio_{time.time_ns()}.m4a"
        
        try:
            # Verify temp audio path directory exists
            temp_audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(
                "Writing video with audio. Temp audio path: %s, Output: %s",
                temp_audio_path,
                output_file
            )
            
            # Write with explicit audio=True and all audio parameters
            # CRITICAL: audio=True is required to force audio track inclusion
            # Use high-quality audio settings for clear Hebrew speech
            final.write_videofile(
                str(output_file),
                codec="libx264",
                audio=True,  # CRITICAL: Explicitly enable audio
                audio_codec="aac",
                audio_fps=44100,  # Standard audio sample rate (matches stitcher output)
                audio_bitrate="256k",  # Higher bitrate for better clarity (especially Hebrew)
                audio_bufsize=3000,  # Larger buffer for stability
                audio_nbytes=4,  # 32-bit audio for better quality
                fps=30,
                threads=4,
                ffmpeg_params=["-pix_fmt", "yuv420p"],
                logger=None,  # Suppress console output to avoid encoding errors with Hebrew
                write_logfile=False,
                temp_audiofile=str(temp_audio_path),
            )
            
            # Verify output file has audio by checking file size
            if output_file.exists():
                file_size = output_file.stat().st_size
                # A video with audio should be significantly larger than video-only
                min_expected_size = int(audio_duration * 15000)  # ~15KB per second minimum
                if file_size < min_expected_size:
                    self.logger.warning(
                        "Output file may be missing audio. Size: %d bytes, expected at least: %d bytes",
                        file_size, min_expected_size
                    )
                else:
                    self.logger.info(
                        "Video file created successfully. Size: %d bytes (%.2f MB), expected audio duration: %.2fs",
                        file_size, file_size / (1024 * 1024), audio_duration
                    )
            else:
                self.logger.error("CRITICAL: Output file was not created: %s", output_file)
        finally:
            audio_mix.close()
            audio.close()
            final.close()
            base.close()
            for clip in clip_list:
                clip.close()
            # Clean up temp audio file
            if temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                except OSError:
                    pass  # Ignore cleanup errors
        
        self.logger.info("Video exported successfully: %s", output_file)
        return output_file

    def _write_srt(self, dialogue_json: Dict, total_duration: float, output_path: Path) -> None:
        """
        Generate a basic SRT file from dialogue turns.

        Timing heuristic: allocate 0.4s per word, clamped to [2s, 6s] per caption,
        preserving sequence. Ensures the last caption does not exceed total audio duration.
        """
        turns = [d for d in dialogue_json.get("dialogue", []) if isinstance(d, dict)]
        if not turns:
            return

        entries: List[str] = []
        cursor = 0.0
        for idx, turn in enumerate(turns, start=1):
            text = str(turn.get("text", "")).strip()
            if not text:
                continue
            words = len(text.split()) or 1
            duration = min(6.0, max(2.0, words * 0.4))
            start = cursor
            end = min(cursor + duration, total_duration)
            cursor = end
            entries.append(
                f"{idx}\n{self._format_ts(start)} --> {self._format_ts(end)}\n{text}\n"
            )
            if cursor >= total_duration:
                break

        output_path.write_text("\n".join(entries), encoding="utf-8")
        self.logger.info("captions.srt written with %d entries", len(entries))

    @staticmethod
    def _format_ts(seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def compose(
        self,
        dialogue_json: Dict,
        metadata: Dict,
        run_paths: RunPaths,
        asset_paths: Optional[List[Path]] = None,
        adaptive_timeline: bool = False,
        apply_ken_burns: bool = True,
    ) -> Path:
        # In production mode, block rendering if only placeholders are present
        if not getattr(self.settings, "preview_mode", False):
            visuals_dir = getattr(run_paths, "visuals_dir", None)
            if visuals_dir and visuals_dir.exists():
                placeholders = list(visuals_dir.glob("placeholder_*.png"))
                real_assets = [
                    p for p in visuals_dir.glob("*")
                    if p.suffix.lower() in self.IMAGE_EXTENSIONS and not p.name.startswith("placeholder_")
                ]
                if placeholders and not real_assets:
                    message = (
                        "Placeholder visuals detected with no real assets. "
                        "Aborting render (preview_mode is disabled)."
                    )
                    self.logger.error(message)
                    if hasattr(run_paths, "log"):
                        run_paths.log(message)
                    raise RuntimeError(message)
        # AGGRESSIVE CLEANUP: If image_01.png exists, DELETE placeholder_01.png
        run_dir = run_paths.run_dir
        for i in range(1, 20):
            real = list(run_dir.glob(f"image_{i:02d}_*.png")) + list(run_dir.glob(f"image_{i:02d}_*.jpg"))
            placeholder = run_dir / f"placeholder_{i:02d}.png"
            if real and placeholder.exists():
                print(f"🔥 DESTROYING {placeholder.name} because real image exists")
                os.remove(placeholder)

        start = time.perf_counter()
        try:
            clips = self.create_timeline(
                dialogue_json,
                metadata,
                run_paths.final_audio_path,
                run_paths.visuals_dir,
                run_paths,
                asset_paths=asset_paths,
                adaptive_timeline=adaptive_timeline,
                apply_ken_burns=apply_ken_burns,
            )
        except Exception as exc:
            self.logger.error(
                "[VideoComposer] Timeline creation failed; using slide fallback: %s",
                exc,
                exc_info=True,
            )
            if run_paths:
                run_paths.log(f"Timeline creation failed; using slide fallback: {exc}")

            try:
                audio_clip = AudioFileClip(str(run_paths.final_audio_path))
                total_duration = audio_clip.duration
                audio_clip.close()
            except Exception as audio_exc:
                self.logger.error(
                    "[VideoComposer] Failed to read audio duration for fallback: %s",
                    audio_exc,
                    exc_info=True,
                )
                total_duration = 0

            clips = self._build_slide_clips(dialogue_json, metadata, total_duration)
        output = self.render_final_video(
            clips,
            run_paths.final_audio_path,
            run_paths.final_video_path,
            dialogue_json=dialogue_json,
        )
        elapsed = time.perf_counter() - start
        self.logger.info("Video composition completed in %.2fs (clips=%s)", elapsed, len(clips))
        return output

    def _build_slide_clips(self, dialogue_json: Dict, metadata: Dict, total_duration: float) -> List[VideoClip]:
        topic = metadata.get("topic", "Azure בפשטות")
        date = metadata.get("date", "")
        key_topics = metadata.get("key_concepts", [])[:6]
        labs = metadata.get("labs", [])[:4]
        summary = metadata.get("summary", "")
        reading_list = metadata.get("reading_list", [])[:4]
        dialogue_turns = [turn for turn in dialogue_json.get("dialogue", []) if isinstance(turn, dict)]

        quotes: List[str] = []
        for turn in dialogue_turns:
            text = (turn.get("text") or "").strip()
            if not text:
                continue
            speaker = (turn.get("speaker") or "").strip()
            prefix = f"{speaker}: " if speaker else ""
            quotes.append(f"{prefix}{text}")
        quotes = quotes[:6]

        font_title, font_body = self._load_fonts()
        base_theme = self._select_theme(metadata)

        hero_bullets = [
            metadata.get("goal", "סשן מודרך וסיכום חי"),
            f"אורך אודיו: {max(total_duration / 60, 0.1):.1f} דק'",
            f"דוברים: {max(len(dialogue_turns), 1)} · מושגים: {len(key_topics) or '—'}",
        ]
        hero_chips = [
            date or "ללא תאריך",
            metadata.get("audience", "קהל יעד: מחנכים"),
            metadata.get("location", "Online • M.B.S Studio"),
        ]

        slide_specs: List[Dict[str, Any]] = [
            {
                "type": "standard",
                "title": topic,
                "subtitle": date or "סשן חדש",
                "bullets": hero_bullets,
                "chips": hero_chips,
                "hero": True,
                "theme_shift": 0,
            }
        ]

        if key_topics:
            slide_specs.append(
                {
                    "type": "standard",
                    "title": "מושגים מרכזיים",
                    "subtitle": "5 התובנות שחייבים לזכור",
                    "bullets": key_topics,
                    "theme_shift": 1,
                }
            )
        if labs:
            slide_specs.append(
                {
                    "type": "standard",
                    "title": "תרגולים / מעבדות",
                    "subtitle": "פעולות להמשך",
                    "bullets": labs,
                    "theme_shift": 2,
                }
            )
        if summary:
            summary_sentences = [
                sentence.strip()
                for sentence in summary.replace("\n", " ").split(".")
                if sentence.strip()
            ]
            slide_specs.append(
                {
                    "type": "standard",
                    "title": "תקציר מרכזי",
                    "subtitle": "במקום אחד",
                    "bullets": summary_sentences[:5] or [summary],
                    "theme_shift": 3,
                }
            )
        if reading_list:
            slide_specs.append(
                {
                    "type": "standard",
                    "title": "קריאה מומלצת",
                    "subtitle": "Deep dives להמשך",
                    "bullets": reading_list,
                    "theme_shift": 4,
                }
            )
        if quotes:
            for idx, chunk in enumerate(self._chunk_list(quotes, chunk_size=3)):
                slide_specs.append(
                    {
                        "type": "standard",
                        "title": "ציטוטים שנשארים",
                        "subtitle": "Highlights מהשיחה",
                        "bullets": chunk,
                        "theme_shift": 5 + idx,
                    }
                )

        speaker_blocks = self._build_speaker_blocks(dialogue_turns, per_card=2, max_cards=3)
        for idx, block in enumerate(speaker_blocks):
            slide_specs.append(
                {
                    "type": "speaker",
                    "title": "דוברים מובילים",
                    "blocks": block,
                    "theme_shift": 8 + idx,
                }
            )

        outro_lines = [
            "שאלו את ה-AI לשאלות המשך",
            "פתחו את המצגת שסוכמה אוטומטית",
            metadata.get("call_to_action", "המשיכו לייצר למידה אינטראקטיבית."),
        ]
        slide_specs.append(
            {
                "type": "standard",
                "title": "מה הלאה?",
                "subtitle": "Action Items",
                "bullets": outro_lines,
                "theme_shift": 20,
            }
        )

        if not slide_specs:
            slide_specs.append(
                {
                    "type": "standard",
                    "title": topic,
                    "bullets": ["Azure בפשטות"],
                    "theme_shift": 0,
                }
            )

        slides: List[Image.Image] = []
        total_specs = len(slide_specs)
        for idx, spec in enumerate(slide_specs):
            progress = idx / max(total_specs - 1, 1)
            theme_variant = self._theme_variant(base_theme, spec.get("theme_shift", idx))
            if spec["type"] == "speaker":
                slides.append(
                    self._render_speaker_slide(
                        title=spec.get("title", "דוברים מובילים"),
                        blocks=spec["blocks"],
                        font_title=font_title,
                        font_body=font_body,
                        theme=theme_variant,
                        progress=progress,
                    )
                )
            else:
                slides.append(
                    self._render_slide(
                        title=spec["title"],
                        bullets=spec["bullets"],
                        font_title=font_title,
                        font_body=font_body,
                        theme=theme_variant,
                        subtitle=spec.get("subtitle", ""),
                        chips=spec.get("chips"),
                        hero=spec.get("hero", False),
                        progress=progress,
                    )
                )

        if total_duration <= 0:
            total_duration = len(slides) * 4 or 12
        weights: List[float] = []
        for spec in slide_specs:
            if spec.get("hero"):
                weights.append(1.3)
            elif spec["type"] == "speaker":
                weights.append(0.9)
            elif spec.get("title") in {"מה הלאה?", "סיום ההרצאה"}:
                weights.append(1.1)
            else:
                weights.append(1.0)
        total_weight = sum(weights) or 1.0
        durations = [(total_duration * w / total_weight) for w in weights]
        durations = [max(1.0, d) for d in durations]

        clips: List[VideoClip] = []
        for image, duration in zip(slides, durations):
            array = np.array(image)
            clip = ImageClip(array)
            clip = self._apply_duration(clip, duration)
            fade_window = min(0.8, duration / 3)
            # MoviePy 2.0: use with_effects instead of fx()
            clip = clip.fx(vfx.fadein, fade_window).fx(vfx.fadeout, fade_window)
            clips.append(clip)
        return clips

    def _render_slide(
        self,
        title: str,
        bullets: List[str],
        font_title: ImageFont.ImageFont,
        font_body: ImageFont.ImageFont,
        theme: Dict[str, Tuple[int, int, int]],
        subtitle: str = "",
        chips: Optional[List[str]] = None,
        hero: bool = False,
        progress: float = 0.0,
    ) -> Image.Image:
        width, height = 1920, 1080
        background = self._gradient_canvas(theme["primary"], theme["secondary"]).convert("RGBA")

        overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.ellipse(
            (width - 500, -80, width + 240, 440),
            fill=(theme["accent"][0], theme["accent"][1], theme["accent"][2], 80),
        )
        overlay_draw.rectangle((0, height - 320, width, height), fill=(0, 0, 0, 60))
        background = Image.alpha_composite(background, overlay)

        card_bounds = (100, 120, width - 100, height - 120)
        panel = Image.new("RGBA", background.size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(card_bounds, radius=48, fill=theme.get("panel", (2, 6, 23, 200)))
        panel_draw.rounded_rectangle(
            (card_bounds[0], card_bounds[1] - 30, card_bounds[0] + 260, card_bounds[1] - 6),
            radius=12,
            fill=theme["accent"],
        )
        background = Image.alpha_composite(background, panel)
        draw = ImageDraw.Draw(background)

        title_y = card_bounds[1] + (20 if hero else 60)
        draw.text((card_bounds[0] + 60, title_y), title, font=font_title, fill=theme["text"])
        if subtitle:
            draw.text(
                (card_bounds[0] + 60, title_y + 80),
                subtitle,
                font=font_body,
                fill=theme["muted"],
            )

        y = (card_bounds[1] + 200) if hero else (card_bounds[1] + 240)
        bullet_width = card_bounds[2] - card_bounds[0] - 180
        line_height = getattr(font_body, "size", 32) + 8
        for bullet in bullets:
            if not bullet:
                continue
            wrapped = self._wrap_text(bullet, font_body, bullet_width)
            for line in wrapped:
                draw.text((card_bounds[0] + 110, y), line, font=font_body, fill=theme["text"])
                y += line_height
            y += 12
            if y > card_bounds[3] - 200:
                break

        chip_y = card_bounds[3] - 190
        chip_x = card_bounds[0] + 110
        for chip in chips or []:
            if not chip:
                continue
            text = chip if len(chip) <= 48 else f"{chip[:45]}..."
            text_width = self._measure_text(text, font_body) + 60
            chip_rect = (chip_x, chip_y, chip_x + text_width, chip_y + 54)
            draw.rounded_rectangle(chip_rect, radius=22, fill=theme["chip_bg"])
            draw.text((chip_x + 30, chip_y + 14), text, font=font_body, fill=theme["text"])
            chip_x += text_width + 18
            if chip_x > card_bounds[2] - 160:
                chip_x = card_bounds[0] + 110
                chip_y -= 70

        progress_label = f"{int(progress * 100):02d}% הושלם"
        draw.text(
            (card_bounds[2] - 260, card_bounds[3] - 90),
            progress_label,
            font=font_body,
            fill=theme["muted"],
        )
        self._draw_progress_bar(draw, card_bounds, theme, progress)

        return background.convert("RGB")

    def _render_speaker_slide(
        self,
        title: str,
        blocks: List[Dict[str, str]],
        font_title: ImageFont.ImageFont,
        font_body: ImageFont.ImageFont,
        theme: Dict[str, Tuple[int, int, int]],
        progress: float = 0.0,
    ) -> Image.Image:
        width, height = 1920, 1080
        background = self._gradient_canvas(theme["secondary"], theme["primary"]).convert("RGBA")
        overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, 0, width, height), fill=(0, 0, 0, 50))
        background = Image.alpha_composite(background, overlay)

        card_bounds = (100, 120, width - 100, height - 120)
        panel = Image.new("RGBA", background.size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(card_bounds, radius=48, fill=theme.get("panel", (2, 6, 23, 210)))
        background = Image.alpha_composite(background, panel)
        draw = ImageDraw.Draw(background)

        draw.text((card_bounds[0] + 60, card_bounds[1] + 40), title, font=font_title, fill=theme["text"])
        column_count = max(len(blocks), 1)
        available_width = card_bounds[2] - card_bounds[0] - 120
        column_width = (available_width - (column_count - 1) * 30) / column_count
        column_width = max(300, column_width)
        card_top = card_bounds[1] + 140
        card_bottom = card_bounds[3] - 140
        for idx, block in enumerate(blocks):
            x0 = card_bounds[0] + 60 + idx * (column_width + 30)
            x1 = x0 + column_width
            sub_panel = Image.new("RGBA", background.size, (0, 0, 0, 0))
            sub_draw = ImageDraw.Draw(sub_panel)
            sub_draw.rounded_rectangle(
                (x0, card_top, x1, card_bottom),
                radius=32,
                fill=(theme["chip_bg"][0], theme["chip_bg"][1], theme["chip_bg"][2], 220),
            )
            background = Image.alpha_composite(background, sub_panel)
            draw = ImageDraw.Draw(background)

            speaker = block.get("speaker") or "Speaker"
            snippet = (block.get("text") or "").strip()
            draw.text((x0 + 40, card_top + 30), speaker, font=font_body, fill=theme["text"])
            snippet_lines = self._wrap_text(snippet, font_body, int(column_width) - 80)
            text_y = card_top + 90
            for line in snippet_lines[:8]:
                draw.text((x0 + 40, text_y), line, font=font_body, fill=theme["muted"])
                text_y += getattr(font_body, "size", 32) + 6

        self._draw_progress_bar(draw, card_bounds, theme, progress)
        return background.convert("RGB")

    def _draw_progress_bar(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Tuple[int, int, int, int],
        theme: Dict[str, Tuple[int, int, int]],
        progress: float,
    ) -> None:
        bar_margin = 120
        bar_rect = (
            bounds[0] + bar_margin,
            bounds[3] - 50,
            bounds[2] - bar_margin,
            bounds[3] - 20,
        )
        muted = theme.get("muted", (148, 163, 184))
        draw.rounded_rectangle(bar_rect, radius=12, fill=(muted[0], muted[1], muted[2], 80))
        clamped = max(0.0, min(progress, 1.0))
        fill_width = int((bar_rect[2] - bar_rect[0]) * clamped)
        if fill_width <= 0:
            return
        fill_rect = (bar_rect[0], bar_rect[1], bar_rect[0] + fill_width, bar_rect[3])
        draw.rounded_rectangle(fill_rect, radius=12, fill=theme["accent"])

    def _build_speaker_blocks(
        self,
        dialogue_turns: List[Dict[str, Any]],
        per_card: int = 2,
        max_cards: int = 3,
    ) -> List[List[Dict[str, str]]]:
        entries: List[Dict[str, str]] = []
        for turn in dialogue_turns:
            text = (turn.get("text") or "").strip()
            if not text:
                continue
            speaker = (turn.get("speaker") or "דובר/ת").strip() or "דובר/ת"
            entries.append({"speaker": speaker, "text": text})
            if len(entries) >= per_card * max_cards:
                break
        return self._chunk_list(entries, per_card)

    def _select_theme(self, metadata: Dict) -> Dict[str, Tuple[int, int, int]]:
        palettes = [
            {
                "primary": (5, 8, 38),
                "secondary": (30, 64, 175),
                "accent": (56, 189, 248),
                "text": (248, 250, 252),
                "muted": (148, 163, 184),
                "panel": (2, 6, 23, 210),
                "chip_bg": (23, 37, 84, 180),
            },
            {
                "primary": (13, 24, 33),
                "secondary": (18, 83, 60),
                "accent": (74, 222, 128),
                "text": (241, 245, 249),
                "muted": (148, 163, 184),
                "panel": (8, 20, 28, 210),
                "chip_bg": (16, 44, 32, 200),
            },
            {
                "primary": (49, 12, 78),
                "secondary": (109, 40, 217),
                "accent": (249, 115, 22),
                "text": (255, 245, 235),
                "muted": (242, 211, 238),
                "panel": (34, 4, 49, 200),
                "chip_bg": (71, 22, 107, 200),
            },
        ]
        topic = metadata.get("topic", "")
        idx = sum(ord(char) for char in topic) % len(palettes)
        return palettes[idx].copy()

    def _theme_variant(self, base: Dict[str, Tuple[int, int, int]], shift: int) -> Dict[str, Tuple[int, int, int]]:
        variant = base.copy()

        def shift_color(color: Tuple[int, int, int], delta: int) -> Tuple[int, int, int]:
            return tuple(min(255, max(0, channel + delta)) for channel in color)

        delta = int((shift % 3 - 1) * 18)
        variant["primary"] = shift_color(base["primary"], delta)
        variant["secondary"] = shift_color(base["secondary"], -delta)
        accent_delta = 12 if shift % 2 else -12
        variant["accent"] = shift_color(base["accent"], accent_delta)
        chip_rgba = base.get("chip_bg", (12, 74, 110, 180))
        chip_delta = int((shift % 4) * 10)
        variant["chip_bg"] = (
            min(255, max(0, chip_rgba[0] + chip_delta)),
            min(255, max(0, chip_rgba[1] + chip_delta)),
            min(255, max(0, chip_rgba[2] + chip_delta)),
            chip_rgba[3],
        )
        return variant

    def _gradient_canvas(self, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
        width, height = 1920, 1080
        gradient = Image.new("RGB", (width, height), color=top)
        draw = ImageDraw.Draw(gradient)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            draw.line([(0, y), (width, y)], fill=color)
        return gradient

    def _wrap_text(self, text: Any, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        if not isinstance(text, str):
            if isinstance(text, dict):
                # If text is a dictionary (like a lab object), try to extract a string representation
                text = text.get("name") or text.get("title") or text.get("description") or str(text)
            else:
                text = str(text)
        
        words = text.split()
        lines: List[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            w = self._measure_text(test, font)
            if w <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _measure_text(self, text: str, font: ImageFont.ImageFont) -> int:
        if hasattr(font, "getbbox"):
            box = font.getbbox(text)
            return box[2] - box[0]
        if hasattr(font, "getlength"):
            return int(font.getlength(text))
        return max(len(text), 1) * max(font.size, 10) // 2

    def _load_fonts(self) -> Tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
        # Try Hebrew-supporting fonts in order of preference
        font_options = [
            ("arial.ttf", 60, 36),  # Arial (good Hebrew support)
            ("tahoma.ttf", 60, 36),  # Tahoma (good Hebrew support)
            ("david.ttf", 60, 36),   # David (Hebrew font)
            ("times.ttf", 60, 36),   # Times New Roman
            ("cour.ttf", 60, 36),    # Courier New
        ]

        for font_name, title_size, body_size in font_options:
            try:
                title_font = ImageFont.truetype(font_name, title_size)
                body_font = ImageFont.truetype(font_name, body_size)
                self.logger.debug("Loaded Hebrew-compatible font: %s", font_name)
                return title_font, body_font
            except OSError:
                continue

        # Fallback to default font
        self.logger.warning("No Hebrew-compatible fonts found, using default font")
        fallback = ImageFont.load_default()
        return fallback, fallback

    def _chunk_list(self, values: Sequence[T], chunk_size: int) -> List[List[T]]:
        if chunk_size <= 0:
            return [list(values)]
        chunked: List[List[T]] = []
        current: List[T] = []
        for value in values:
            current.append(value)
            if len(current) == chunk_size:
                chunked.append(current)
                current = []
        if current:
            chunked.append(current)
        return chunked

