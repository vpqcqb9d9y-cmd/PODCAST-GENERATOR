from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple


def _format_ts(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _compute_durations(turns: List[Tuple[int, str]], total_duration: float) -> List[float]:
    """
    Distribute total_duration across captions proportionally to word count,
    while keeping a reasonable min/max per caption.
    """
    if total_duration <= 0:
        return [0.0 for _ in turns]

    # Base heuristic per caption
    base_durations = []
    for _, text in turns:
        words = len(text.split()) or 1
        base_durations.append(min(6.0, max(2.0, words * 0.4)))

    total_base = sum(base_durations) or 1.0
    scale = total_duration / total_base
    scaled = [max(0.5, d * scale) for d in base_durations]  # keep floor

    # Adjust last caption to land exactly on total_duration
    cumulative = 0.0
    for i in range(len(scaled)):
        cumulative += scaled[i]
    if cumulative > 0:
        diff = total_duration - cumulative
        scaled[-1] = max(0.3, scaled[-1] + diff)

    return scaled


def generate_srt_from_dialogue(dialogue_json: Dict, total_duration: float, output_path: Path) -> Path:
    """
    Create captions.srt aligned to the audio duration.

    - Durations are proportional to word count but normalized to exactly total_duration.
    - Falls back to a flat split if dialogue is empty.
    """
    turns_raw = [d for d in dialogue_json.get("dialogue", []) if isinstance(d, dict)]
    turns: List[Tuple[int, str]] = []
    for idx, turn in enumerate(turns_raw, start=1):
        text = str(turn.get("text", "")).strip()
        if text:
            turns.append((idx, text))

    if not turns or total_duration <= 0:
        output_path.write_text("", encoding="utf-8")
        return output_path

    durations = _compute_durations(turns, total_duration)

    entries: List[str] = []
    cursor = 0.0
    for (idx, text), dur in zip(turns, durations):
        start = cursor
        end = min(cursor + dur, total_duration)
        cursor = end
        entries.append(f"{idx}\n{_format_ts(start)} --> {_format_ts(end)}\n{text}\n")
        if cursor >= total_duration:
            break

    output_path.write_text("\n".join(entries), encoding="utf-8")
    return output_path
