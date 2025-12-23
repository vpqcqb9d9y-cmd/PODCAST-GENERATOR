# User Guide (English)

This guide covers the main UI panels, key buttons, and common actions in M.B.S Studio.

## Layout Overview
- **Projects Hub (left)**: Browse past runs, open folders, play audio/video, load a run, or delete output. Status icons indicate available artifacts (🎧 audio, 🎬 video, 📊 PPTX, 📖 story).
- **Workspace (center)**: AI chat (Gemini/Azure), metadata editor, file/URL uploads, story preview. Ideal for preparing dialogue and metadata.
- **Control & Insights (right)**: Transcript selector, output mode toggles, voice profile picker, run buttons, gallery/status cards, and live run log.
- **Header banner**: Cost Center, Log Center, Appearance, Backup/Restore, About, Network/CPU badges.

## Core Buttons & Actions
- **Load transcript**: Choose the input transcript for the run.
- **Output mode**: Video+Audio / Audio-only / Full suite (video, PPT, story).
- **Run / Preview**: Start pipeline; Preview trims dialogue and limits visuals to speed up.
- **Voice profile**: Pick Azure/ElevenLabs voice set for Roee/Noa.
- **Include visuals**: Enable/disable video/visual generation; respects visual generator mode.
- **Generate visual metadata**: Builds or refreshes `visual_metadata.json` from story/metadata.
- **Cost Center**: Budgets, calculators, usage charts.
- **Log Center**: Live stdout view, copy/save log.
- **Backup/Restore**: Save or reload settings/history/UI state.

## Visuals & Timeline
- **Visual generator**: `manim`, `imagen`, `imagen_manim`, `veo`, or `hybrid`.
- **Image count**: Number of stills to request/generate.
- **Auto video duration**: Let audio length define video duration (recommended).
- **Timeline**: Assets ordered by index; images/videos stretched to audio; captions burned via FFmpeg, MoviePy overlay as fallback.

## Captions (BiDi)
- Captions use LRI/PDI isolation for embedded English/numbers and RLM for trailing punctuation to keep Hebrew+English in correct visual order. Shaping uses `arabic-reshaper` + `python-bidi` when available.
- Test string for quick verification: `שלום! ברוכים הבאים ל-Microsoft 365, זה עובד?`. You can render a sample clip to `outputs/tests/rtl_bidi_test.mp4`.

## CLI Quickstart
```bash
python -m scripts.generate_podcast transcript.txt metadata.json --include-visuals --voice-profile classic
```
Key flags:
- `--preview` or app preview mode: short, fast render with fewer visuals.
- `--skip-visuals`: audio-only.
- `--force`: rebuild all artifacts.
- `--output-dir PATH`: custom output root.

## Troubleshooting (common)
- **FFmpeg missing**: Install and add to PATH.
- **Hebrew path issues**: Video composition writes temp files to ASCII-safe temp dirs.
- **Visuals blank/black**: Check `visual_metadata.json` and quality report; rerender with real images or allow placeholders in non-adaptive mode.
- **Captions flipped**: Ensure BiDi deps installed; otherwise fallback isolation should still anchor punctuation.

For a full feature list and release notes, see the main `README.md`.

