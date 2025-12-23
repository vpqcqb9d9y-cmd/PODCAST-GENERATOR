from __future__ import annotations

import json
import re
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, List

from openai import APIError, APITimeoutError, AzureOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..utils import RunPaths, Settings, get_logger


HEBREW_FONT = "Arial"  # Default Hebrew-compatible font for generated scenes
AZURE = "#1E6DE0"
CONCRETE_WHITE = "#F4F5F7"
SOFT_TEAL = "#4DC1B6"

@dataclass
class ManimSceneGenerator:
    """Generate Manim animation code for technical concepts."""

    settings: Settings

    def __post_init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self.client = AzureOpenAI(
            api_key=self.settings.openai_api_key,
            api_version=self.settings.openai_api_version,
            azure_endpoint=self.settings.openai_endpoint,
        )

    def identify_visual_needs(self, dialogue_json: Dict) -> List[Dict[str, str]]:
        """
        Use LLM to propose 1-2 abstract concepts for simple geometric Manim animation.
        Works for any topic (technical or not).
        """
        dialogues = dialogue_json.get("dialogue", [])
        full_text = "\n".join(item.get("text", "") for item in dialogues)
        if not full_text.strip():
            return []

        prompt = (
            "Given the following dialogue transcript (may be Hebrew), identify 1-2 abstract"
            " concepts that can be illustrated with very simple geometric shapes in Manim."
            " Avoid complex assets, photos, or detailed text rendering. Return ONLY JSON:"
            " a list of objects, each with a 'description' field in Hebrew describing a"
            " simple geometric animation idea (circles, lines, arrows, grids, transforms)."
            " No prose or code fences."
            f"\n\nTranscript:\n{full_text}"
        )

        try:
            response = self._chat_completion(prompt, max_tokens=400)
            raw_text = response.choices[0].message.content or ""
            scenes = self._parse_scene_suggestions(raw_text)
            if scenes:
                return scenes
            self.logger.warning("LLM returned no parsable scenes; using generic fallback.")
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning("LLM scene discovery failed: %s", exc)

        # Safe fallback: single generic abstract scene
        return [
            {
                "description": "אנימציה גיאומטרית כללית: מעגלים וריבועים שמסבירים קשרים ומעברים בין רעיונות.",
            }
        ]

    def generate_manim_code(self, scene_description: str, class_name: str) -> str:
        """
        Use Azure OpenAI to generate Manim Python code.
        """
        prompt = f"""
You are a Manim expert. Write a Python script using Manim Community v0.18.
- Create a class named {class_name} that inherits from Scene.
- Visualize the following concept in Hebrew annotations: {scene_description}
- Style: high-end 3D-feel using flat primitives (no photos), color palette AZURE/CONCRETE_WHITE/SOFT_TEAL, clean edges.
- Motion: every element enters ONLY with Create/Write/FadeInFrom (no bare add anywhere); include a subtle background float/pulse (e.g., Rectangle or VGroup oscillating 3-5px up/down over 6s) with rate_func=smootherstep so something always moves softly during dialogue.
- Add a slow camera-like dolly; if camera frame access differs by Manim version, fall back to shifting mobjects or background layers—avoid `self.camera.frame` when unavailable.
- Include a module-level constant HEBREW_FONT = "{HEBREW_FONT}" and use it for all Text/Paragraph fonts; also constants AZURE, CONCRETE_WHITE, SOFT_TEAL.
- Add an rtl(text: str) helper that uses arabic_reshaper + bidi.get_display to render Hebrew RTL safely; every displayed string must pass through rtl(...). Align text RIGHT. Use Assistant or Alef font variants when available.
- All Text/Paragraph instances must set font=HEBREW_FONT, color=AZURE or SOFT_TEAL for accents, and wrap the string with rtl(...).
- Scene safety: begin construct() with self.wait(1.5) and end with self.wait(1.5) to avoid blank frames; include at least one additional self.wait() during the sequence.
- Ensure backgrounds are lightly tinted (CONCRETE_WHITE) so there are no black/blank frames; never leave the canvas empty.
- Use frame dimensions via config.frame_width and config.frame_height (or define these values explicitly in the script) instead of relying on global FRAME_WIDTH/FRAME_HEIGHT constants.
- Append a comment line "# END OF SCENE" at the very end of the file to confirm code completion.
- Return only valid Python code (no markdown fences).
""".strip()
        response = self._chat_completion(prompt, max_tokens=1500)
        code = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        code = self._strip_code_fences(code)
        if "HEBREW_FONT" not in code:
            code = f'HEBREW_FONT = "{HEBREW_FONT}"\n' + code
        return code

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences (```python ... ```) from text."""
        lines = text.strip().splitlines()
        if not lines:
            return text
        # Check if wrapped in code fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    def render_scenes(self, scenes_directory: Path) -> List[Path]:
        """
        Execute Manim for each scene file.
        Uses `manim` CLI if on PATH, otherwise falls back to `python -m manim`
        (still requires manim to be importable in the current environment).
        """
        outputs: List[Path] = []
        manim_exec = shutil.which("manim")
        if manim_exec:
            base_cmd = [manim_exec]
        else:
            # Fallback: try module invocation
            try:
                import manim  # noqa: F401
                base_cmd = [sys.executable, "-m", "manim"]
                self.logger.info("Manim not on PATH; using module fallback via python -m manim")
            except Exception:
                self.logger.warning("Manim CLI not found and module import failed; skipping animation rendering.")
                raise RuntimeError("Manim CLI not available in PATH")

        for scene_file in scenes_directory.glob("*.py"):
            try:
                class_name = self._extract_scene_class(scene_file)
            except ValueError as exc:
                self.logger.warning("Skipping %s: %s", scene_file.name, exc)
                continue
            output_name = scene_file.with_suffix(".mp4").name
            scene_path = scene_file.resolve()
            media_dir = scenes_directory / "media"
            cmd = base_cmd + [
                "-qm",
                "--media_dir",
                str(media_dir),
                "-o",
                output_name,
                str(scene_path),
                class_name,
            ]
            self.logger.info("Rendering %s", scene_file.name)
            try:
                subprocess.run(cmd, check=True)
            except FileNotFoundError:
                self.logger.warning("Manim executable not found during render.")
                raise RuntimeError("Manim executable not found during render")
            except subprocess.CalledProcessError as exc:
                self.logger.error("Manim failed for %s: %s", scene_file.name, exc)
                continue

            # Manim writes into media/videos/<scene>/<quality>/<file>.mp4; move it next to scenes
            scene_output = scenes_directory / output_name
            if not scene_output.exists():
                media_root = scenes_directory / "media" / "videos"
                candidates = list(media_root.rglob(output_name)) if media_root.exists() else []
                if candidates:
                    source = max(candidates, key=lambda p: p.stat().st_mtime)
                    try:
                        scene_output.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source), scene_output)
                        self.logger.info("Moved Manim output from %s to %s", source, scene_output)
                    except Exception as move_exc:
                        self.logger.error("Failed to move Manim output %s -> %s: %s", source, scene_output, move_exc)
                        continue
                else:
                    self.logger.warning(
                        "Manim output not found for %s (looked in %s)", output_name, media_root
                    )
                    continue
            try:
                self.validate_scene_output(scene_output)
                outputs.append(scene_output)
            except Exception as exc:
                self.logger.error("Scene validation failed for %s: %s", scene_file.name, exc)
                if scene_output.exists():
                    try:
                        scene_output.unlink()
                    except OSError:
                        pass
        return outputs

    def _load_cv2(self):
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            self.logger.error("OpenCV (cv2) is required for scene validation: %s", exc)
            return None
        return cv2

    def validate_scene_output(self, scene_path: Path) -> bool:
        """
        Ensure Manim generated a valid video file for the scene.
        """
        if not scene_path.exists():
            raise FileNotFoundError(f"Manim failed to generate: {scene_path}")

        file_size = scene_path.stat().st_size
        if file_size < 10_000:
            raise ValueError(f"Manim output too small: {file_size} bytes")

        cv2 = self._load_cv2()
        if cv2 is None:
            return False

        cap = cv2.VideoCapture(str(scene_path))
        if not cap.isOpened():
            cap.release()
            raise ValueError(f"Cannot open Manim video: {scene_path}")

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count < 10:
            cap.release()
            raise ValueError(f"Manim video has only {frame_count} frames")

        cap.release()
        return True

    def build_scenes(self, dialogue_json: Dict, run_paths: RunPaths) -> List[Path]:
        scenes = self.identify_visual_needs(dialogue_json)
        if not scenes:
            return []
        rendered: List[Path] = []
        for idx, scene in enumerate(scenes, start=1):
            class_name = f"AzureScene{idx}"
            code = self.generate_manim_code(scene["description"], class_name)
            scene_file = run_paths.visuals_dir / f"{class_name}.py"
            scene_file.write_text(code, encoding="utf-8")
        rendered = self.render_scenes(run_paths.visuals_dir)
        if scenes and not rendered:
            raise RuntimeError("Manim scene rendering failed: no outputs were produced.")
        return rendered

    def _extract_scene_class(self, scene_file: Path) -> str:
        pattern = re.compile(r"class\s+(\w+)\(Scene\)")
        for line in scene_file.read_text(encoding="utf-8").splitlines():
            match = pattern.search(line)
            if match:
                return match.group(1)
        raise ValueError(f"No Scene subclass found in {scene_file.name}")

    def _is_manim_available(self) -> bool:
        """
        Check whether the Manim CLI is available in PATH or importable via python -m manim.
        """
        if shutil.which("manim"):
            return True
        try:
            import manim  # noqa: F401
            return True
        except Exception:
            return False

    def _parse_scene_suggestions(self, raw_text: str) -> List[Dict[str, str]]:
        """Parse JSON list of scene descriptions from LLM response."""
        cleaned = self._strip_code_fences(raw_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        scenes: List[Dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("description", "")).strip()
            if desc:
                scenes.append({"description": desc})
            if len(scenes) >= 2:
                break
        return scenes

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
        reraise=True,
    )
    def _chat_completion(self, prompt: str, max_tokens: int):
        return self.client.chat.completions.create(
            model=self.settings.openai_deployment,
            messages=[
                {"role": "system", "content": "You write concise Manim Community scripts."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )

