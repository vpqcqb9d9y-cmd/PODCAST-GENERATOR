![Logo](LOGO.JPEG)

# Azure Podcast Generator

Automated pipeline and PyQt6 desktop GUI that convert long-form lectures into concise, studio-grade podcasts and explainer videos. Includes Voice Lab for recording/cloning voices and CLI tools for scripted runs.

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

