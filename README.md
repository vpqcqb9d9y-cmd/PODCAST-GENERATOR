# M.B.S Studio – AI Lecture-to-Podcast Pipeline

> Transform long-form Hebrew lectures into concise, studio-grade podcasts and explainer videos inspired by Google NotebookLM.
>
> Current version: **v3.2.0**

Looking for the full Hebrew documentation? Jump to the localized guide in [README.he.md](README.he.md) or scroll down to the “מדריך בעברית” section retained below.

## Table of Contents
- [🚀 Quick Start in 3 Steps](#-quick-start-in-3-steps)
- [🧙‍♂️ אשף מהיר לויז׳ואלס](#-אשף מהיר ליצירת ווידאו)
- [Overview](#overview)
- [Key Highlights](#key-highlights)
- [Architecture at a Glance](#architecture-at-a-glance)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Quickstart – CLI Pipeline](#quickstart--cli-pipeline)
- [M.B.S Studio GUI](#mbs-studio-gui)
- [Costs, Telemetry & Logs](#costs-telemetry--logs)
- [Project Layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Contributing & License](#contributing--license)
- [מדריך בעברית](#מדריך-במפורט-בעברית-המקור)

---

## 🚀 Quick Start in 3 Steps

**Get your first podcast in under 5 minutes:**

### Step 1: Setup
```bash
# Clone and install
git clone https://github.com/<org>/podcast-generator.git
cd podcast-generator
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI & Speech keys
```

### Step 2: Launch the GUI
```bash
# Windows
launch_gui.bat

# Or directly
python -m src.gui.app
```

### Step 3: Generate Your Podcast
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

**That's it!** Your podcast, video, and slides will be saved in `outputs/`.

---

## 🧙‍♂️ אשף מהיר לויז׳ואלס (חובה לווידאו!)

> ⚠️ **חשוב**: החל מגרסה **v3.1.3** הפייפליין או ה-GUI בונים תמיד `visual_metadata.json` גם אם ה-AI לא זמין, אבל זהו רק פתרון גיבוי. כדי לקבל פריימים קולנועיים עם טקסט עברי RTL עדיין מומלץ להפעיל את האשף לפני יצירת וידאו!

### אפשרות 1: דרך הממשק (GUI)
1. לחץ על כפתור **"🎨 צור מטא-דאטה ויזואלית"** בפאנל הימני
2. המתן לסיום היצירה (כמה שניות)
3. רק אז לחץ על **"הפעל Pipeline"**

### אפשרות 2: דרך שורת הפקודה
```bash
python -m scripts.create_visual_metadata ^
  outputs/2025-11-25_azure-networking-basics/story.json ^
  --metadata outputs/2025-11-25_azure-networking-basics/metadata.json ^
  --output   outputs/2025-11-25_azure-networking-basics/visual_metadata.json ^
  --image-count 10
```

### מה האשף עושה?
| שלב | פעולה |
|-----|-------|
| 1️⃣ | סורק את `story.json` ואת המושגים החשובים |
| 2️⃣ | מייצר 8-12 פריימים קולנועיים עם הנחיות עבריות RTL |
| 3️⃣ | מוסיף בלוק וידאו עם תיאור סצנות |
| 4️⃣ | מבטיח שכל פרומפט מזכיר "Hebrew overlays / RTL" |

### למה זה חשוב?
- **ללא visual_metadata.json** → תמונות גנריות, טקסט באנגלית, פלייסהולדרים
- **עם visual_metadata.json** → תמונות מותאמות, טקסט עברי RTL, איכות גבוהה

> 💡 **טיפ**: אם ה-story כבר מכיל אובייקט `metadata`, אין צורך בפרמטר `--metadata` – האשף יטען אותו לבד וישמור את הקובץ החדש באותה תיקייה.

---

## Overview
M.B.S Studio ingests a raw transcript (±30K words), enriches it with AI-driven metadata, and produces:
1. A natural-sounding dialogue between two virtual hosts (Roee & Noa).
2. Studio-quality Hebrew TTS tracks mixed into a finished podcast.
3. Optional visuals (Manim scenes + NotebookLM-like slides) and PPT exports.

## Key Highlights
- **Multi-stage pipeline** (Dialogue → Speech → Video) orchestrated via CLI or GUI.
- **NotebookLM-inspired metadata fabric** powered by Azure OpenAI & Gemini for bilingual contexts.
- **UI state persistence**: right rail width and chat font selections are saved to `config/ui_config.json` so your layout sticks between sessions.
- **Display Settings auto-save**: font size, theme, and bubble colors are written to `config/ui_config.json` when you click “OK” and are reloaded on the next launch/run.
- **Hebrew-first UX** with dynamic RTL/LTR text alignment (Hebrew messages align right, English left), RTL-aware chat, metadata editor, story preview, and gallery.
- **Dual TTS Support**: Azure Neural TTS (fast & affordable) or ElevenLabs (natural voices, 30+ options).
- **ElevenLabs Voice Selector**: Browse and preview 30+ voices with real-time provider switching.
- **Visual Model Selector**: Pick Imagen 4 (standard/fast) per run; deprecated Imagen 3 fast auto-migrates to Imagen 4.
- **Production Guardian (NEW)**: Auto-heals visuals, removes black frames, normalizes audio loudness, and applies Ken Burns to static images before final render.

### Visual Generation (NEW v2.6.1)
- **5 Visual Modes**: Choose from Manim (free), Imagen (images), Imagen+Manim ⭐, VEO (video), Hybrid 💎
- **VEO Video Generation**: Create AI-powered animated video clips with automatic fallback to placeholder videos
- **Smart Image Generation**: Respects `image_count` setting, extracts concepts from dialogue automatically
- **AI Helper Button**: 🤖 Get AI assistance to enrich metadata for optimal image generation
- **Cost Calculator**: Updated with accurate pricing for all visual modes

### Recent Updates (v3.1.3)
- **GUI Visual Metadata Reliability**: הוספנו ספינר חי והמרת חירום מקומית, כך שגם אם Gemini/Azure לא זמינים – הכפתור “🎨 צור מטא-דאטה ויזואלית” יחזור תוך 1‑2 דקות עם 10 פריימים + בלוק וידאו.
- **Always-On System Indicators**: מדדי CPU/NET/🔋 חוזרים לשורת הסטטוס התחתונה לטובת מסכים קטנים, בלי לוותר על תג הסטטוס הקומפקטי בכותרת.

### Recent Updates (v3.2.0)
- ProductionGuardian safeguards: validates assets, removes black frames, adaptive timelines without placeholders, Ken Burns pan/zoom, and audio normalization before video render.
- Voice Lab recording runs on a background thread with Stop / Play Preview / Delete controls to keep the UI responsive.
- Smart Preview caps dialogue to 3 turns, forces auto video duration, and limits preview images to 3 while preferring real frames over placeholders to avoid purple screens.
- Imagen selection is pinned to `imagen-4.0-generate-001` (fast/3.x values auto-upgrade) to prevent provider 404 errors.

### Recent Updates (v3.1.1)
- **Auto Visual Metadata Fallbacks**: אם לא קיים `visual_metadata.json` (או שהוא ריק), הפייפליין בונה אותו אוטומטית מתוך ה-story והמטא-דאטה – אין יותר ריצות שמייצרות רק פלייסהולדר כחול.
- **יציבות בדוחות איכות**: בדיקות האיכות כבר לא מתריעות לשווא על “No images defined”, כי קובץ הגיבוי כולל 8‑12 פריימים מלאים + בלוק וידאו.
- **תיעוד ועדכון גרסה**: README (אנגלית/עברית) והאפליקציה עודכנו ל־v3.1.1 כדי להדגיש את הגיבוי החדש ואת חוויית הוויז׳ואלס המשופרת.

### Recent Updates (v3.1.0)
- **Visual Metadata Wizard**: הפעלה בפקודה אחת (`python -m scripts.create_visual_metadata ...`) מייצרת `visual_metadata.json` עשיר מתוך story/metadata, כולל פריימים קולנועיים ובלוק וידאו.
- **Better Quality Checks**: הקומפוזר וה-Quality Checker משתמשים ב-OpenCV כדי לתפוס תמונות פגומות מראש ולנתח פריימים ירוקים/שחורים.
- **אשף מהיר להתחלה**: סעיף חדש ב-README (בעברית) שמסביר איך להפיק ויז׳ואלס מותאמים לפני הפייפליין – בלי צורך בעדכוני LLM ידניים.

### Recent Updates (v3.0.0)
- **Universal Content Processing System**: 🧠 Revolutionary AI that automatically classifies ANY educational content (technical, business, medical, creative, etc.) and adapts all processing accordingly.
- **Dynamic Visual Metadata Generation**: 🎨 Automatic generation of optimized visual prompts, styles, colors, and moods based on content type - no manual configuration needed.
- **Adaptive ETA & Processing**: ⚡ Smart weight calculation that optimizes processing time and resources based on content complexity and requirements.
- **Intelligent Content Classification**: 🏷️ 6 specialized content categories with tailored dialogue styles, visual aesthetics, and processing strategies.
- **Improved Video Composer**: 🎬 Fixed image integration in videos, enhanced Hebrew font support, and eliminated color changes at video end.
- **Visual Content Validation**: ✅ Automatic detection and logging of visual assets, with detailed quality reports and recommendations.
- **Sample Visual Metadata**: 📋 Complete example file (`data/sample_visual_metadata.json`) for Hebrew content creators.

### Recent Updates (v2.7.0)
- **Delete All Feature**: New "🗑️ מחק הכל" button to clear all projects physically while preserving cost history statistics.
- **Smart Cost Tracking**: Cost history survives project deletion, ensuring accurate budget tracking.
- **UI Improvements**: Main window opens maximized; dialogs remember their size/position; enhanced responsive layout.
- **ElevenLabs Voice Selector**: Added language indicators (🇮🇱/🇺🇸) to help identify Hebrew-compatible voices.
- **Transcript Management**: Smarter transcript handling that prevents accidental chat reset when reloading projects.
- **History Validation**: Auto-cleanup of invalid history entries with missing folders
- **Enhanced TTS Info**: Clear Hebrew support information for both Azure and ElevenLabs providers
- **Improved Launcher**: `launch_gui.bat` auto-installs dependencies and creates virtual environment
- **Transcript from Chat**: Generate transcript directly from AI chat conversation
- **Custom Project Names**: Set custom names for project directories
- **Improved ETA**: Weighted stage-based progress calculation for accurate time estimates
- **Network Map Export**: Generate Mermaid mindmaps from metadata for visualization
- **Backup & Restore**: Persist settings, history, and GUI state with one-click backup
- **Cost governance**: monthly budgets, live calculators, and cost-per-run telemetry with clear tables
- **History-aware workspace**: load the latest run in one click, inspect assets, open artifacts directly
- **Production diagnostics**: unified log center, automatic failure logs, and resumable runs
- **Sleep mode recovery**: Heartbeat monitoring with automatic stall detection during long renders

## Architecture at a Glance
| Stage | Responsibility | Key Modules |
|-------|----------------|-------------|
| Dialogue Generation | Chunk raw transcript, summarize, craft JSON dialogue | `src/dialogue/chunker.py`, `generator.py` |
| Speech Synthesis | Azure TTS or ElevenLabs, dual voices, leveling, mixdown | `src/audio/tts.py`, `elevenlabs_tts.py`, `stitcher.py` |
| Visuals & Slides | Manim animations, Google AI images/videos, slide composer, PPT export | `src/visuals/*.py`, `src/outputs/deck.py` |
| Pipeline Runner | Orchestrates CLI/GUI runs, cost tracking, logging, sleep recovery | `src/pipeline/runner.py`, `src/gui/app.py` |

Data products for each run land under `outputs/<date>_<slug>/` with dialogue JSON, metadata, audio stems, PPTX, story, slides, and logs.

## Prerequisites
- Python **3.9+**
- FFmpeg (available via `choco install ffmpeg` on Windows) and added to `PATH`
- Azure resources:
  - **Azure OpenAI** deployment (GPT-4o/4-turbo)
  - **Azure Speech Services** resource (optional if using ElevenLabs)
- Optional: Gemini API key for hybrid metadata seeding
- Optional: ElevenLabs API key for natural Hebrew voices

## TTS Providers

### Azure Neural TTS (Default)
Fast, reliable, and cost-effective. Good for rapid iterations and budget-conscious production.
- Cost: ~$0.016 per 1,000 characters
- Voices: he-IL-AvriNeural (Roee), he-IL-HilaNeural (Noa)

### ElevenLabs (Premium)
Natural-sounding multilingual voices. Recommended for high-quality Hebrew podcasts.
- Cost: ~$0.30 per 1,000 characters
- 30+ voices available with voice selector dialog
- Model: eleven_multilingual_v2

**To enable ElevenLabs:**
```env
ELEVENLABS_API_KEY=your-api-key
DEFAULT_TTS_PROVIDER=elevenlabs
```

**CLI usage:**
```bash
python -m scripts.generate_podcast transcript.txt metadata.json --tts-provider elevenlabs
```

## Google AI Visual Generation (NEW in v2.4)

Generate high-quality educational visuals using Google's latest AI models:

### Imagen 4 (Image Generation)
Create network maps, architecture diagrams, and slide backgrounds.
- **Models**: `imagen-4.0-generate-001` (standard), `imagen-4.0-ultra-generate-001` (high precision), `imagen-4.0-fast-generate-001` (fast)
- **Cost**: $0.02-$0.06 per image
- **Model selector in GUI**: choose the Imagen model per project; legacy `imagen-3.0-fast-generate-001` is migrated automatically to `imagen-4.0-generate-001` to avoid 404s.
- **Preview respects custom prompts**: even in Draft mode, existing `visual_metadata.json` prompts are passed through—no forced blue placeholders.

### VEO (Video Generation)
Create short animated scenes for educational content.
- **Model**: `veo-2.0-generate-001`
- **Cost**: $0.75 per second of video

## Troubleshooting

- **Use the launcher**: Always start the app via `launch_gui.bat` to ensure the virtual environment and dependencies load correctly. The script keeps the window open on errors so you can read them.
- **Imagen 4 safety settings**: Vertex AI requires `block_low_and_above` safety thresholds. If you see `400 INVALID_ARGUMENT ... Only block_low_and_above is supported for safetySetting`, update to the latest code and ensure your environment uses `IMAGEN_MODEL=imagen-4.0-generate-001`.
- **Models**: Defaults are `IMAGEN_MODEL=imagen-4.0-generate-001` and `VEO_MODEL=veo-2.0-generate-001`. Override in `.env` as needed.
- **Strict parameters for Imagen 4**: Current client builds must omit explicit safety settings to avoid local validation errors. Use the bundled code and `launch_gui.bat` to run.

## 🎥 Vertex AI Setup (Required for Imagen 4 & Veo)

To use advanced models like Imagen 4 and Veo, you must configure Google Cloud:

1. **Google Cloud Console**: Go to your project, ensure **Billing** is enabled.
2. **Enable APIs**: Search for and enable the **Vertex AI API**.
3. **Model Garden**: Go to Vertex AI -> Model Garden, search for "Imagen" and "Veo", and click **Enable/Agree**.
4. **Auth**: Run `gcloud auth application-default login` on your machine.
5. **Update .env**:

    ```bash
    GOOGLE_CLOUD_PROJECT=your-project-id
    GOOGLE_CLOUD_LOCATION=us-central1
    IMAGEN_MODEL=imagen-4.0-generate-001
    VEO_MODEL=veo-2.0-generate-001
    ```
   - Search for `Veo` and do the same.

### Step 2: Update .env File

No new API key is needed. Use your existing Gemini API key, but add the model settings:

```env
# --- Visual Generation Settings ---

# Choose generation mode:
# hybrid = Recommended combination (AI images + code animations + video)
VISUAL_GENERATOR=hybrid

# Model selection (Vertex AI):
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001

# Number of images to generate per project
IMAGE_COUNT=5

# Note: The system uses the GEMINI_API_KEY defined above.
# Ensure the project associated with this key is configured with Vertex AI API enabled.
```

### Visual Generator Modes

| Mode | Description | Cost | Output |
|------|-------------|------|--------|
| `manim` | Local Manim animations | **Free** | Mathematical/geometric animations |
| `imagen` | Google AI images only | ~$0.04/image | Static educational images (network maps, diagrams) |
| `imagen_manim` ⭐ | Imagen + Manim **Recommended!** | ~$0.04/image | Best balance: AI images + local animations |
| `veo` | VEO video generation | ~$0.75/sec | Up to 3 AI-generated video clips with fallback |
| `hybrid` 💎 | Full combo: All modes | Variable | Maximum quality: images + animations + video clips |

**VEO Video Generation (NEW v2.6.1):**
- Generates up to 3 short video clips: intro, concept explanations, conclusion
- Tries VEO API first, falls back to professional animated placeholders using moviepy
- Animated gradient backgrounds with motion graphics

**Configuration:**
```env
GEMINI_API_KEY=your-gemini-api-key
VISUAL_GENERATOR=imagen_manim  # manim | imagen | imagen_manim | veo | hybrid
IMAGE_COUNT=5  # Number of images to generate (1-20)
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001
```

**GUI Features:**
- Click "🎨 הגדרות ויזואליים" button to configure visual generation settings
- **🤖 AI Helper**: Click to get AI assistance for enriching metadata with key concepts
- Set image count: 1-20 images per project
- Set video duration: automatic (follows audio) or manual
- Cost calculator with accurate pricing for all modes
- "🧹 נקה טעינה" button clears workspace without deleting history data
- UI preferences (splitter sizes, right panel width, fonts, output mode) are stored in `config/ui_config.json`. Delete this file to reset layout to defaults.

## Troubleshooting

- **Video not generated / command shows `--skip-visuals`:** Ensure the output mode is set to `Video + Audio` (or `Full Suite`) and that the "צור וידאו/ויזואליזציות" checkbox is checked. Preferences are persisted in `config/ui_config.json`, so if visuals were disabled previously, re-enable them and rerun.

### Custom Visual Metadata
For professional-grade custom visuals instead of generic AI generation, create a `visual_metadata.json` file alongside your `metadata.json`:

```json
{
  "background": "Detailed context about your content for AI understanding",
  "general_notes": {
    "aesthetics": "Visual style guidelines and color preferences",
    "style_guide": "Technical specifications for consistent branding",
    "technical_specs": "Resolution, format, and quality requirements"
  },
  "images": [
    {
      "index": 1,
      "title": "Descriptive title for the image",
      "prompt": "Detailed AI prompt describing exactly what you want - include Hebrew text if needed",
      "style": "photorealistic, artistic, etc.",
      "mood": "dramatic, hopeful, energetic, etc.",
      "color_palette": "warm colors, cool tones, specific hex codes",
      "background_context": "How this image fits your narrative"
    }
  ],
  "video": {
    "prompt": "Detailed prompt for video generation with Hebrew elements",
    "duration_seconds": 180,
    "scenes": ["Scene descriptions"],
    "music_sync": "How video should sync with audio",
    "target_platforms": ["YouTube", "Instagram", "TikTok"],
    "style_guide": "Video-specific style requirements"
  }
}
```

**Benefits:**
- ✅ **100% Custom Control**: Specify exact prompts, styles, and colors
- ✅ **Professional Quality**: Consistent branding across all visuals
- ✅ **Hebrew-Optimized**: Full support for Hebrew content and aesthetics
- ✅ **Cost Effective**: Only generate what you actually need

**Sample File**: See `data/sample_visual_metadata.json` for a complete example based on Hebrew content.

## Installation & Setup
```bash
git clone https://github.com/<org>/podcast-generator.git
cd podcast-generator

pip install -e .[dev]   # editable dev install
# or
pip install -e .
```

1. Copy `.env.example` → `.env`.
2. Populate Azure OpenAI + Speech keys, region, deployments, and optional intro/outro audio paths.
3. Validate FFmpeg availability: `ffmpeg -version`.

> The Hebrew section below keeps the full step-by-step environment table if you prefer working in Hebrew.

## Quickstart – CLI Pipeline
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals \
  --voice-profile classic \
  --material assets/labs/lab1.pdf \
  --url https://learn.microsoft.com/en-us/azure/architecture/ \
  --export-ppt
```

Flags of interest:
- `--dry-run` – simulate without external API calls.
- `--skip-cache` – force-regenerate dialogue even if cached.
- `--force` – rebuild audio/video artifacts from scratch.
- `--output-dir custom_outputs` – override default run directory.

## M.B.S Studio GUI
Launch via `launch_gui.bat` (or `launch_gui.ps1`):

| Pane | Description |
|------|-------------|
| **Projects Hub (left)** | Recent runs, timeline, and NotebookLM-style explorer cards with quick actions (Folder/Audio/Video/Story/Load). |
| **Workspace (center)** | Hero prompt, onboarding wizard, AI chat (Gemini/Azure), upload slots for supporting files/URLs, metadata editor, live story preview. |
| **Control & Insights (right)** | Transcript picker, output mode toggles, voice profile selector, run controls, gallery with per-artifact status, and a run-status banner that mirrors pipeline logs. |

### Enhanced Progress Tracking (v2.0)
The pipeline now displays **visual progress** with stage icons and ETA:

| Stage | Icon | Description |
|-------|------|-------------|
| Initialize | 🚀 | Pipeline startup |
| Dialogue | 💬 | AI dialogue generation |
| TTS | 🎤 | Voice synthesis |
| Audio | 🎵 | Audio stitching |
| Video | 🎬 | Video composition |
| Complete | ✅ | Pipeline finished |

Progress includes:
- Real-time elapsed time display
- Estimated time remaining (ETA)
- Header status bar for quick glances

### Available Dialogs

| Dialog | Purpose | Access |
|--------|---------|--------|
| **Onboarding Wizard** | First-time user guidance with visual tips | Button in Workspace header |
| **Cost Center** | Budgets, charts, and live cost calculator | Header banner button |
| **Appearance Settings** | Font, color theme, chat background | Header banner button |
| **Log Center** | View, copy, and export pipeline logs | Header banner button |
| **Backup & Restore** | Save/load settings and history | 💾 button in header |
| **About** | Version info and credits | ℹ️ button in header |
| **Voice Selector** | Browse ElevenLabs/Azure voices with preview | Voice profile dropdown |
| **Network Map** | Export Mermaid mindmap from metadata | Button in metadata card |

### Additional UX Features
- **Cost Center** dialog centralizes calculators, budgets, and telemetry charts.
- **Log Center** keeps the latest stdout stream, clipboard copy, and "save to file".
- **History hydration** automatically restores chat + metadata when you load a run.
- **Onboarding Wizard** guides first-time users through the workflow.
- **Backup & Restore** persists `.env`, UI preferences, history, and GUI metadata.
- **TTS Provider Toggle** allows runtime switching between Azure and ElevenLabs.

### 🎙️ Voice Lab (Instant Voice Cloning)
- New tab next to Control Panel: **"🎙️ Voice Lab"**.
- **Upload/record** a clean 60s WAV/MP3 sample.
- Click **Clone with ElevenLabs** → creates a custom `voice_id` via Instant Voice Cloning.
- Saves profile **"Custom"** to `config/voice_profiles.json` (both speakers mapped to the cloned voice, model `eleven_multilingual_v2`).
- Shows **remaining ElevenLabs characters** from `v1/user/subscription` so you can track quota.
- Requires `ELEVENLABS_API_KEY`; without it the clone button is disabled.
- New controls: Record/Stop/Preview/Reset; cloning stays disabled until a valid file exists to prevent crashes.

## Costs, Telemetry & Logs
- Monthly OpenAI/TTS budgets with progress bars.
- Quick calculator (now inside Cost Center) estimates GPT/TTS/Video/PPT costs per run.
- Every pipeline run appends `processing_log.txt` + `history.json` entry with costs, tokens, and artifact paths.

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

## Troubleshooting
- **401 Unauthorized** – verify Azure OpenAI endpoint/key pair in `.env`.
- **404 DeploymentNotFound** – deployment name mismatch; copy the exact string from Azure Portal.
- **FFmpeg missing** – install + add to PATH.
- **Encoding issues** – ensure transcripts are UTF-8.
- **Audio desync** – rerun with `--force`.
- **Video render fails with Hebrew paths** – Fixed in v2.4.0! The system now uses temp directories with ASCII-only paths for FFMPEG.
- **Google API quota exceeded (429)** – Your free tier quota is exhausted. Wait 15 seconds or upgrade to a paid plan.
- **Pipeline stalls during sleep** – v2.4.0 includes heartbeat monitoring with automatic timeout detection.
- **Only 1 image generated** – This usually happens when metadata lacks `key_concepts`. Chat with the AI to build richer metadata before running the pipeline. As of v2.6.0, the system will attempt to extract concepts from dialogue automatically.
- **"נטען" (Loaded) message but nothing loads** – The folder may have been renamed or deleted. v2.6.0 auto-validates paths and removes invalid entries.
- **TTS Hebrew not working** – Both Azure and ElevenLabs support Hebrew. For Azure, use `he-IL-AvriNeural` or `he-IL-HilaNeural`. For ElevenLabs, ensure you're using the `eleven_multilingual_v2` model (default in profiles).
- **Startup crash: `chat_background_path` missing** – remove `config/ui_prefs.json` (the GUI will recreate it) or delete the unknown key from the file. v3.1.4 ignores unknown UI keys safely.

## Contributing & License
PRs are welcome (linters + pytest must pass). Licensed under **MIT**.

---

## מדריך מפורט בעברית (המקור)

הקטעים הבאים נשמרו כפי שהופיעו במדריך המקורי כדי שתוכלו לעבוד בעברית מקצה לקצה.

# Azure בפשטות – Educational Podcast Generator

מערכת אוטומטית להמרת הרצאות ארוכות (3 שעות) לפודקאסטים חינוכיים קצרים (8-10 דקות) בעברית, עם שני דוברים, אודיו איכותי, ואנימציות ויזואליות.

## סקירה כללית

הפרויקט לוקח תמלול של הרצאה ארוכה בעברית וממיר אותו לפודקאסט חינוכי דמוי Google NotebookLM, עם:

- **דיאלוג טבעי** בין שני דוברים (Roee - מומחה, Noa - סטודנטית)
- **קול עברי איכותי** באמצעות Azure Speech Services (שני קולות נפרדים)
- **אנימציות Manim** למושגים טכניים
- **וידאו סופי** המשלב אודיו + אנימציות

## ארכיטקטורה

המערכת מורכבת משלושה שלבים עיקריים:

### 1. יצירת דיאלוג (Dialogue Generation)
- **קלט**: תמלול גולמי (~30,000 מילים) + מטא-דאטה (נושא, תאריך, מושגים מרכזיים)
- **עיבוד**: 
  - חלוקה חכמה של התמלול לחלקים (Token-aware chunking)
  - סיכום חלקים ארוכים באמצעות Azure OpenAI
  - יצירת דיאלוג JSON מובנה בין שני דוברים
- **פלט**: `dialogue.json` עם מבנה מובנה של שיחה

### 2. המרה לקול (Text-to-Speech)
- **קלט**: `dialogue.json`
- **עיבוד**:
  - המרת כל משפט לקול עברי (SSML עם prosody)
  - Roee → `he-IL-AvriNeural` (קול גברי, בטוח)
  - Noa → `he-IL-HilaNeural` (קול נשי, סקרני)
  - הוספת 0.5 שניות שקטה בין דוברים
  - נורמליזציה של עוצמת הקול
- **פלט**: קבצי WAV נפרדים לכל משפט + `final_podcast.mp3` (128kbps, mono)

### 3. יצירת וידאו (אופציונלי)
- **קלט**: `dialogue.json` + `final_podcast.mp3`
- **עיבוד**:
  - זיהוי מושגים טכניים שצריכים ויזואליזציה (VM, Load Balancer, Storage, וכו')
  - יצירת קוד Manim לכל סצנה באמצעות Azure OpenAI
  - רינדור אנימציות (1080p, 30fps)
  - חיבור אודיו + אנימציות + intro/outro לוידאו אחד
- **פלט**: `final_video.mp4` (H.264, 1080p, 30fps)

## התקנה

### דרישות מוקדמות

1. **Python 3.9+**
2. **FFmpeg** - להתקנה ב-Windows:
   ```powershell
   choco install ffmpeg
   ```
   או הורדה מ-[ffmpeg.org](https://ffmpeg.org/download.html) והוספה ל-PATH

3. **Azure Resources**:
   - משאב **Azure OpenAI** (עם deployment של GPT-4o או GPT-4-turbo)
   - משאב **Azure Speech Services**

### התקנת תלויות

```bash
# התקנה במצב editable (לפיתוח)
pip install -e .[dev]

# או התקנה רגילה
pip install -e .
```

### הגדרת משתני סביבה

1. העתק את `.env.example` ל-`.env`:
   ```bash
   cp .env.example .env
   ```

2. מלא את הערכים ב-`.env`:

   **Azure OpenAI** (חובה):
   ```env
   AZURE_OPENAI_ENDPOINT=https://<resource-name>.openai.azure.com/
   AZURE_OPENAI_API_KEY=<key מהמשאב OpenAI>
   AZURE_OPENAI_DEPLOYMENT=<שם הפריסה המדויק>
   AZURE_OPENAI_API_VERSION=2024-02-01
   ```
   
   **Azure Speech Services** (חובה):
   ```env
   AZURE_SPEECH_KEY=<key מהמשאב Speech>
   AZURE_SPEECH_REGION=westeurope
   AZURE_SPEECH_ENDPOINT=https://westeurope.api.cognitive.microsoft.com/
   ```

   **קבצי אודיו** (אופציונלי):
   ```env
   INTRO_MUSIC=assets/audio/intro.mp3
   OUTRO_MUSIC=assets/audio/outro.mp3
   ```

   **הגדרות נוספות**:
   ```env
   OUTPUT_BASE_DIR=outputs
   ENABLE_VISUALS=true
   CACHE_DIALOGUES=true
  VOICE_PROFILES_PATH=config/voice_profiles.json
  VOICE_PROFILES_DEFAULT=classic
   MONTHLY_TTS_CHARACTER_LIMIT=450000
   MONTHLY_OPENAI_COST_LIMIT=180.0
   ```

   **מחולל מטא-דאטה בסגנון NotebookLM (Gemini)**
   ```env
   GEMINI_API_KEY=<מפתח מודל Gemini 1.5>
   GEMINI_MODEL=gemini-1.5-flash
   METADATA_SYSTEM_PROMPT=אתה NotebookLM Assistant שמייצר מטא-דאטה עשיר בהרכב עברית/אנגלית טבעי.
   ```

### איך למצוא את הערכים ב-Azure Portal

#### Azure OpenAI:
1. פתח את משאב Azure OpenAI בפורטל
2. עבור ל-**Keys and Endpoint**
3. העתק:
   - **Endpoint** (מסתיים ב-`.openai.azure.com/`)
   - **Key 1** או **Key 2**
4. עבור ל-**Deployments** והעתק את **שם הפריסה** המדויק

#### Azure Speech Services:
1. פתח את משאב Speech Services בפורטל
2. עבור ל-**Keys and Endpoint**
3. העתק:
   - **Key 1** או **Key 2**
   - **Location/Region** (למשל: `westeurope`)

## שימוש

### פקודה בסיסית

```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json
```

### עם ויזואליזציה

```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals
```

**בחירת פרופיל קולות + חומרים תומכים:**
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals \
  --voice-profile energetic \
  --material assets/labs/lab1.pdf \
  --url https://learn.microsoft.com/en-us/azure/architecture/ \
  --export-ppt
```

### דוגמאות נוספות

**דרי-ראן (ללא קריאות API)**:
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --dry-run
```

**דילוג על cache**:
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --skip-cache
```

**כוח (regenerate הכל)**:
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --force
```

**תיקיית פלט מותאמת**:
```bash
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --output-dir custom_outputs
```

### ממשק M.B.S Studio (GUI)

1. התקן תלויות והפעל `launch_gui.bat` (או `launch_gui.ps1`).
2. החלון החדש מחולק לשלושה אזורים:
   - **Projects Hub** (שמאל): כרטיסיות עם כל הריצות, כפתורי Open/Play/PPT, וסייר תוצרים עם חיפוש, טעינת פרויקט קיים או מחיקתו, ולוח זמנים ל-30 הימים האחרונים.
   - **M.B.S Workspace** (מרכז): צ'אט אינטראקטיבי עם Gemini/Azure, כפתורי-שבלונה (סכם שיעור, תכנן מצגת...), העלאת קבצים וקישורים, ומטא-דאטה שנבנה אוטומטית מתמלול בודד (כולל אזהרה כשזוהתה תערובת עברית/אנגלית).
   - **Control & Insights** (ימין): בחירת תמלול, בחירת תוצר, קולות, ביצוע pipeline, ועורך JSON מלא למטא-דאטה עם כפתורי שמירה/שחזור, Story חי וגלריית תוצרים.
3. לחצן “מרכז עלויות” בראש העמוד פותח דיאלוג ייעודי לניהול המגבלות, תרשימי הצריכה וסטטיסטיקות ה-30 הימים האחרונים.
4. לחצן “מרכז לוגים” מאפשר להעתיק/לשמור את הלוג הנוכחי, והמערכת שומרת אוטומטית קובץ לוג בתיקיית הפרויקט במקרה של תקלה.
5. לוג ריצה מובנה בתחתית מציג כל פקודה/שגיאה בזמן אמת.

כך אפשר לתכנן שיעור שלם “בסגנון NotebookLM” בלי להקליד JSON ידנית: מדברים עם הבינה, גוררים קבצים, מקבלים מטא-דאטה עשיר (כולל עריכה ידנית + Save/Revert) ומריצים את ה-Pipeline באותו חלון.

#### חוויית משתמש מחודשת

- ברירת מחדל: בחירה בתמלול בלבד מפעילה מאחורי הקלעים ייצור מטא-דאטה בסיסי ושאלות המשך.
- טקסטים בעברית מיושרים לימין באופן אוטומטי (צ'אט, מטא-דאטה, Story); טקסטים באנגלית נשארים משמאל.
- גלריית הפרויקטים כוללת סייר תיקיות עם חיפוש, טעינת פרויקטים קיימים ומחיקה מלאה של תיקיות פלט, כולל סמלי סטטוס (🎧/🎬/📊/📖).
- ניהול העלויות עבר ללחצן “מרכז עלויות” שמרכז מגבלות, תרשימים והתראות במקום כרטיסים עמוסים.
- כרטיס “מחשבון עלויות” מחשב עלויות משוערות לפי מילים/דקות וסוגי התוצרים שתבחרו.
- כרטיס המטא-דאטה כולל כפתור “מפת רשת” שמייצא Mermaid mindmap של מושגים, Labs והמלצות המשך.
- כפתור “מרכז לוגים” מציג את הלוג האחרון ומאפשר להעתיקו או לשמור אותו תוך שמירת אוטומטית של תקלות בכל תיקיית פרויקט.
- בורר מודלי Imagen חדש (4.0 רגיל/מהיר) וגם במצב טיוטה משתמש ב-visual_metadata אם קיים – בלי פלייסהולדר כחול.
- Voice Lab עם כפתורי Record/Stop/Preview/Reset ושיכפול קולי זמין רק לאחר בחירת קובץ תקין.

### מבנה קובץ מטא-דאטה

קובץ ה-JSON של המטא-דאטה צריך להכיל:

```json
{
  "topic": "שם ההרצאה",
  "date": "2025-11-24",
  "key_concepts": [
    "מושג 1",
    "מושג 2",
    "מושג 3"
  ],
  "labs": [
    "Lab 1: יצירת VM",
    "Lab 2: הגדרת Load Balancer"
  ],
  "speaker": "שם המרצה (אופציונלי)",
  "extra_notes": "הערות נוספות (אופציונלי)",
  "source_video": "נתיב לקובץ וידאו מקורי (אופציונלי)"
}
```

## מבנה הפרויקט

```
PODCAST GENERATOR/
├── src/
│   ├── dialogue/          # יצירת דיאלוג
│   │   ├── generator.py   # Azure OpenAI integration
│   │   └── chunker.py     # Token-aware text splitting
│   ├── audio/             # המרה לקול
│   │   ├── tts.py         # Azure Speech TTS
│   │   └── stitcher.py    # חיבור קבצים + intro/outro
│   ├── visuals/           # אנימציות ווידאו
│   │   ├── manim_generator.py  # יצירת קוד Manim
│   │   └── video_composer.py   # חיבור אודיו+וידאו
│   ├── pipeline/          # אורכיסטרציה
│   │   └── runner.py      # Pipeline orchestrator
│   └── utils/             # כלי עזר
│       ├── config.py      # טעינת הגדרות
│       ├── logging.py     # Structured logging
│       ├── storage.py     # ניהול נתיבים
│       └── costs.py       # מעקב עלויות
├── scripts/
│   └── generate_podcast.py  # CLI entry point
├── tests/                 # בדיקות
├── assets/
│   └── audio/            # קבצי intro/outro
├── data/                 # קבצי דוגמה
├── outputs/              # תוצאות (נוצר אוטומטית)
│   └── 2025-11-24_<topic>/
│       ├── dialogue.json
│       ├── audio_segments/
│       ├── final_podcast.mp3
│       ├── metadata.json
│       ├── processing_log.txt
│       └── visuals/      # אם --include-visuals
└── .env                  # הגדרות (לא ב-git)
```

## קבצי פלט

לכל הרצאה נוצר תיקייה ב-`outputs/` עם המבנה הבא:

```
outputs/2025-11-24_<topic>/
├── dialogue.json              # דיאלוג מלא (JSON)
├── metadata.json              # מטא-דאטה של ההרצאה
├── processing_log.txt         # לוג מפורט של כל השלבים
├── audio_segments/           # קבצי WAV נפרדים
│   ├── segment_0.wav
│   ├── segment_1.wav
│   └── ...
├── final_podcast.mp3         # פודקאסט סופי (128kbps, mono)
├── summary.pptx              # מצגת סיכום (אם הופעלה)
├── story.md / story.json     # סיפור NotebookLM אינטראקטיבי
└── visuals/                  # אם --include-visuals
    ├── scene_0.mp4
    ├── scene_1.mp4
    └── final_video.mp4       # וידאו סופי (1080p, 30fps)
```

### העשרת מטא-דאטה (חומרים תומכים)
- אפשר להעביר קבצים (`--material` או דרך ה-GUI) וקישורים (`--url`) שהמערכת תסכם באמצעות Azure OpenAI.
- התוצרים נשמרים תחת `metadata.json`:
  - `supporting_materials`: מערך עם תקציר, Labs, References, Reading List לכל חומר.
  - מפתחות `labs`, `references`, `reading_list` מורחבים אוטומטית על בסיס הממצאים.
- הקבצים עצמם מועתקים לתת-תיקייה `materials/` בתוך תיקיית הריצה לצורך תיעוד.

## עלויות

### Free Tier
- **Speech TTS**: 500,000 תווים בחודש (חינם)
- **OpenAI**: $200 קרדיט בחודש הראשון

### תעריפים עדכניים (נובמבר 2025)

| שירות | מחיר קלט (ל-1K tokens) | מחיר פלט (ל-1K tokens) | מקור |
| --- | --- | --- | --- |
| Azure OpenAI GPT-4o | **$0.005** | **$0.015** | [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) |
| Google Gemini 1.5/2.5 Flash (Vertex AI) | **$0.00035** | **$0.00105** | [Vertex AI pricing](https://cloud.google.com/vertex-ai/pricing#generative_ai_models) |
| Azure Neural TTS (Standard) | — | **$16 / מיליון תווים** | [Azure Speech pricing](https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/) |
| ElevenLabs (Multilingual v2) | — | **$300 / מיליון תווים** | [ElevenLabs pricing](https://elevenlabs.io/pricing) |

> *הערכים מסוכמים מהדף הרשמי של Microsoft ו-Google נכון לנובמבר 2025; בדקו שוב במדינות/מטבעות שונים.*

### נוסחה מהירה להערכת Pipeline

1. **הערכת טוקנים**: `tokens ≈ #מילים × 1.3`.  
2. **עלות GPT**: `Cost_GPT ≈ (tokens / 1000) × (0.005 לקלט + 0.015 לפלט)` כשמייצרים אודיו+וידאו (הנחה: פלט ≈ 60% מהקלט).  
3. **הערכת תווי דיבור**: `speech_chars ≈ #מילים × 4.5`.  
4. **עלות TTS**: `Cost_TTS ≈ (speech_chars / 1,000,000) × $16`.  
5. **סה\"כ** = `Cost_GPT + Cost_TTS` (הוסף עוד 10% למנימל מתמטיקה/Manim).

**דוגמה**: הרצאה של ~12,000 מילים → ≈ 15,600 טוקנים קלט ו-9,000 פלט.  
`Cost_GPT ≈ (15.6 × 0.005) + (9 × 0.015) ≈ $0.26`.  
`speech_chars ≈ 54,000 → Cost_TTS ≈ $0.86`.  
סה\"כ ≈ **$1.1** לפני רינדור וידאו.

### עלות משוערת להרצאה אחת
- **Pipeline מלא (וידאו + PPTX + Story)**: ~**$1.1** להרצאה של 3 שעות (ע"פ הדוגמה למעלה).
- **מצב Audio-only**: ~**$0.23** (GPT-4o ≈ $0.15 + Speech ≈ $0.08).

### מחשבון עלויות ב-GUI
- בכרטיס “מחשבון עלויות” (בפאנל הימני של M.B.S Studio) מזינים מספר מילים או דקות, בוחרים את ספק ה-AI (Azure GPT-4o או Gemini Flash) ומסמנים אילו תוצרים תרצו להפיק.
- בלחיצה על “חשב עלות משוערת” מוצג פירוט העלויות (מודל, TTS, רינדור וידאו, PPTX) והסכום הכולל, בהתאם למחירי הסעיף הקודם.
- תרחישי הכשל נשמרים בהעתק לוג בתיקיית הפרויקט, ואפשר להעתיק או לשמור את הלוג גם דרך כפתור “מרכז לוגים”.

## פתרון בעיות

### שגיאת 401 PermissionDenied
**סיבה**: מפתח API שגוי או endpoint לא נכון  
**פתרון**: ודא ש-`AZURE_OPENAI_ENDPOINT` מסתיים ב-`.openai.azure.com/` ושהמפתח תואם למשאב OpenAI

### שגיאת 404 DeploymentNotFound
**סיבה**: שם הפריסה ב-`.env` לא תואם לפריסה ב-Azure  
**פתרון**: פתח את משאב Azure OpenAI → Deployments → העתק את השם המדויק (כולל מקפים/אותיות גדולות)

### שגיאת FFmpeg לא נמצא
**סיבה**: FFmpeg לא מותקן או לא ב-PATH  
**פתרון**: התקן FFmpeg והוסף ל-PATH:
```powershell
choco install ffmpeg
```

### שגיאת encoding בעברית
**סיבה**: קובץ לא ב-UTF-8  
**פתרון**: ודא שכל קבצי הטקסט (תמלול, מטא-דאטה) שמורים ב-UTF-8

### אודיו לא מסונכרן
**סיבה**: קבצי segment לא נוצרו כראוי  
**פתרון**: הרץ עם `--force` כדי ליצור מחדש את כל קבצי האודיו

## תכונות מתקדמות

### Caching
המערכת שומרת cache של דיאלוגים שנוצרו. אם תעבור על אותו תמלול שוב, היא תשתמש ב-cache (אלא אם תעבור עם `--skip-cache`).

### Retry Logic
כל קריאת API כוללת retry אוטומטי (3 ניסיונות) עם exponential backoff.

### Resume Support
אם ההרצה נכשלה באמצע, אפשר להריץ שוב והמערכת תמשיך מהנקודה שבה נעצרה.

## בדיקות

```bash
# הרצת כל הבדיקות
pytest

# בדיקה ספציפית
pytest tests/test_chunker.py
```

## לוגים

כל הרצה יוצרת `processing_log.txt` עם:
- טיימינג של כל שלב
- שימוש ב-tokens/characters
- עלויות משוערות
- אזהרות ושגיאות

## רישיון

MIT

## תמיכה

לשאלות או בעיות, פתח issue ב-repository.

---

**הערה**: הפרויקט מיועד להרצאות חינוכיות בעברית. תמיכה בשפות נוספות אפשרית בעתיד.
