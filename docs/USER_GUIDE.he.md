# מדריך משתמש (עברית)

מדריך זה מסביר את הפאנלים, הכפתורים והפעולות המרכזיות ב‑M.B.S Studio.

## סקירת ממשק
- **Projects Hub (שמאל)**: דפדוף בריצות קודמות, פתיחת תיקיות, ניגון אודיו/וידאו, טעינת ריצה או מחיקת פלט. אייקוני סטטוס (🎧/🎬/📊/📖) מציינים אילו תוצרים קיימים.
- **Workspace (מרכז)**: צ'אט AI (Gemini/Azure), עורך מטא-דאטה, העלאת קבצים/קישורים, תצוגת Story. מתאים להכנת הדיאלוג והמטא-דאטה.
- **Control & Insights (ימין)**: בחירת תמלול, מצב פלט, בחירת פרופיל קולות, כפתורי Run/Preview, גלריה/סטטוס ולוג ריצה חי.
- **סרגל עליון**: Cost Center, Log Center, Appearance, Backup/Restore, About, מדדי רשת/CPU.

## כפתורים ופעולות עיקריות
- **Load transcript**: בחירת התמלול להרצה.
- **Output mode**: Video+Audio / Audio-only / Full suite (וידאו, PPT, Story).
- **Run / Preview**: הפעלת הצינור; Preview מקצר דיאלוג ומצמצם ויזואלים למהירות.
- **Voice profile**: בחירת קולות Azure/ElevenLabs לדוברים (Roee/Noa).
- **Include visuals**: הפעלת/כיבוי יצירת ויזואלים/וידאו; מכבד את מצב הגנרטור.
- **Generate visual metadata**: בנייה/ריענון של `visual_metadata.json` מתוך ה‑Story/מטא-דאטה.
- **Cost Center**: תקציבים, מחשבונים וגרפי שימוש.
- **Log Center**: לוג חי, העתקה/שמירה.
- **Backup/Restore**: גיבוי או שחזור הגדרות/היסטוריה/ממשק.

## ויזואליה וטיימליין
- **Visual generator**: `manim`, `imagen`, `imagen_manim`, `veo`, או `hybrid`.
- **Image count**: מספר התמונות המבוקש.
- **Auto video duration**: התאמת משך הווידאו לאורך האודיו (מומלץ).
- **טיימליין**: נכסי תמונה/וידאו לפי אינדקס; מתיחה בהתאם לאורך האודיו; כתוביות נצרבות ב‑FFmpeg, עם MoviePy כגיבוי.

## כתוביות (BiDi)
- הכתוביות משתמשות ב‑LRI/PDI לבידוד מקטעי אנגלית/מספרים וב‑RLM לעיגון סימני פיסוק בסוף משפט RTL, כדי לשמור על סדר חזותי נכון. שימוש ב‑`arabic-reshaper` + `python-bidi` כאשר זמינים.
- מחרוזת בדיקה: `שלום! ברוכים הבאים ל-Microsoft 365, זה עובד?`. ניתן לרנדר קליפ בדיקה ל‑`outputs/tests/rtl_bidi_test.mp4`.

## CLI קצר
```bash
python -m scripts.generate_podcast transcript.txt metadata.json --include-visuals --voice-profile classic
```
דגלים שימושיים:
- `--preview` או מצב Preview באפליקציה: ריצה קצרה ומהירה עם פחות ויזואלים.
- `--skip-visuals`: אודיו בלבד.
- `--force`: בנייה מחדש של כל התוצרים.
- `--output-dir PATH`: שינוי תיקיית הפלט.

## פתרון תקלות נפוצות
- **FFmpeg לא מותקן**: התקן והוסף ל‑PATH.
- **נתיבי עברית**: קומפוזיציית וידאו משתמשת בנתיבי tmp באנגלית כדי למנוע בעיות.
- **ויזואלים ריקים/שחורים**: בדוק `visual_metadata.json` ו‑Quality Report; רנדר מחדש עם תמונות אמיתיות או אפשר placeholders כשלא באדפטיבי.
- **כתוביות מתהפכות**: ודא שתלויות BiDi מותקנות; בלעדיהן בידוד/עיגון עדיין פועל.

למידע נוסף ורשומות גרסה, עיין ב‑`README.md`.

