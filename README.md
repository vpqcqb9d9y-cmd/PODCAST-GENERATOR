# M.B.S Studio – AI Lecture-to-Podcast Pipeline

Transform long-form Hebrew lectures into concise, studio-grade podcasts and explainer videos inspired by Google NotebookLM.

Current version: **v3.2.1**  
Looking for the full Hebrew documentation? Jump to [`README.he.md`](README.he.md) or the “מדריך בעברית” section below.

---

## Table of Contents
- 🚀 Quick Start in 3 Steps
- 🧙‍♂️ אשף מהיר לויז׳ואלס
- Overview
- Key Highlights
- Architecture at a Glance
- Prerequisites
- Installation & Setup
- Quickstart – CLI Pipeline
- M.B.S Studio GUI
- Google AI Visual Generation
- TTS Providers
- Costs, Telemetry & Logs
- Troubleshooting
- Project Layout
- Contributing & License
- מדריך בעברית

---

## 🚀 Quick Start in 3 Steps
Get your first podcast in under 5 minutes.

**Step 1: Setup**
```bash
git clone https://github.com/<org>/podcast-generator.git
cd podcast-generator
pip install -e .

cp .env.example .env
# Edit .env with your Azure OpenAI & Speech keys
```

**Step 2: Launch the GUI**
```bash
# Windows
launch_gui.bat

# Or directly
python -m src.gui.app
```

**Step 3: Generate Your Podcast**
```
┌─────────────────────────────────────────────────────────────────────┐
│  📁 Projects Hub  │  💬 AI Workspace     │  🎛️ Control Panel       │
├───────────────────┼──────────────────────┼─────────────────────────┤
│                   │  1️⃣ Chat with AI     │  4️⃣ Choose transcript    │
│  Previous runs    │     to build         │     & output settings   │
│  and history      │     metadata         │                         │
│                   │                      │  5️⃣ Click "הפעל Pipeline"│
│                   │  2️⃣ Upload files     │                         │
│                   │     & URLs           │  6️⃣ Watch progress with │
│                   │                      │     🚀💬🎤🎬 icons     │
│                   │  3️⃣ Preview Story    │     and ETA             │
└───────────────────┴──────────────────────┴─────────────────────────┘
```
Your podcast, video, and slides will be saved in `outputs/`.

---

## 🧙‍♂️ אשף מהיר לויז׳ואלס (חובה לווידאו!)
⚠️ החל מ-v3.1.3 הפייפליין בונה `visual_metadata.json` אוטומטית גם בלי AI, אך כדי לקבל פריימים קולנועיים עם טקסט עברי RTL מומלץ להפעיל את האשף לפני הווידאו.

**GUI**  
1. לחץ על “🎨 צור מטא-דאטה ויזואלית” בפאנל הימני.  
2. חכה לסיום (שניות).  
3. רק אז לחץ “הפעל Pipeline”.

**CLI**  
```bash
python -m scripts.create_visual_metadata ^
  outputs/2025-11-25_azure-networking-basics/story.json ^
  --metadata outputs/2025-11-25_azure-networking-basics/metadata.json ^
  --output   outputs/2025-11-25_azure-networking-basics/visual_metadata.json ^
  --image-count 10
```

| שלב | פעולה |
|-----|-------|
| 1️⃣ | סורק story.json והמושגים החשובים |
| 2️⃣ | מייצר 8‑12 פריימים קולנועיים RTL |
| 3️⃣ | מוסיף בלוק וידאו עם תיאור סצנות |
| 4️⃣ | מבטיח תיוג “Hebrew overlays / RTL” |

למה חשוב?  
- ללא `visual_metadata.json`: תמונות גנריות, טקסט באנגלית, פלייסהולדרים.  
- עם `visual_metadata.json`: תמונות מותאמות, טקסט RTL, איכות גבוהה.  
טיפ: אם ה-story כולל metadata – אין צורך ב-`--metadata`.

---

## Overview
M.B.S Studio ingests a raw transcript (±30K words), enriches it with AI-driven metadata, and produces:
- A natural-sounding dialogue between two virtual hosts (Roee & Noa).
- Studio-quality Hebrew TTS tracks mixed into a finished podcast.
- Optional visuals (Manim scenes + NotebookLM-like slides) and PPT exports.

## Key Highlights
- Multi-stage pipeline (Dialogue → Speech → Video).
- NotebookLM-inspired metadata fabric (Azure OpenAI & Gemini).
- UI state persistence and RTL-first UX.
- Dual TTS (Azure / ElevenLabs) with voice selector.
- Visual model selector (Imagen 4), Production Guardian (Ken Burns, black-frame cleanup, adaptive timelines, audio normalization).

### Visual Generation
- 5 modes: Manim, Imagen, Imagen+Manim ⭐, VEO, Hybrid 💎
- VEO clips (up to 3) with placeholder fallback.
- AI helper for metadata; cost calculator.

### Recent Updates
- v3.3.0: chat banner spacing, offline guard for network actions, mic visualizer, transcript context in chat, Azure TTS dropdown fetches voices, MP4 uploads blocked in picker.
- v3.2.0: ProductionGuardian safeguards, Voice Lab background thread, Smart Preview limits, Imagen pinned to `imagen-4.0-generate-001`.
- v3.1.3: Visual wizard spinner + local fallback; system indicators restored.
- v3.1.1: Auto visual_metadata.json when missing; quality checks no longer warn on “No images defined”.
- v3.1.0: One-command visual wizard, OpenCV checks, quick-start visual guide.
- v3.0.0: Universal content classification, dynamic visual metadata, adaptive ETA, improved composer.

---

## Architecture at a Glance
| Stage | Responsibility | Key Modules |
|-------|----------------|-------------|
| Dialogue Generation | Chunk raw transcript, summarize, craft JSON dialogue | `src/dialogue/chunker.py`, `generator.py` |
| Speech Synthesis | Azure TTS or ElevenLabs, dual voices, leveling, mixdown | `src/audio/tts.py`, `elevenlabs_tts.py`, `stitcher.py` |
| Visuals & Slides | Manim animations, Google AI images/videos, slide composer, PPT export | `src/visuals/*.py`, `src/outputs/deck.py` |
| Pipeline Runner | Orchestrates CLI/GUI runs, cost tracking, logging, sleep recovery | `src/pipeline/runner.py`, `src/gui/app.py` |

Data products live under `outputs/<date>_<slug>/` (dialogue, metadata, audio stems, PPTX, story, visuals, logs).

## Prerequisites
- Python 3.9+
- FFmpeg in PATH (`choco install ffmpeg` on Windows)
- Azure OpenAI + Speech
- Optional: Gemini API key (hybrid visuals), ElevenLabs API key (premium TTS)

## TTS Providers
**Azure Neural TTS (default)** — ~$0.016/1K chars. Voices: he-IL-AvriNeural, he-IL-HilaNeural.  
**ElevenLabs** — ~$0.30/1K chars; 30+ voices; model `eleven_multilingual_v2`.  
Enable ElevenLabs:
```env
ELEVENLABS_API_KEY=your-api-key
DEFAULT_TTS_PROVIDER=elevenlabs
```

## Google AI Visual Generation
- Imagen 4: network maps, diagrams, slide backgrounds. Models: `imagen-4.0-generate-001` (fast/ultra variants).
- VEO: short animated scenes (~$0.75/s), with placeholder fallback.
- Modes: `manim`, `imagen`, `imagen_manim`, `veo`, `hybrid` (full combo).
- Visual metadata: supply `visual_metadata.json` for best quality (Hebrew RTL prompts). Auto-generated when missing; wizard recommended.

## Installation & Setup
```bash
pip install -e .[dev]
```
`.env` essentials:
```env
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=...

# Visuals (Vertex AI)
GEMINI_API_KEY=...
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001
VISUAL_GENERATOR=hybrid
IMAGE_COUNT=5
```

## Quickstart – CLI Pipeline
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals \
  --voice-profile classic \
  --export-ppt
```
Flags: `--dry-run`, `--skip-cache`, `--force`, `--output-dir`, `--material`, `--url`.

## M.B.S Studio GUI
- Launch via `launch_gui.bat` (keeps window open on errors).
- Panes: Projects Hub (history/timeline/explorer), Workspace (AI chat, uploads, metadata, story), Control & Insights (transcript/output mode/voices/run controls/gallery).
- Banner buttons: refresh/update check, backup/restore, about, Cost Center, Appearance, Log Center, 🎨 Visual settings.
- Voice Lab: record/stop/preview/reset; clone with ElevenLabs; shows remaining characters.

### Progress Tracking
Stages with icons/ETA: 🚀 Initialize → 💬 Dialogue → 🎤 TTS → 🎵 Audio → 🎬 Video → ✅ Complete.

### Available Dialogs
Onboarding, Cost Center, Appearance, Log Center, Backup/Restore, About, Voice Selector, Network Map export.

## Costs, Telemetry & Logs
- Per-run `processing_log.txt` and `history.json` with costs, tokens, stage timings.
- Cost calculator (GPT/TTS/Video/PPT) in Cost Center.
- Budgets for OpenAI/TTS recommended.

## Troubleshooting
- Hybrid visuals: `VISUAL_GENERATOR=hybrid` merges Imagen + Manim clips automatically.
- PPTX text-only fallback when visuals missing.
- FFmpeg missing → install/add to PATH.
- Encoding → ensure UTF-8.
- Audio desync → `--force`; Hotfix 3.2.1 enforces duration match.
- Azure 401/404 → verify endpoint/key/deployment names.
- Imagen 4 safety: use `imagen-4.0-generate-001`; omit explicit safety params.
- Gemini/Imagen quota: placeholders will be produced; check logs.

## 🎥 Vertex AI Setup (Imagen 4 & VEO)
1. Enable Billing + Vertex AI API in Google Cloud.  
2. In Model Garden, enable Imagen and Veo.  
3. Auth locally: `gcloud auth application-default login`.  
4. `.env`:
```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001
VISUAL_GENERATOR=hybrid
IMAGE_COUNT=5
```

### Visual Generator Modes
| Mode | Cost | Output |
|------|------|--------|
| manim | Free | Local animations |
| imagen | ~$0.04/img | Static educational images |
| imagen_manim ⭐ | ~$0.04/img | AI images + Manim |
| veo | ~$0.75/s | Up to 3 AI clips |
| hybrid 💎 | Variable | Images + animations + clips |

---

## Project Layout
```
PODCAST GENERATOR/
├── src/
│   ├── dialogue/   # transcript chunking + dialogue generation
│   ├── audio/      # TTS + stitching
│   ├── visuals/    # Manim + slide composer
│   ├── outputs/    # PPT/story exporters
│   ├── pipeline/   # CLI/GUI orchestration
│   └── utils/      # config, logging, storage, costs
├── scripts/        # CLI entry points
├── tests/          # pytest suite
├── assets/         # intro/outro audio
├── data/           # sample inputs
└── outputs/        # generated runs
```

## Contributing & License
- PRs are welcome (linters + pytest must pass).
- License: **MIT**.

---

## מדריך בעברית (תקציר)
למדריך מלא בעברית ראו [`README.he.md`](README.he.md).  
הקטעים הבאים נשמרו לטובת עבודה בעברית מקצה לקצה (דיאלוג, TTS, ויזואליים, העלויות, מבנה הריצה והפתרון בעיות בעברית).

