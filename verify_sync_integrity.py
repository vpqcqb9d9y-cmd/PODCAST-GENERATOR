#!/usr/bin/env python3
"""Validate that captions.srt timing matches audio segment durations."""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import wave


TimecodePattern = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})")


@dataclass
class SrtEntry:
    index: int
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def parse_timecode(code: str) -> float:
    match = TimecodePattern.fullmatch(code.strip())
    if not match:
        raise ValueError(f"Invalid timecode: {code!r}")
    h = int(match.group("h"))
    m = int(match.group("m"))
    s = int(match.group("s"))
    ms = int(match.group("ms"))
    return h * 3600 + m * 60 + s + ms / 1000.0


def load_srt(path: Path) -> List[SrtEntry]:
    content = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
    entries: List[SrtEntry] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            idx = len(entries) + 1
        times = lines[1]
        try:
            start_s, end_s = [parse_timecode(t) for t in times.split("-->")]
        except Exception:
            continue
        text = "\n".join(lines[2:]) if len(lines) > 2 else ""
        entries.append(SrtEntry(index=idx, start=start_s, end=end_s, text=text))
    entries.sort(key=lambda e: e.start)
    return entries


def _recursive_find_numeric_list(obj: Any) -> Optional[List[float]]:
    if isinstance(obj, list) and obj and all(isinstance(x, (int, float)) for x in obj):
        return [float(x) for x in obj]
    if isinstance(obj, dict):
        for val in obj.values():
            found = _recursive_find_numeric_list(val)
            if found:
                return found
    return None


def load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_segment_durations(data: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    if not data:
        return None
    for key in ("segment_durations", "segments_durations", "segment_lengths", "segments"):
        if key in data and isinstance(data[key], list):
            numeric = [float(x) for x in data[key] if isinstance(x, (int, float))]
            if numeric:
                return numeric
    return _recursive_find_numeric_list(data)


def extract_lead_in(data: Optional[Dict[str, Any]], explicit: Optional[float]) -> float:
    if explicit is not None:
        return max(0.0, explicit)
    if not data:
        return 0.0
    for key in ("lead_in_seconds", "lead_in", "intro_duration"):
        value = data.get(key)
        if isinstance(value, (int, float)):
            return max(0.0, float(value))
    return 0.0


def probe_wav_duration(path: Path) -> Optional[float]:
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate == 0:
                return None
            return frames / float(rate)
    except Exception:
        return None


def load_audio_durations(segments_dir: Path) -> List[float]:
    if not segments_dir.exists():
        return []
    durations: List[float] = []
    files = sorted([p for p in segments_dir.iterdir() if p.suffix.lower() == ".wav"])
    for p in files:
        dur = probe_wav_duration(p)
        if dur is not None:
            durations.append(dur)
    return durations


def group_entries_by_turn(
    entries: List[SrtEntry], lead_in: float, segment_durations: List[float], tol: float
) -> List[List[SrtEntry]]:
    groups: List[List[SrtEntry]] = []
    cursor = lead_in
    idx = 0
    for seg_dur in segment_durations:
        turn_entries: List[SrtEntry] = []
        boundary = cursor + seg_dur
        while idx < len(entries):
            turn_entries.append(entries[idx])
            idx += 1
            next_start = entries[idx].start if idx < len(entries) else None
            if next_start is None or next_start >= boundary - tol:
                break
        groups.append(turn_entries)
        cursor = boundary
    return groups


def check_gaps_overlaps(entries: List[SrtEntry], tol: float) -> List[str]:
    issues: List[str] = []
    for prev, nxt in zip(entries, entries[1:]):
        gap = nxt.start - prev.end
        if gap > tol:
            issues.append(f"Gap of {gap:.3f}s between entry {prev.index} and {nxt.index}")
        elif gap < -tol:
            issues.append(f"Overlap of {-gap:.3f}s between entry {prev.index} and {nxt.index}")
    return issues


def run_validation(
    srt_path: Path,
    dialogue_path: Optional[Path],
    quality_path: Optional[Path],
    segments_dir: Optional[Path],
    lead_in_arg: Optional[float],
    tolerance: float,
    skip_audio_check: bool,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if not srt_path.exists():
        return False, [f"SRT file not found: {srt_path}"]

    srt_entries = load_srt(srt_path)
    if not srt_entries:
        return False, ["No subtitles found in SRT."]

    dialogue_json = load_json(dialogue_path)
    quality_json = load_json(quality_path)

    segment_durations = extract_segment_durations(quality_json) or extract_segment_durations(dialogue_json)
    if not segment_durations:
        return False, ["segment_durations not found in quality_report.json or dialogue.json"]

    lead_in_seconds = extract_lead_in(quality_json, lead_in_arg)

    first_start = srt_entries[0].start
    if abs(first_start - lead_in_seconds) > tolerance:
        errors.append(
            f"Lead-in mismatch: first subtitle starts at {first_start:.3f}s, expected {lead_in_seconds:.3f}s "
            f"(delta {first_start - lead_in_seconds:+.3f}s)"
        )

    groups = group_entries_by_turn(srt_entries, lead_in_seconds, segment_durations, tolerance)

    cursor = lead_in_seconds
    for turn_idx, (seg_dur, turn_entries) in enumerate(zip(segment_durations, groups), start=1):
        if not turn_entries:
            errors.append(f"Turn {turn_idx}: no subtitles mapped to this turn.")
            cursor += seg_dur
            continue
        start_delta = abs(turn_entries[0].start - cursor)
        if start_delta > tolerance:
            errors.append(
                f"Turn {turn_idx}: start mismatch (subtitle {turn_entries[0].index}) "
                f"delta={turn_entries[0].start - cursor:+.3f}s"
            )

        total_turn_duration = sum(e.duration for e in turn_entries)
        duration_delta = abs(total_turn_duration - seg_dur)
        if duration_delta > tolerance:
            errors.append(
                f"Turn {turn_idx}: duration mismatch (SRT {total_turn_duration:.3f}s vs audio {seg_dur:.3f}s) "
                f"delta={total_turn_duration - seg_dur:+.3f}s"
            )
        cursor += seg_dur

    issues = check_gaps_overlaps(srt_entries, tolerance)
    errors.extend(issues)

    if not skip_audio_check and segments_dir:
        audio_durations = load_audio_durations(segments_dir)
        if not audio_durations:
            errors.append(f"No audio segments found in {segments_dir} for duration check.")
        else:
            for idx, seg_dur in enumerate(segment_durations):
                if idx >= len(audio_durations):
                    errors.append(
                        f"Audio segment missing for turn {idx + 1}: expected {len(segment_durations)} files, "
                        f"found {len(audio_durations)}"
                    )
                    break
                audio_dur = audio_durations[idx]
                delta = abs(audio_dur - seg_dur)
                if delta > tolerance:
                    errors.append(
                        f"Turn {idx + 1}: audio duration mismatch (file {audio_dur:.3f}s vs reported {seg_dur:.3f}s) "
                        f"delta={audio_dur - seg_dur:+.3f}s"
                    )

    ok = len(errors) == 0
    return ok, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify that captions.srt aligns with dialogue segment durations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--srt", type=Path, default=Path("captions.srt"), help="Path to captions.srt")
    parser.add_argument(
        "--dialogue", type=Path, default=Path("dialogue.json"), help="Path to dialogue.json (optional fallback)"
    )
    parser.add_argument(
        "--quality", type=Path, default=Path("quality_report.json"), help="Path to quality_report.json (optional)"
    )
    parser.add_argument(
        "--segments-dir",
        type=Path,
        default=Path("audio_segments"),
        help="Directory containing per-turn audio segments (.wav)",
    )
    parser.add_argument("--lead-in", type=float, default=None, help="Override lead-in seconds (intro music).")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Allowed timing drift in seconds.")
    parser.add_argument(
        "--skip-audio-check",
        action="store_true",
        help="Skip validating segment durations against audio files (useful for mock data).",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    ok, errors = run_validation(
        srt_path=args.srt,
        dialogue_path=args.dialogue,
        quality_path=args.quality,
        segments_dir=args.segments_dir,
        lead_in_arg=args.lead_in,
        tolerance=args.tolerance,
        skip_audio_check=args.skip_audio_check,
    )

    print("==== Validation Report ====")
    print(f"SRT: {args.srt}")
    print(f"Dialogue: {args.dialogue}")
    print(f"Quality report: {args.quality}")
    print(f"Segments dir: {args.segments_dir}")
    print(f"Lead-in (expected): {args.lead_in if args.lead_in is not None else 'auto'}")
    print(f"Tolerance: {args.tolerance:.3f}s")

    if ok:
        print("Status: PASS")
        return 0

    print("Status: FAIL")
    for issue in errors:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

