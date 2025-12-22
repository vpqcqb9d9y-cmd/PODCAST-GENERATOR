from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import re

import arabic_reshaper
from bidi.algorithm import get_display


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


def _split_turn_text(
    text: str,
    max_words: int = 10,
    max_chars: int = 80,
) -> List[str]:
    """
    Split a dialogue turn into smaller chunks for readability.

    - Prefer sentence boundaries (., !, ?, …).
    - Further split long sentences into ~max_words chunks and enforce max_chars.
    """
    if not text:
        return []

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[\.!\?…])\s+", text)
        if s and s.strip()
    ]
    if not sentences:
        sentences = [text.strip()]

    chunks: List[str] = []
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        current: List[str] = []
        for word in words:
            tentative = " ".join(current + [word]).strip()
            if (
                current
                and (len(tentative) > max_chars or len(current) >= max_words)
            ):
                chunks.append(" ".join(current).strip())
                current = [word]
            else:
                current.append(word)
        if current:
            chunks.append(" ".join(current).strip())

    # Merge very short trailing chunks into previous ones to avoid over-fragmentation
    merged: List[str] = []
    for chunk in chunks:
        if merged:
            prev = merged[-1]
            prev_words = prev.split()
            chunk_words = chunk.split()
            if (
                len(chunk_words) <= 3
                and len(prev_words) + len(chunk_words) <= max_words
                and len(prev) + 1 + len(chunk) <= max_chars
            ):
                merged[-1] = f"{prev} {chunk}".strip()
                continue
        merged.append(chunk)

    chunks = merged

    # Safety: if everything was filtered out, return the raw text
    return chunks or [text.strip()]


def generate_srt_from_dialogue(
    dialogue_json: Dict,
    total_duration: float,
    output_path: Path,
    segment_durations: Optional[Iterable[float]] = None,
    lead_in_seconds: float = 0.0,
    outro_seconds: float = 0.0,
) -> Path:
    """
    Create captions.srt aligned to the audio duration.

    - If segment_durations is provided, use exact per-segment audio lengths.
    - Otherwise, durations are proportional to word count but normalized to the speech window.
    - lead_in_seconds offsets captions (e.g., intro music), outro_seconds keeps tail silent.
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

    # Dedicate window to speech only (exclude intro/outro padding)
    speech_window = max(0.0, total_duration - lead_in_seconds - outro_seconds)

    durations: List[float]
    if segment_durations:
        durations = [max(0.01, float(d or 0.0)) for d in segment_durations]
        # If provided durations do not cover all turns, pad with minimal durations
        if len(durations) < len(turns):
            durations.extend([0.5] * (len(turns) - len(durations)))
    else:
        durations = _compute_durations(turns, speech_window)

    entries: List[str] = []
    cursor = lead_in_seconds
    latest_end_allowed = lead_in_seconds + speech_window if speech_window > 0 else total_duration
    entry_index = 1

    for (turn_idx, text), dur in zip(turns, durations):
        if cursor >= latest_end_allowed:
            break

        chunks = _split_turn_text(text, max_words=10, max_chars=80)
        if not chunks:
            continue

        # Duration split per chunk based on word weight
        word_counts = [max(1, len(c.split())) for c in chunks]
        total_words = sum(word_counts) or len(chunks)
        raw_allocations = [dur * (wc / total_words) for wc in word_counts]

        # Enforce a minimal duration and fix rounding drift on the last chunk
        min_chunk = 0.3
        chunk_durations: List[float] = []
        for alloc in raw_allocations:
            chunk_durations.append(max(min_chunk, alloc))

        drift = dur - sum(chunk_durations)
        if chunk_durations:
            chunk_durations[-1] = max(min_chunk, chunk_durations[-1] + drift)

        for chunk_text, chunk_dur in zip(chunks, chunk_durations):
            if cursor >= latest_end_allowed:
                break
            start = min(cursor, latest_end_allowed)
            end = min(cursor + chunk_dur, latest_end_allowed)
            if end <= start:
                continue

            # Shape RTL text exactly once at SRT creation time
            shaped = arabic_reshaper.reshape(chunk_text)
            bidi_text = get_display(shaped)

            entries.append(
                f"{entry_index}\n{_format_ts(start)} --> {_format_ts(end)}\n{bidi_text}\n"
            )
            entry_index += 1
            cursor = end

        # Protect against overruns in cases where durations were very small
        cursor = min(cursor, latest_end_allowed)

    output_path.write_text("\n".join(entries), encoding="utf-8")
    return output_path
