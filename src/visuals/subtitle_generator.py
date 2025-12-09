from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def _format_ts(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def generate_srt_from_dialogue(dialogue_json: Dict, total_duration: float, output_path: Path) -> Path:
    """
    Create captions.srt from dialogue JSON using a simple timing heuristic.

    Each caption gets 0.4s per word (clamped 2-6s). Stops at total_duration.
    """
    turns = [d for d in dialogue_json.get("dialogue", []) if isinstance(d, dict)]
    if not turns:
        return output_path

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
        entries.append(f"{idx}\n{_format_ts(start)} --> {_format_ts(end)}\n{text}\n")
        if cursor >= total_duration:
            break

    output_path.write_text("\n".join(entries), encoding="utf-8")
    return output_path
