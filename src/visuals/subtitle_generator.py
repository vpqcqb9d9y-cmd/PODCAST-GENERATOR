from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import re

try:
    import arabic_reshaper  # type: ignore
    from bidi.algorithm import get_display  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    arabic_reshaper = None
    get_display = None


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


def fix_rtl_text(text: str) -> str:
    """
    Apply BiDi shaping so mixed Hebrew/English and punctuation render correctly.

    - Uses arabic_reshaper + python-bidi when available.
    - Falls back to the original text if shaping fails or dependencies are missing.
    """
    if not text:
        return ""
    shaped = text
    if arabic_reshaper is not None:
        try:
            shaped = arabic_reshaper.reshape(text)
        except Exception:
            shaped = text
    if get_display is not None:
        try:
            return get_display(shaped, base_dir="R")
        except Exception:
            return shaped
    return shaped


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

    durations: List[float]
    has_segments = bool(segment_durations)
    if has_segments:
        durations = [max(0.01, float(d or 0.0)) for d in segment_durations or []]
        if len(durations) < len(turns):
            durations.extend([0.5] * (len(turns) - len(durations)))
    else:
        speech_window = max(0.0, total_duration - lead_in_seconds - outro_seconds)
        durations = _compute_durations(turns, speech_window)

    entries: List[str] = []
    cursor = lead_in_seconds
    entry_index = 1

    if has_segments:
        for (_, text), dur in zip(turns, durations):
            if dur <= 0:
                dur = 0.01

            chunks = _split_turn_text(text, max_words=10, max_chars=80)
            if not chunks:
                cursor += dur
                continue

            word_counts = [max(1, len(c.split())) for c in chunks]
            total_words = sum(word_counts) or len(chunks)
            raw_allocations = [dur * (wc / total_words) for wc in word_counts]

            min_chunk = 0.3
            chunk_durations: List[float] = [max(min_chunk, alloc) for alloc in raw_allocations]
            drift = dur - sum(chunk_durations)
            if chunk_durations:
                chunk_durations[-1] = max(min_chunk, chunk_durations[-1] + drift)

            chunk_cursor = cursor
            for chunk_text, chunk_dur in zip(chunks, chunk_durations):
                start = chunk_cursor
                end = chunk_cursor + chunk_dur
                if end <= start:
                    continue
                visual_text = fix_rtl_text(chunk_text)

                entries.append(
                    f"{entry_index}\n{_format_ts(start)} --> {_format_ts(end)}\n{visual_text}\n"
                )
                entry_index += 1
                chunk_cursor = end

            # Advance cursor strictly by the provided segment duration to keep contiguous timing
            cursor += dur
    else:
        speech_window = max(0.0, total_duration - lead_in_seconds - outro_seconds)
        audio_limit = total_duration if total_duration > 0 else lead_in_seconds + speech_window
        if outro_seconds > 0 and total_duration > 0:
            audio_limit = max(0.0, total_duration - outro_seconds)
        latest_end_allowed = lead_in_seconds + speech_window if speech_window > 0 else audio_limit
        latest_end_allowed = min(latest_end_allowed, audio_limit) if audio_limit > 0 else latest_end_allowed

        for (_, text), dur in zip(turns, durations):
            if cursor >= latest_end_allowed:
                break

            chunks = _split_turn_text(text, max_words=10, max_chars=80)
            if not chunks:
                continue

            word_counts = [max(1, len(c.split())) for c in chunks]
            total_words = sum(word_counts) or len(chunks)
            raw_allocations = [dur * (wc / total_words) for wc in word_counts]

            min_chunk = 0.3
            chunk_durations: List[float] = [max(min_chunk, alloc) for alloc in raw_allocations]
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
                visual_text = fix_rtl_text(chunk_text)

                entries.append(
                    f"{entry_index}\n{_format_ts(start)} --> {_format_ts(end)}\n{visual_text}\n"
                )
                entry_index += 1
                cursor = end

            cursor = min(cursor, latest_end_allowed)

    output_path.write_text("\n".join(entries), encoding="utf-8")
    return output_path
