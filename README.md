# M.B.S Studio – AI Lecture-to-Podcast Pipeline

Transform long-form Hebrew lectures into concise, studio-grade podcasts and explainer videos. Inspired by Google NotebookLM, built with PyQt6 and a hybrid Manim/Google AI visuals stack.

> **Current version: v3.4.2** | **Build date: 2025-12-21**  
> Hebrew guide: see [`README.he.md`](README.he.md)

---

## Hotfix 3.4.2
- **Manim resilience**: Auto-fallback to `python -m manim` when CLI isn’t on PATH, and absolute paths + `--media_dir` prevent nested/relative path breaks on Windows/Hebrew.
- **Subtitles in sync**: SRT durations are normalized to the final audio length (word-weighted), so captions hug the spoken timeline and end exactly with audio.
- **Visual pipeline**: Verified preview runs include real Manim clips and Google Imagen frames; placeholders avoided unless no visuals survive validation.

## Hotfix 3.3.2
- **Topic-true visuals**: Removed Azure/vendor defaults from visual metadata; prompts now adapt to topic/mood (tech vs art/music) with hallucination guardrails.
- **Visible subtitles**: Final render burns SRT via FFmpeg with Hebrew-safe Arial + black box; MoviePy fallback parses UTF-8 and reshapes RTL.
- **Liveliness**: Stronger Ken Burns (zoom 1.15 + drift) and timeline respects dialogue timestamps when available.

---

## Key Features
- PyQt6 GUI with Projects, AI Workspace, and Control panels.
- Voice Lab: record, preview, and clone voices via ElevenLabs.
- System monitor banner (CPU/MEM/battery/network) with live badge.
- End-to-end pipeline: chunking, dialogue generation, TTS, stitching, visuals, PPT/story export.
- Cost center, logs center, history browser, backup/restore utilities.
- CLI scripts for headless pipeline and visual metadata generation.

## Installation
1. **Prerequisites**
   - Python 3.9+
   - FFmpeg on PATH
   - Optional APIs: Azure OpenAI + Speech, ElevenLabs, Google Generative AI
2. **Set up**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e .
   # Dev: pip install -e .[dev]
   ```
3. **Configure secrets** (env vars or .env)
   - `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`
   - `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`
   - Optional: `ELEVENLABS_API_KEY`, `GOOGLE_API_KEY`

## Usage
- **Launch GUI**
  ```bash
  python run_gui.py
  ```
  or `launch_gui.bat` / `launch_gui.ps1`.

- **Run pipeline via CLI**
  ```bash
  python -m scripts.generate_podcast --help
  ```

- **Tests**
  ```bash
  pip install -e .[dev]
  pytest
  ```

## Project Structure
```
PODCAST GENERATOR/
├── run_gui.py               # GUI entry point (imports gui.main)
├── launch_gui.bat / .ps1    # GUI launchers
├── build_exe.bat            # Packaging helper
├── config/                  # UI prefs and voice profiles
├── data/                    # Sample transcript/metadata
├── outputs/                 # Generated runs, history, backups
├── scripts/                 # CLI tools (generate_podcast, create_visual_metadata, tests)
├── src/
│   ├── gui/                 # PyQt6 app
│   │   ├── app.py           # PodcastGeneratorWindow + main()
│   │   ├── controllers/     # SystemMonitorController, VoiceLabController
│   │   ├── workers.py       # PipelineWorker, ChatWorker, RecordingWorker, etc.
│   │   ├── panels/          # Projects, Workspace, Control/Summary builders
│   │   ├── dialogs/         # About, Backup, Cost/Log centers, Voice selector
│   │   ├── widgets.py       # Custom scroll/chat widgets
│   │   └── constants.py     # App display name, stages, theme constants
│   ├── audio/               # TTS, stitching
│   ├── dialogue/            # Chunking + dialogue generation
│   ├── visuals/             # Manim/video composition, Google AI visuals
│   ├── metadata/            # Chat session + metadata builders
│   ├── pipeline/            # CLI/runner orchestration
│   └── utils/               # Settings, logging, storage, costs, helpers
├── tests/                   # Pytest suite
├── pyproject.toml           # Package metadata & dependencies
├── README.md                # English guide (this file)
└── README.he.md             # Hebrew guide
```

### Responsibilities
- `run_gui.py` / `gui.main`: launch the desktop UI.
- `scripts/generate_podcast.py`: headless pipeline entry.
- `scripts/create_visual_metadata.py`: build/verify visual metadata.
- `src/gui/controllers/`: encapsulated GUI logic (system metrics, Voice Lab).
- `src/gui/workers.py`: QThread/QObject workers for pipeline/chat/recording.
- `src/gui/panels/`: UI builders for projects, workspace, control tabs.
- `src/audio/`: TTS synthesis and audio stitching.
- `src/dialogue/`: transcript chunking and dialogue generation.
- `src/visuals/`: visual metadata, Manim/video composition, Google AI visuals.
- `src/utils/`: settings, logging, storage, cost tracking, helpers.
- `config/`: user prefs and voice profiles.
- `outputs/`: generated artifacts, logs, backups, history.

## Notes & Tips
- Ensure FFmpeg is installed and on PATH for video/audio steps.
- Voice Lab cloning requires `ELEVENLABS_API_KEY`; otherwise the clone button stays disabled.
- Azure and Google keys enable their respective AI providers; the app degrades gracefully if keys are missing.

---

## Version History

### Recent Updates (v3.4.0)
- Google Imagen fully upgraded to Imagen 4 (Fast/Standard/Ultra) with refreshed pricing; legacy Imagen 3 selections are auto-migrated.
- Cost Center adds advanced FinOps: per-provider reset days (Azure/Gemini/ElevenLabs), UTC-accurate cycle progress + days-remaining countdown, and grouped monthly history with totals; friendlier Hebrew labels for AI/TTS.
- Visual safety: loading a project now detects existing `visual_metadata.json`, marks it as loaded, and warns before regenerating to avoid extra API charges.
- Visual settings & calculators use the selected Imagen 4 variant pricing for estimates.

### Recent Updates (v3.3.1)
- Manim scene selection uses LLM-derived geometric concepts from dialogue (no hardcoded keywords).
- OpenCV reads are Unicode-safe across Guardian, Composer, and QA, eliminating false corrupt-image flags on Hebrew paths.
- QA video analysis wraps `VideoCapture` failures with MoviePy fallback and detects short/empty prompts in visual metadata.
- Guardian preserves assets on read errors while still removing true black frames.

### Recent Updates (v3.3.0)
- Live Chat banner padding adjusted for better vertical spacing.
- Network-dependent actions now block when offline and flash the bottom status banner in red.
- Voice Lab adds a live mic visualizer while recording.
- Chat sessions include the active transcript snippet/path for better context in metadata building.
- Azure TTS dropdown now fetches available Neural voices (key/region required) and respects your selection.
- Transcription picker is restricted to text files (MP4 uploads disabled to avoid crashes).

### Recent Updates (v3.2.1) - Hotfix Release
- **Hybrid visuals**: Fixed image inclusion in hybrid mode - both AI images and Manim animations are now merged correctly.
- **Audio sync**: Enforced video duration matching audio duration; FFmpeg fallback ensures audio is always attached.
- **GUI stability**: Global exception handler prevents silent crashes - all errors are logged and displayed.
- **API resilience**: Google AI failures (quota/network) now generate placeholders automatically, allowing pipeline to complete.

### Recent Updates (v3.2.0)
- ProductionGuardian safeguards: validates assets, removes black frames, adaptive timelines without placeholders, Ken Burns pan/zoom, and audio normalization before video render.
- Voice Lab recording runs on a background thread with Stop / Play Preview / Delete controls to keep the UI responsive.
- Smart Preview caps dialogue to 3 turns, forces auto video duration, and limits preview images to 3 while preferring real frames over placeholders to avoid purple screens.
- Imagen selection is pinned to imagen-4.0-generate-001 (fast/3.x values auto-upgrade) to prevent provider 404 errors.

### Recent Updates (v3.1.3)
- GUI Visual Metadata Reliability: Added live spinner and local fallback conversion, so even if Gemini/Azure are unavailable, the "🎨 צור מטא-דאטה ויזואלית" button returns within 1-2 minutes with 10 frames + video block.
- Always-On System Indicators: CPU/NET/🔋 metrics return to the bottom status bar for small screens, without sacrificing the compact status badge in the header.

### Recent Updates (v3.1.1)
- Auto Visual Metadata Fallbacks: If visual_metadata.json doesn't exist (or is empty), the pipeline builds it automatically from story and metadata – no more runs that produce only blue placeholders.
- Quality report stability: Quality checks no longer falsely warn about "No images defined", because the backup file includes 8-12 full frames + video block.

### Recent Updates (v3.1.0)
- Visual Metadata Wizard: One-command execution (`python -m scripts.create_visual_metadata ...`) generates rich visual_metadata.json from story/metadata, including cinematic frames and video block.
- Better Quality Checks: Composer and Quality Checker use OpenCV to catch damaged images early and analyze green/black frames.
- Quick Start Guide: New section in README (Hebrew) explaining how to generate custom visuals before the pipeline – no manual LLM updates needed.

### Recent Updates (v3.0.0)
Universal Content Processing System: 🧠 Revolutionary AI that automatically classifies ANY educational content (technical, business, medical, creative, etc.) and adapts all processing accordingly.
Dynamic Visual Metadata Generation: 🎨 Automatic generation of optimized visual prompts, styles, colors, and moods based on content type - no manual configuration needed.
Adaptive ETA & Processing: ⚡ Smart weight calculation that optimizes processing time and resources based on content complexity and requirements.
Intelligent Content Classification: 🏷️ 6 specialized content categories with tailored dialogue styles, visual aesthetics, and processing strategies.
Improved Video Composer: 🎬 Fixed image integration in videos, enhanced Hebrew font support, and eliminated color changes at video end.
Visual Content Validation: ✅ Automatic detection and logging of visual assets, with detailed quality reports and recommendations.
Sample Visual Metadata: 📋 Complete example file (data/sample_visual_metadata.json) for Hebrew content creators.
Recent Updates (v2.7.0)
Delete All Feature: New "🗑️ מחק הכל" button to clear all projects physically while preserving cost history statistics.
Smart Cost Tracking: Cost history survives project deletion, ensuring accurate budget tracking.
UI Improvements: Main window opens maximized; dialogs remember their size/position; enhanced responsive layout.
ElevenLabs Voice Selector: Added language indicators (🇮🇱/🇺🇸) to help identify Hebrew-compatible voices.
Transcript Management: Smarter transcript handling that prevents accidental chat reset when reloading projects.
History Validation: Auto-cleanup of invalid history entries with missing folders
Enhanced TTS Info: Clear Hebrew support information for both Azure and ElevenLabs providers
Improved Launcher: launch_gui.bat auto-installs dependencies and creates virtual environment
Transcript from Chat: Generate transcript directly from AI chat conversation
Custom Project Names: Set custom names for project directories
Improved ETA: Weighted stage-based progress calculation for accurate time estimates
Network Map Export: Generate Mermaid mindmaps from metadata for visualization
Backup & Restore: Persist settings, history, and GUI state with one-click backup
Cost governance: monthly budgets, live calculators, and cost-per-run telemetry with clear tables
History-aware workspace: load the latest run in one click, inspect assets, open artifacts directly
Production diagnostics: unified log center, automatic failure logs, and resumable runs
Sleep mode recovery: Heartbeat monitoring with automatic stall detection during long renders
Architecture at a Glance
Stage	Responsibility	Key Modules
Dialogue Generation	Chunk raw transcript, summarize, craft JSON dialogue	src/dialogue/chunker.py, generator.py
Speech Synthesis	Azure TTS or ElevenLabs, dual voices, leveling, mixdown	src/audio/tts.py, elevenlabs_tts.py, stitcher.py
Visuals & Slides	Manim animations, Google AI images/videos, slide composer, PPT export	src/visuals/*.py, src/outputs/deck.py
Pipeline Runner	Orchestrates CLI/GUI runs, cost tracking, logging, sleep recovery	src/pipeline/runner.py, src/gui/app.py
Data products for each run land under outputs/<date>_<slug>/ with dialogue JSON, metadata, audio stems, PPTX, story, slides, and logs.

Prerequisites
Python 3.9+
FFmpeg (available via choco install ffmpeg on Windows) and added to PATH
Azure resources:
Azure OpenAI deployment (GPT-4o/4-turbo)
Azure Speech Services resource (optional if using ElevenLabs)
Optional: Gemini API key for hybrid metadata seeding
Optional: ElevenLabs API key for natural Hebrew voices
TTS Providers
Azure Neural TTS (Default)
Fast, reliable, and cost-effective. Good for rapid iterations and budget-conscious production.

Cost: ~$0.016 per 1,000 characters
Voices: he-IL-AvriNeural (Roee), he-IL-HilaNeural (Noa)
ElevenLabs (Premium)
Natural-sounding multilingual voices. Recommended for high-quality Hebrew podcasts.

Cost: ~$0.30 per 1,000 characters
30+ voices available with voice selector dialog
Model: eleven_multilingual_v2
To enable ElevenLabs:

ELEVENLABS_API_KEY=your-api-key
DEFAULT_TTS_PROVIDER=elevenlabs
CLI usage:

python -m scripts.generate_podcast transcript.txt metadata.json --tts-provider elevenlabs
Google AI Visual Generation (NEW in v2.4)
Generate high-quality educational visuals using Google's latest AI models:

Imagen 4 (Image Generation)
Create network maps, architecture diagrams, and slide backgrounds.

Models: imagen-4.0-generate-001 (standard), imagen-4.0-ultra-generate-001 (high precision), imagen-4.0-fast-generate-001 (fast)
Cost: $0.03-$0.06 per image
Model selector in GUI: choose the Imagen model per project; legacy imagen-3.0-fast-generate-001 is migrated automatically to imagen-4.0-generate-001 to avoid 404s.
Preview respects custom prompts: even in Draft mode, existing visual_metadata.json prompts are passed through—no forced blue placeholders.
VEO (Video Generation)
Create short animated scenes for educational content.

Model: veo-2.0-generate-001
Cost: $0.75 per second of video
Troubleshooting
Hybrid visuals (Imagen + Manim): VISUAL_GENERATOR=hybrid now merges Google Imagen stills with local Manim clips into one timeline. No extra flags needed—both asset types are passed to the composer automatically.
PPTX text-only fallback: Slide export now succeeds even when zero visuals are generated (e.g., API outage). The deck renders with text-only slides instead of failing.
Stability fixes: Resolved an UnboundLocalError in video composition when visuals are missing, and the Import Project flow now rehydrates metadata.json from disk to restore UI state reliably.
Use the launcher: Always start the app via launch_gui.bat to ensure the virtual environment and dependencies load correctly. The script keeps the window open on errors so you can read them.
Imagen 4 safety settings: Vertex AI requires block_low_and_above safety thresholds. If you see 400 INVALID_ARGUMENT ... Only block_low_and_above is supported for safetySetting, update to the latest code and ensure your environment uses IMAGEN_MODEL=imagen-4.0-generate-001.
Models: Defaults are IMAGEN_MODEL=imagen-4.0-generate-001 and VEO_MODEL=veo-2.0-generate-001. Override in .env as needed.
Strict parameters for Imagen 4: Current client builds must omit explicit safety settings to avoid local validation errors. Use the bundled code and launch_gui.bat to run.
🎥 Vertex AI Setup (Required for Imagen 4 & Veo)
To use advanced models like Imagen 4 and Veo, you must configure Google Cloud:

Google Cloud Console: Go to your project, ensure Billing is enabled.

Enable APIs: Search for and enable the Vertex AI API.

Model Garden: Go to Vertex AI -> Model Garden, search for "Imagen" and "Veo", and click Enable/Agree.

Auth: Run gcloud auth application-default login on your machine.

Update .env:

GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001
Search for Veo and do the same.
Step 2: Update .env File
No new API key is needed. Use your existing Gemini API key, but add the model settings:

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
Visual Generator Modes
Mode	Description	Cost	Output
manim	Local Manim animations	Free	Mathematical/geometric animations
imagen	Google AI images only	~$0.04/image	Static educational images (network maps, diagrams)
imagen_manim ⭐	Imagen + Manim Recommended!	~$0.04/image	Best balance: AI images + local animations
veo	VEO video generation	~$0.75/sec	Up to 3 AI-generated video clips with fallback
hybrid 💎	Full combo: All modes	Variable	Maximum quality: images + animations + video clips
VEO Video Generation (NEW v2.6.1):

Generates up to 3 short video clips: intro, concept explanations, conclusion
Tries VEO API first, falls back to professional animated placeholders using moviepy
Animated gradient backgrounds with motion graphics
Configuration:

GEMINI_API_KEY=your-gemini-api-key
VISUAL_GENERATOR=imagen_manim  # manim | imagen | imagen_manim | veo | hybrid
IMAGE_COUNT=5  # Number of images to generate (1-20)
IMAGEN_MODEL=imagen-4.0-generate-001
VEO_MODEL=veo-2.0-generate-001
GUI Features:

Click "🎨 הגדרות ויזואליים" button to configure visual generation settings
🤖 AI Helper: Click to get AI assistance for enriching metadata with key concepts
Set image count: 1-20 images per project
Set video duration: automatic (follows audio) or manual
Cost calculator with accurate pricing for all modes
"🧹 נקה טעינה" button clears workspace without deleting history data
UI preferences (splitter sizes, right panel width, fonts, output mode) are stored in config/ui_config.json. Delete this file to reset layout to defaults.
Troubleshooting
Video not generated / command shows --skip-visuals: Ensure the output mode is set to Video + Audio (or Full Suite) and that the "צור וידאו/ויזואליזציות" checkbox is checked. Preferences are persisted in config/ui_config.json, so if visuals were disabled previously, re-enable them and rerun.
Custom Visual Metadata
For professional-grade custom visuals instead of generic AI generation, create a visual_metadata.json file alongside your metadata.json:

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
Benefits:

✅ 100% Custom Control: Specify exact prompts, styles, and colors
✅ Professional Quality: Consistent branding across all visuals
✅ Hebrew-Optimized: Full support for Hebrew content and aesthetics
✅ Cost Effective: Only generate what you actually need
Sample File: See data/sample_visual_metadata.json for a complete example based on Hebrew content.

Installation & Setup
git clone https://github.com/<org>/podcast-generator.git
cd podcast-generator

pip install -e .[dev]   # editable dev install
# or
pip install -e .
Copy .env.example → .env.
Populate Azure OpenAI + Speech keys, region, deployments, and optional intro/outro audio paths.
Validate FFmpeg availability: ffmpeg -version.
The Hebrew section below keeps the full step-by-step environment table if you prefer working in Hebrew.

Quickstart – CLI Pipeline
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals \
  --voice-profile classic \
  --material assets/labs/lab1.pdf \
  --url https://learn.microsoft.com/en-us/azure/architecture/ \
  --export-ppt
Flags of interest:

--dry-run – simulate without external API calls.
--skip-cache – force-regenerate dialogue even if cached.
--force – rebuild audio/video artifacts from scratch.
--output-dir custom_outputs – override default run directory.
M.B.S Studio GUI
Launch via launch_gui.bat (or launch_gui.ps1):

Pane	Description
Projects Hub (left)	Recent runs, timeline, and NotebookLM-style explorer cards with quick actions (Folder/Audio/Video/Story/Load).
Workspace (center)	Hero prompt, onboarding wizard, AI chat (Gemini/Azure), upload slots for supporting files/URLs, metadata editor, live story preview.
Control & Insights (right)	Transcript picker, output mode toggles, voice profile selector, run controls, gallery with per-artifact status, and a run-status banner that mirrors pipeline logs.
Enhanced Progress Tracking (v2.0)
The pipeline now displays visual progress with stage icons and ETA:

Stage	Icon	Description
Initialize	🚀	Pipeline startup
Dialogue	💬	AI dialogue generation
TTS	🎤	Voice synthesis
Audio	🎵	Audio stitching
Video	🎬	Video composition
Complete	✅	Pipeline finished
Progress includes:

Real-time elapsed time display
Estimated time remaining (ETA)
Header status bar for quick glances
Available Dialogs
Dialog	Purpose	Access
Onboarding Wizard	First-time user guidance with visual tips	Button in Workspace header
Cost Center	Budgets, charts, and live cost calculator	Header banner button
Appearance Settings	Font, color theme, chat background	Header banner button
Log Center	View, copy, and export pipeline logs	Header banner button
Backup & Restore	Save/load settings and history	💾 button in header
About	Version info and credits	ℹ️ button in header
Voice Selector	Browse ElevenLabs/Azure voices with preview	Voice profile dropdown
Network Map	Export Mermaid mindmap from metadata	Button in metadata card
Additional UX Features
Cost Center dialog centralizes calculators, budgets, and telemetry charts.
Log Center keeps the latest stdout stream, clipboard copy, and "save to file".
History hydration automatically restores chat + metadata when you load a run.
Onboarding Wizard guides first-time users through the workflow.
Backup & Restore persists .env, UI preferences, history, and GUI metadata.
TTS Provider Toggle allows runtime switching between Azure and ElevenLabs.
🎙️ Voice Lab (Instant Voice Cloning)
New tab next to Control Panel: "🎙️ Voice Lab".
Upload/record a clean 60s WAV/MP3 sample.
Click Clone with ElevenLabs → creates a custom voice_id via Instant Voice Cloning.
Saves profile "Custom" to config/voice_profiles.json (both speakers mapped to the cloned voice, model eleven_multilingual_v2).
Shows remaining ElevenLabs characters from v1/user/subscription so you can track quota.
Requires ELEVENLABS_API_KEY; without it the clone button is disabled.
New controls: Record/Stop/Preview/Reset; cloning stays disabled until a valid file exists to prevent crashes.
Costs, Telemetry & Logs
Monthly OpenAI/TTS budgets with progress bars.
Quick calculator (now inside Cost Center) estimates GPT/TTS/Video/PPT costs per run.
Every pipeline run appends processing_log.txt + history.json entry with costs, tokens, and artifact paths.
Project Layout
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
Troubleshooting
401 Unauthorized – verify Azure OpenAI endpoint/key pair in .env.
404 DeploymentNotFound – deployment name mismatch; copy the exact string from Azure Portal.
FFmpeg missing – install + add to PATH.
Encoding issues – ensure transcripts are UTF-8.
Audio desync – rerun with --force.
Video render fails with Hebrew paths – Fixed in v2.4.0! The system now uses temp directories with ASCII-only paths for FFMPEG.
Google API quota exceeded (429) – Your free tier quota is exhausted. Wait 15 seconds or upgrade to a paid plan.
Pipeline stalls during sleep – v2.4.0 includes heartbeat monitoring with automatic timeout detection.
Only 1 image generated – This usually happens when metadata lacks key_concepts. Chat with the AI to build richer metadata before running the pipeline. As of v2.6.0, the system will attempt to extract concepts from dialogue automatically.
"נטען" (Loaded) message but nothing loads – The folder may have been renamed or deleted. v2.6.0 auto-validates paths and removes invalid entries.
TTS Hebrew not working – Both Azure and ElevenLabs support Hebrew. For Azure, use he-IL-AvriNeural or he-IL-HilaNeural. For ElevenLabs, ensure you're using the eleven_multilingual_v2 model (default in profiles).
Startup crash: chat_background_path missing – remove config/ui_prefs.json (the GUI will recreate it) or delete the unknown key from the file. v3.1.4 ignores unknown UI keys safely.
Contributing & License
PRs are welcome (linters + pytest must pass). Licensed under MIT.

מדריך מפורט בעברית (המקור)
הקטעים הבאים נשמרו כפי שהופיעו במדריך המקורי כדי שתוכלו לעבוד בעברית מקצה לקצה.

Azure בפשטות – Educational Podcast Generator
מערכת אוטומטית להמרת הרצאות ארוכות (3 שעות) לפודקאסטים חינוכיים קצרים (8-10 דקות) בעברית, עם שני דוברים, אודיו איכותי, ואנימציות ויזואליות.

סקירה כללית
הפרויקט לוקח תמלול של הרצאה ארוכה בעברית וממיר אותו לפודקאסט חינוכי דמוי Google NotebookLM, עם:

דיאלוג טבעי בין שני דוברים (Roee - מומחה, Noa - סטודנטית)
קול עברי איכותי באמצעות Azure Speech Services (שני קולות נפרדים)
אנימציות Manim למושגים טכניים
וידאו סופי המשלב אודיו + אנימציות
ארכיטקטורה
המערכת מורכבת משלושה שלבים עיקריים:

1. יצירת דיאלוג (Dialogue Generation)
קלט: תמלול גולמי (~30,000 מילים) + מטא-דאטה (נושא, תאריך, מושגים מרכזיים)
עיבוד:
חלוקה חכמה של התמלול לחלקים (Token-aware chunking)
סיכום חלקים ארוכים באמצעות Azure OpenAI
יצירת דיאלוג JSON מובנה בין שני דוברים
פלט: dialogue.json עם מבנה מובנה של שיחה
2. המרה לקול (Text-to-Speech)
קלט: dialogue.json
עיבוד:
המרת כל משפט לקול עברי (SSML עם prosody)
Roee → he-IL-AvriNeural (קול גברי, בטוח)
Noa → he-IL-HilaNeural (קול נשי, סקרני)
הוספת 0.5 שניות שקטה בין דוברים
נורמליזציה של עוצמת הקול
פלט: קבצי WAV נפרדים לכל משפט + final_podcast.mp3 (128kbps, mono)
3. יצירת וידאו (אופציונלי)
קלט: dialogue.json + final_podcast.mp3
עיבוד:
זיהוי מושגים טכניים שצריכים ויזואליזציה (VM, Load Balancer, Storage, וכו')
יצירת קוד Manim לכל סצנה באמצעות Azure OpenAI
רינדור אנימציות (1080p, 30fps)
חיבור אודיו + אנימציות + intro/outro לוידאו אחד
פלט: final_video.mp4 (H.264, 1080p, 30fps)
התקנה
דרישות מוקדמות
Python 3.9+

FFmpeg - להתקנה ב-Windows:

choco install ffmpeg
או הורדה מ-ffmpeg.org והוספה ל-PATH

Azure Resources:

משאב Azure OpenAI (עם deployment של GPT-4o או GPT-4-turbo)
משאב Azure Speech Services
התקנת תלויות
# התקנה במצב editable (לפיתוח)
pip install -e .[dev]

# או התקנה רגילה
pip install -e .
הגדרת משתני סביבה
העתק את .env.example ל-.env:

cp .env.example .env
מלא את הערכים ב-.env:

Azure OpenAI (חובה):

AZURE_OPENAI_ENDPOINT=https://<resource-name>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key מהמשאב OpenAI>
AZURE_OPENAI_DEPLOYMENT=<שם הפריסה המדויק>
AZURE_OPENAI_API_VERSION=2024-02-01
Azure Speech Services (חובה):

AZURE_SPEECH_KEY=<key מהמשאב Speech>
AZURE_SPEECH_REGION=westeurope
AZURE_SPEECH_ENDPOINT=https://westeurope.api.cognitive.microsoft.com/
קבצי אודיו (אופציונלי):

INTRO_MUSIC=assets/audio/intro.mp3
OUTRO_MUSIC=assets/audio/outro.mp3
הגדרות נוספות:

OUTPUT_BASE_DIR=outputs
ENABLE_VISUALS=true
CACHE_DIALOGUES=true
VOICE_PROFILES_PATH=config/voice_profiles.json VOICE_PROFILES_DEFAULT=classic MONTHLY_TTS_CHARACTER_LIMIT=450000 MONTHLY_OPENAI_COST_LIMIT=180.0


**מחולל מטא-דאטה בסגנון NotebookLM (Gemini)**
```env
GEMINI_API_KEY=<מפתח מודל Gemini 1.5>
GEMINI_MODEL=gemini-1.5-flash
METADATA_SYSTEM_PROMPT=אתה NotebookLM Assistant שמייצר מטא-דאטה עשיר בהרכב עברית/אנגלית טבעי.
איך למצוא את הערכים ב-Azure Portal
Azure OpenAI:
פתח את משאב Azure OpenAI בפורטל
עבור ל-Keys and Endpoint
העתק:
Endpoint (מסתיים ב-.openai.azure.com/)
Key 1 או Key 2
עבור ל-Deployments והעתק את שם הפריסה המדויק
Azure Speech Services:
פתח את משאב Speech Services בפורטל
עבור ל-Keys and Endpoint
העתק:
Key 1 או Key 2
Location/Region (למשל: westeurope)
שימוש
פקודה בסיסית
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json
עם ויזואליזציה
python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals
בחירת פרופיל קולות + חומרים תומכים:

python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --include-visuals \
  --voice-profile energetic \
  --material assets/labs/lab1.pdf \
  --url https://learn.microsoft.com/en-us/azure/architecture/ \
  --export-ppt
דוגמאות נוספות
דרי-ראן (ללא קריאות API):

python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --dry-run
דילוג על cache:

python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --skip-cache
כוח (regenerate הכל):

python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --force
תיקיית פלט מותאמת:

python -m scripts.generate_podcast \
  data/sample_transcript.txt \
  data/sample_metadata.json \
  --output-dir custom_outputs
ממשק M.B.S Studio (GUI)
התקן תלויות והפעל launch_gui.bat (או launch_gui.ps1).
החלון החדש מחולק לשלושה אזורים:
Projects Hub (שמאל): כרטיסיות עם כל הריצות, כפתורי Open/Play/PPT, וסייר תוצרים עם חיפוש, טעינת פרויקט קיים או מחיקתו, ולוח זמנים ל-30 הימים האחרונים.
M.B.S Workspace (מרכז): צ'אט אינטראקטיבי עם Gemini/Azure, כפתורי-שבלונה (סכם שיעור, תכנן מצגת...), העלאת קבצים וקישורים, ומטא-דאטה שנבנה אוטומטית מתמלול בודד (כולל אזהרה כשזוהתה תערובת עברית/אנגלית).
Control & Insights (ימין): בחירת תמלול, בחירת תוצר, קולות, ביצוע pipeline, ועורך JSON מלא למטא-דאטה עם כפתורי שמירה/שחזור, Story חי וגלריית תוצרים.
לחצן “מרכז עלויות” בראש העמוד פותח דיאלוג ייעודי לניהול המגבלות, תרשימי הצריכה וסטטיסטיקות ה-30 הימים האחרונים.
לחצן “מרכז לוגים” מאפשר להעתיק/לשמור את הלוג הנוכחי, והמערכת שומרת אוטומטית קובץ לוג בתיקיית הפרויקט במקרה של תקלה.
לוג ריצה מובנה בתחתית מציג כל פקודה/שגיאה בזמן אמת.
כך אפשר לתכנן שיעור שלם “בסגנון NotebookLM” בלי להקליד JSON ידנית: מדברים עם הבינה, גוררים קבצים, מקבלים מטא-דאטה עשיר (כולל עריכה ידנית + Save/Revert) ומריצים את ה-Pipeline באותו חלון.

חוויית משתמש מחודשת
ברירת מחדל: בחירה בתמלול בלבד מפעילה מאחורי הקלעים ייצור מטא-דאטה בסיסי ושאלות המשך.
טקסטים בעברית מיושרים לימין באופן אוטומטי (צ'אט, מטא-דאטה, Story); טקסטים באנגלית נשארים משמאל.
גלריית הפרויקטים כוללת סייר תיקיות עם חיפוש, טעינת פרויקטים קיימים ומחיקה מלאה של תיקיות פלט, כולל סמלי סטטוס (🎧/🎬/📊/📖).
ניהול העלויות עבר ללחצן “מרכז עלויות” שמרכז מגבלות, תרשימים והתראות במקום כרטיסים עמוסים.
כרטיס “מחשבון עלויות” מחשב עלויות משוערות לפי מילים/דקות וסוגי התוצרים שתבחרו.
כרטיס המטא-דאטה כולל כפתור “מפת רשת” שמייצא Mermaid mindmap של מושגים, Labs והמלצות המשך.
כפתור “מרכז לוגים” מציג את הלוג האחרון ומאפשר להעתיקו או לשמור אותו תוך שמירת אוטומטית של תקלות בכל תיקיית פרויקט.
בורר מודלי Imagen חדש (4.0 רגיל/מהיר) וגם במצב טיוטה משתמש ב-visual_metadata אם קיים – בלי פלייסהולדר כחול.
Voice Lab עם כפתורי Record/Stop/Preview/Reset ושיכפול קולי זמין רק לאחר בחירת קובץ תקין.
מבנה קובץ מטא-דאטה
קובץ ה-JSON של המטא-דאטה צריך להכיל:

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
מבנה הפרויקט
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
קבצי פלט
לכל הרצאה נוצר תיקייה ב-outputs/ עם המבנה הבא:

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
העשרת מטא-דאטה (חומרים תומכים)
אפשר להעביר קבצים (--material או דרך ה-GUI) וקישורים (--url) שהמערכת תסכם באמצעות Azure OpenAI.
התוצרים נשמרים תחת metadata.json:
supporting_materials: מערך עם תקציר, Labs, References, Reading List לכל חומר.
מפתחות labs, references, reading_list מורחבים אוטומטית על בסיס הממצאים.
הקבצים עצמם מועתקים לתת-תיקייה materials/ בתוך תיקיית הריצה לצורך תיעוד.
עלויות
Free Tier
Speech TTS: 500,000 תווים בחודש (חינם)
OpenAI: $200 קרדיט בחודש הראשון
תעריפים עדכניים (נובמבר 2025)
שירות	מחיר קלט (ל-1K tokens)	מחיר פלט (ל-1K tokens)	מקור
Azure OpenAI GPT-4o	$0.005	$0.015	Azure OpenAI pricing
Google Gemini 1.5/2.5 Flash (Vertex AI)	$0.00035	$0.00105	Vertex AI pricing
Azure Neural TTS (Standard)	—	$16 / מיליון תווים	Azure Speech pricing
ElevenLabs (Multilingual v2)	—	$300 / מיליון תווים	ElevenLabs pricing
הערכים מסוכמים מהדף הרשמי של Microsoft ו-Google נכון לנובמבר 2025; בדקו שוב במדינות/מטבעות שונים.

נוסחה מהירה להערכת Pipeline
הערכת טוקנים: tokens ≈ #מילים × 1.3.
עלות GPT: Cost_GPT ≈ (tokens / 1000) × (0.005 לקלט + 0.015 לפלט) כשמייצרים אודיו+וידאו (הנחה: פלט ≈ 60% מהקלט).
הערכת תווי דיבור: speech_chars ≈ #מילים × 4.5.
עלות TTS: Cost_TTS ≈ (speech_chars / 1,000,000) × $16.
סה"כ = Cost_GPT + Cost_TTS (הוסף עוד 10% למנימל מתמטיקה/Manim).
דוגמה: הרצאה של ~12,000 מילים → ≈ 15,600 טוקנים קלט ו-9,000 פלט.
Cost_GPT ≈ (15.6 × 0.005) + (9 × 0.015) ≈ $0.26.
speech_chars ≈ 54,000 → Cost_TTS ≈ $0.86.
סה"כ ≈ $1.1 לפני רינדור וידאו.

עלות משוערת להרצאה אחת
Pipeline מלא (וידאו + PPTX + Story): ~$1.1 להרצאה של 3 שעות (ע"פ הדוגמה למעלה).
מצב Audio-only: ~$0.23 (GPT-4o ≈ $0.15 + Speech ≈ $0.08).
מחשבון עלויות ב-GUI
בכרטיס “מחשבון עלויות” (בפאנל הימני של M.B.S Studio) מזינים מספר מילים או דקות, בוחרים את ספק ה-AI (Azure GPT-4o או Gemini Flash) ומסמנים אילו תוצרים תרצו להפיק.
בלחיצה על “חשב עלות משוערת” מוצג פירוט העלויות (מודל, TTS, רינדור וידאו, PPTX) והסכום הכולל, בהתאם למחירי הסעיף הקודם.
תרחישי הכשל נשמרים בהעתק לוג בתיקיית הפרויקט, ואפשר להעתיק או לשמור את הלוג גם דרך כפתור “מרכז לוגים”.
פתרון בעיות
שגיאת 401 PermissionDenied
סיבה: מפתח API שגוי או endpoint לא נכון
פתרון: ודא ש-AZURE_OPENAI_ENDPOINT מסתיים ב-.openai.azure.com/ ושהמפתח תואם למשאב OpenAI

שגיאת 404 DeploymentNotFound
סיבה: שם הפריסה ב-.env לא תואם לפריסה ב-Azure
פתרון: פתח את משאב Azure OpenAI → Deployments → העתק את השם המדויק (כולל מקפים/אותיות גדולות)

שגיאת FFmpeg לא נמצא
סיבה: FFmpeg לא מותקן או לא ב-PATH
פתרון: התקן FFmpeg והוסף ל-PATH:

choco install ffmpeg
שגיאת encoding בעברית
סיבה: קובץ לא ב-UTF-8
פתרון: ודא שכל קבצי הטקסט (תמלול, מטא-דאטה) שמורים ב-UTF-8

אודיו לא מסונכרן
סיבה: קבצי segment לא נוצרו כראוי
פתרון: הרץ עם --force כדי ליצור מחדש את כל קבצי האודיו

תכונות מתקדמות
Caching
המערכת שומרת cache של דיאלוגים שנוצרו. אם תעבור על אותו תמלול שוב, היא תשתמש ב-cache (אלא אם תעבור עם --skip-cache).

Retry Logic
כל קריאת API כוללת retry אוטומטי (3 ניסיונות) עם exponential backoff.

Resume Support
אם ההרצה נכשלה באמצע, אפשר להריץ שוב והמערכת תמשיך מהנקודה שבה נעצרה.

בדיקות
# הרצת כל הבדיקות
pytest

# בדיקה ספציפית
pytest tests/test_chunker.py
לוגים
כל הרצה יוצרת processing_log.txt עם:

טיימינג של כל שלב
שימוש ב-tokens/characters
עלויות משוערות
אזהרות ושגיאות
רישיון
MIT

תמיכה
לשאלות או בעיות, פתח issue ב-repository.

הערה: הפרויקט מיועד להרצאות חינוכיות בעברית. תמיכה בשפות נוספות אפשרית בעתיד.

About
# M.B.S Studio – AI Lecture-to-Podcast Pipeline

Resources
 Readme
 Activity
Stars
 0 stars
Watchers
 0 watching
Forks
 0 forks
Releases
No releases published
Create a new release
Packages
No packages published
Publish your first package
Languages
Python
99.5%
 
Other
0.5%
Suggested workflows
Based on your tech stack
Publish Python Package logo
Publish Python Package
Publish a Python Package to PyPI on release.
Pylint logo
Pylint
Lint a Python application with pylint.
Python application logo
Python application
Create and test a Python application.
More workflows
Footer
