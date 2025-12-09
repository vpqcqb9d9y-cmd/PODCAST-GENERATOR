from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from openai import APIError, APITimeoutError, AzureOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..utils import RunPaths, Settings, get_logger


HEBREW_FONT = "Arial"  # Default Hebrew-compatible font for generated scenes

KEYWORD_TO_SCENE = {
    "virtual network": "תרשים של משאבים בתוך VNet עם תתי-רשתות וחיבור ל-VPN.",
    "load balancer": "אנימציה של בקשות נכנסות המחולקות בין מופעי שרתים שונים.",
    "vm": "דיאגרמה של VM Scale Set עם הוספה והסרה אוטומטית של מכונות.",
    "storage": "השוואה בין Azure Blob, File Shares ו-Managed Disks.",
    "container": "מחשה של Cluster AKS שמריץ פודים ומאזן תעבורה.",
}


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
        Scan dialogue for keywords that need visualization.
        Returns a list of scene descriptors.
        """
        dialogues = dialogue_json.get("dialogue", [])
        full_text = " ".join(item.get("text", "").lower() for item in dialogues)
        matches: List[Dict[str, str]] = []
        for keyword, description in KEYWORD_TO_SCENE.items():
            if keyword in full_text:
                matches.append({"keyword": keyword, "description": description})
        return matches

    def generate_manim_code(self, scene_description: str, class_name: str) -> str:
        """
        Use Azure OpenAI to generate Manim Python code.
        """
        prompt = f"""
You are a Manim expert. Write a Python script using Manim Community v0.18.
- Create a class named {class_name} that inherits from Scene.
- Visualize the following concept in Hebrew annotations: {scene_description}
- Use simple geometric primitives, VGroup arrangements, and animations (Create, FadeIn, Arrow).
- Include a module-level constant HEBREW_FONT = "{HEBREW_FONT}" and use it for all Text/Mobject fonts to ensure RTL support.
- Make sure every scene includes at least two self.wait() calls (minimum 1 second each): one after the main animation and one before ending, to avoid blank/green frames.
- Return only valid Python code.
""".strip()
        response = self._chat_completion(prompt, max_tokens=900)
        code = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        code = self._strip_code_fences(code)
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
        Execute `manim -qm -o output.mp4 scene.py ClassName` for each scene file.
        Returns empty list if manim is not installed.
        """
        outputs: List[Path] = []
        for scene_file in scenes_directory.glob("*.py"):
            try:
                class_name = self._extract_scene_class(scene_file)
            except ValueError as exc:
                self.logger.warning("Skipping %s: %s", scene_file.name, exc)
                continue
            output_name = scene_file.with_suffix(".mp4").name
            cmd = ["manim", "-qm", "-o", output_name, str(scene_file), class_name]
            self.logger.info("Rendering %s", scene_file.name)
            try:
                subprocess.run(cmd, check=True, cwd=scenes_directory)
            except FileNotFoundError:
                self.logger.warning("Manim not installed; skipping animation rendering.")
                return []
            except subprocess.CalledProcessError as exc:
                self.logger.error("Manim failed for %s: %s", scene_file.name, exc)
                continue
            scene_output = scenes_directory / output_name
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
        return rendered

    def _extract_scene_class(self, scene_file: Path) -> str:
        pattern = re.compile(r"class\s+(\w+)\(Scene\)")
        for line in scene_file.read_text(encoding="utf-8").splitlines():
            match = pattern.search(line)
            if match:
                return match.group(1)
        raise ValueError(f"No Scene subclass found in {scene_file.name}")

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

