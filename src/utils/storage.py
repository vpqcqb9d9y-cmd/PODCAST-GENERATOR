from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u0590-\u05fe]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "lecture"


def validate_history_entry_paths(entry: Dict) -> Dict:
    """
    Validate paths in a history entry and add a 'valid' flag.
    
    Checks if the run_dir exists and key files are accessible.
    
    Args:
        entry: History entry dict with paths
        
    Returns:
        Entry with added 'path_valid' boolean flag
    """
    run_dir_str = entry.get("run_dir", "")
    if not run_dir_str:
        entry["path_valid"] = False
        return entry
    
    run_dir = Path(run_dir_str)
    
    # Check if run directory exists
    if not run_dir.exists():
        entry["path_valid"] = False
        return entry
    
    # Check if at least one key file exists
    dialogue = entry.get("dialogue", "")
    audio = entry.get("final_audio", "")
    
    has_content = False
    if dialogue and Path(dialogue).exists():
        has_content = True
    if audio and Path(audio).exists():
        has_content = True
    if (run_dir / "metadata.json").exists():
        has_content = True
    if (run_dir / "dialogue.json").exists():
        has_content = True
    
    entry["path_valid"] = has_content or run_dir.exists()
    return entry


def get_valid_run_dir(entry: Dict) -> Optional[Path]:
    """
    Get a valid run directory path from a history entry.
    
    Args:
        entry: History entry dict
        
    Returns:
        Path object if valid, None if not
    """
    run_dir_str = entry.get("run_dir", "")
    if not run_dir_str:
        return None
    
    run_dir = Path(run_dir_str)
    if run_dir.exists():
        return run_dir
    
    return None


@dataclass
class RunPaths:
    """Encapsulate filesystem layout for a single lecture processing run."""

    base_dir: Path
    lecture_date: str
    topic: str
    transcript_language: str = ""
    transcript_language_secondary: str = ""
    transcript_is_mixed: bool = False
    transcript_hebrew_ratio: float = 0.0
    transcript_latin_ratio: float = 0.0
    transcript_language_detector: str = ""

    def __post_init__(self) -> None:
        topic_slug = _slugify(self.topic)
        self.run_dir = self.base_dir / f"{self.lecture_date}_{topic_slug}"
        self.dialogue_path = self.run_dir / "dialogue.json"
        self.metadata_path = self.run_dir / "metadata.json"
        self.log_path = self.run_dir / "processing_log.txt"
        self.audio_dir = self.run_dir / "audio_segments"
        self.visuals_dir = self.run_dir / "visuals"
        self.materials_dir = self.run_dir / "materials"
        self.cache_dir = self.base_dir / ".cache" / "dialogues"
        self.final_audio_path = self.run_dir / f"lecture_{self.lecture_date}_summary.mp3"
        self.final_video_path = self.run_dir / f"lecture_{self.lecture_date}_summary.mp4"
        self.ensure_directories()

    def ensure_directories(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.visuals_dir.mkdir(parents=True, exist_ok=True)
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")

