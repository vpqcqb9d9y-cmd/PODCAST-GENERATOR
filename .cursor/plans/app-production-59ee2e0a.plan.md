<!-- 59ee2e0a-12bb-48ec-ac92-f9b6e0a671fb 545610f1-510d-4f64-902f-85b9cf538ac5 -->
# תיקון הגדרות תצוגה וגיבוי - v2.1.0

## משימות

### 1. עדכון גרסה

- קובץ: `src/gui/constants.py`
- שנה `APP_VERSION = "2.0.0"` ל-`APP_VERSION = "2.1.0"`
- עדכן `APP_BUILD_DATE`

### 2. תיקון גיבוי - גודל 0

- קובץ: `src/gui/dialogs/backup.py`
- הבעיה: קובץ `config/ui_prefs.json` לא קיים אם המשתמש לא שינה הגדרות
- פתרון: הוסף גיבוי של קובץ `.env` ותיקיית `config/` כולה (אם קיימת)
- תקן את הצגת הגודל גם לקבצים קטנים (KB במקום MB)

### 3. הסרת אפשרות רקע מותאם

- קובץ: `src/gui/dialogs/appearance.py`
- הסר את `_build_background_row()`, `_build_alignment_row()`, `_build_mode_row()`
- הסר את כפתור "נקה רקע"
- הסר את `bg_edit`, `align_combo`, `bg_mode_combo`
- עדכן `selected_values()` להחזיר ערכים ריקים לרקע

- קובץ: `src/gui/app.py`
- פשט את `_apply_chat_preferences()` - הסר את כל הקוד שקשור לרקע תמונה
- הסר את הודעות ה-DEBUG

### 4. הסרת כפתור "התאם תצוגה" מהצ'אט

- קובץ: `src/gui/panels/workspace.py`
- הסר את השורות 199-202 (כפתור `chat_quick_settings_btn`)
- הגדרות התצוגה יהיו זמינות רק דרך הכפתור בראש החלון

### 5. ניקוי קוד

- הסר משתנים לא בשימוש מ-`_chat_theme_config()`
- הסר `chat_background_path`, `chat_background_alignment`, `chat_background_mode` מרשימת ההגדרות

## קבצים לשינוי

1. `src/gui/constants.py` - גרסה
2. `src/gui/dialogs/backup.py` - תיקון גיבוי
3. `src/gui/dialogs/appearance.py` - הסרת רקע
4. `src/gui/panels/workspace.py` - הסרת כפתור
5. `src/gui/app.py` - ניקוי קוד רקע

### To-dos

- [ ] Create constants.py with app constants and cost values
- [ ] Create constants.py with app constants and cost values
- [ ] Create workers.py with PipelineWorker, ChatWorker, MetadataSeedWorker
- [ ] Create widgets.py with SmoothScrollArea, ChatBubbleDelegate
- [ ] Create dialogs/ module with OnboardingWizard, ChatAppearanceDialog, CostCenterDialog, LogCenterDialog
- [ ] Create panels/ module with projects, workspace, summary panel builders
- [ ] Slim down app.py to use extracted modules
- [ ] Improve video creation progress indicators with icons and ETA
- [ ] Add comprehensive docstrings to all modules and functions
- [ ] Update README.md with quick start guide and visual wizard
- [ ] Verify all functionality works correctly after refactoring
- [ ] Create workers.py with PipelineWorker, ChatWorker, MetadataSeedWorker
- [ ] Create widgets.py with SmoothScrollArea, ChatBubbleDelegate
- [ ] Create dialogs/ module with OnboardingWizard, ChatAppearanceDialog, CostCenterDialog, LogCenterDialog
- [ ] Create panels/ module with projects, workspace, summary panel builders
- [ ] Slim down app.py to use extracted modules
- [ ] Improve video creation progress indicators with icons and ETA
- [ ] Add comprehensive docstrings to all modules and functions
- [ ] Update README.md with quick start guide and visual wizard
- [ ] Verify all functionality works correctly after refactoring
- [ ] Create constants.py with app constants and cost values
- [ ] Update README.he.md with new GUI module structure
- [ ] Create build_exe.bat for PyInstaller EXE generation
- [ ] Fix Projects panel spacing and cut-off issues
- [ ] Test all UI functions work correctly
- [ ] Create constants.py with app constants and cost values
- [ ] Improve video creation progress indicators with icons and ETA
- [ ] Add comprehensive docstrings to all modules and functions
- [ ] Update README.md with quick start guide and visual wizard
- [ ] Verify all functionality works correctly after refactoring
- [ ] Create workers.py with PipelineWorker, ChatWorker, MetadataSeedWorker
- [ ] Create widgets.py with SmoothScrollArea, ChatBubbleDelegate
- [ ] Create dialogs/ module with OnboardingWizard, ChatAppearanceDialog, CostCenterDialog, LogCenterDialog
- [ ] Create panels/ module with projects, workspace, summary panel builders
- [ ] Slim down app.py to use extracted modules
- [ ] Improve video creation progress indicators with icons and ETA
- [ ] Add comprehensive docstrings to all modules and functions
- [ ] Update README.md with quick start guide and visual wizard
- [ ] Verify all functionality works correctly after refactoring
- [ ] Update APP_VERSION to 2.1.0 in constants.py
- [ ] Fix backup to include .env and show KB for small files
- [ ] Remove background image options from appearance dialog
- [ ] Remove 'התאם תצוגה' button from chat toolbar
- [ ] Clean up background-related code from app.py