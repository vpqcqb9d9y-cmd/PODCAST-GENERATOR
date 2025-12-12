![Logo](LOGO.JPEG)

# Azure Podcast Generator

צינור אוטומטי ו-GUI שולחני ב-PyQt6 שממירים הרצאות ארוכות לפודקאסטים ולסרטוני הסבר קצרים ברמת סטודיו. כולל Voice Lab להקלטה/שכפול קולות וכלי CLI להרצות מתוזמנות.

## Key Features
- ממשק PyQt6 עם פאנלי Projects, AI Workspace ו-Control.
- Voice Lab: הקלטה, תצוגה מקדימה ושכפול קולות דרך ElevenLabs.
- באנר ניטור מערכת (CPU/MEM/battery/network) עם תג חי.
- Pipeline קצה-לקצה: chunking, יצירת דיאלוג, TTS, stitching, ויז׳ואלס, יצוא PPT/Story.
- Cost center, Log center, דפדפן היסטוריה, גיבוי/שחזור.
- סקריפטי CLI להרצות pipeline ללא GUI ולבניית visual metadata.

## Installation
1. **Prerequisites**
   - Python 3.9+
   - FFmpeg ב-PATH
   - APIs אופציונליים: Azure OpenAI + Speech, ElevenLabs, Google Generative AI
2. **Set up**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e .
   # Dev: pip install -e .[dev]
   ```
3. **Configure secrets** (משתני סביבה או ‎.env)
   - `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`
   - `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`
   - אופציונלי: `ELEVENLABS_API_KEY`, `GOOGLE_API_KEY`

## Usage
- **Launch GUI**
  ```bash
  python run_gui.py
  ```
  או `launch_gui.bat` / `launch_gui.ps1`.

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
├── config/                  # העדפות UI ופרופילי קול
├── data/                    # תמלול/מטא-דאטה לדוגמה
├── outputs/                 # ריצות שנוצרו, היסטוריה, גיבויים
├── scripts/                 # כלי CLI (generate_podcast, create_visual_metadata, tests)
├── src/
│   ├── gui/                 # אפליקציית PyQt6
│   │   ├── app.py           # PodcastGeneratorWindow + main()
│   │   ├── controllers/     # SystemMonitorController, VoiceLabController
│   │   ├── workers.py       # PipelineWorker, ChatWorker, RecordingWorker, וכו׳
│   │   ├── panels/          # Projects, Workspace, Control/Summary builders
│   │   ├── dialogs/         # About, Backup, Cost/Log centers, Voice selector
│   │   ├── widgets.py       # רכיבי גלילה/צ׳אט מותאמים
│   │   └── constants.py     # שמות תצוגה, שלבים, ערכות נושא
│   ├── audio/               # TTS ו-stitching
│   ├── dialogue/            # chunking + יצירת דיאלוג
│   ├── visuals/             # קומפוזיציית Manim/וידאו ו-Google AI visuals
│   ├── metadata/            # סשן צ׳אט ובניית מטא-דאטה
│   ├── pipeline/            # orchestration ל-CLI/runner
│   └── utils/               # Settings, logging, storage, costs, helpers
├── tests/                   # חבילת Pytest
├── pyproject.toml           # מטא-דאטה ותלויות
├── README.md                # מדריך באנגלית
└── README.he.md             # מדריך בעברית
```

### Responsibilities
- `run_gui.py` / `gui.main`: השקת ממשק שולחני.
- `scripts/generate_podcast.py`: כניסת pipeline ללא GUI.
- `scripts/create_visual_metadata.py`: בנייה/אימות של visual metadata.
- `src/gui/controllers/`: לוגיקת GUI מבודדת (System Monitor, Voice Lab).
- `src/gui/workers.py`: עובדי QThread/QObject לפייפליין/צ׳אט/הקלטה.
- `src/gui/panels/`: בוני UI לפרויקטים, אזור עבודה וטאבי שליטה.
- `src/audio/`: סינתזת TTS ותפירת אודיו.
- `src/dialogue/`: chunking ויצירת דיאלוג.
- `src/visuals/`: מטא-דאטה ויזואלית, קומפוזיציית Manim/וידאו, Google AI visuals.
- `src/utils/`: הגדרות, לוגים, אחסון, חישובי עלות, עזרי מערכת.
- `config/`: העדפות משתמש ופרופילי קול.
- `outputs/`: תוצרי ריצות, לוגים, גיבויים והיסטוריה.

## Notes & Tips
- ודאו ש-FFmpeg מותקן וזמין ב-PATH לשלבי וידאו/אודיו.
- שכפול ב-Voice Lab דורש `ELEVENLABS_API_KEY`; בלעדיו כפתור השכפול יישאר מושבת.
- מפתחות Azure ו-Google מפעילים את ספקי ה-AI המתאימים; האפליקציה פועלת במצב מופחת אם הם חסרים.

