"""
M.B.S Studio - Onboarding Wizard Dialog
========================================

Multi-step animated wizard to guide new users through
the core features and workflows of M.B.S Studio.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import APP_DISPLAY_NAME


class OnboardingWizard(QDialog):
    """
    Animated multi-step wizard to highlight core workflows.
    
    Guides users through the key features of M.B.S Studio with
    step-by-step instructions and visual feedback.
    
    Steps covered:
        1. Welcome and overview
        2. Metadata and AI chat features
        3. Pipeline execution
        4. Project explorer and cost center
        5. Logs, history, and recovery
    
    Example:
        >>> wizard = OnboardingWizard(parent=main_window)
        >>> wizard.exec()
    """

    WIZARD_STEPS = [
        {
            "icon": "🚀",
            "title": f"ברוך הבא ל-{APP_DISPLAY_NAME}",
            "body": "בחרו תמלול או טענו ריצה קודמת בכרטיסי Projects Hub כדי להדליק את האוטומציות בסגנון NotebookLM.",
        },
        {
            "icon": "🧠",
            "title": "מטא-דאטה חי ו-AI דו-לשוני",
            "body": "תמלול בודד מפעיל יצירת מטא-דאטה, שאלות המשך והשלמות אוטומטיות. הצ'אט מזהה מי מדבר: הודעות שלכם (טורקיז) ותשובות M.B.S (סגול).",
        },
        {
            "icon": "🎤",
            "title": "קולות TTS: Azure או ElevenLabs",
            "body": "שני הספקים תומכים בעברית! Azure (קולות AvriNeural/HilaNeural) מהיר ומשתלם. ElevenLabs (מודל multilingual_v2) טבעי יותר ומומלץ לפודקאסטים איכותיים. לחצו 'בחר קולות' ל-30+ אפשרויות.",
        },
        {
            "icon": "🎨",
            "title": "ויזואליים ותמונות AI",
            "body": "לתמונות מיטביות, ודאו שה-AI יוצר key_concepts במטא-דאטה לפני ההרצה. התמונות נוצרות על בסיס הנושא והמושגים. בהגדרות ויזואליים תוכלו לקבוע כמות תמונות.",
        },
        {
            "icon": "🎬",
            "title": "Pipeline מלא בלחיצה",
            "body": "הגדירו Output mode, קולות, וחומרים משלימים – ואז לחצו על 'הפעל Pipeline'. כרטיס הסטטוס מציג התקדמות חיה עם Progress Bar ו-ETA.",
        },
        {
            "icon": "📊",
            "title": "סייר תוצרים ומרכז עלויות",
            "body": "כרטיסי הסייר מאפשרים פתיחת תיקיות, אודיו, וידאו או Story בלחיצה. פרויקטים שנכשלו מסומנים ב-❌ ותיקיות חסרות ב-🚫.",
        },
        {
            "icon": "🧰",
            "title": "לוגים, שחזור והיסטוריה",
            "body": "לוג ההרצה נשמר אוטומטית, ו-Projects Hub זוכר מטא-דאטה, צ'אט וחומרים. ניתן למחוק את כל הפרויקטים בבטחה ('מחק הכל') תוך שמירת היסטוריית העלויות המצטברת.",
        },
    ]
    """Step definitions for the wizard."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the onboarding wizard dialog.
        
        Args:
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        """Configure window properties and styling."""
        self.setWindowTitle(f"אשף התחלה מהירה – {APP_DISPLAY_NAME}")
        self.setModal(True)
        self.resize(620, 420)
        self.setStyleSheet(self._get_stylesheet())

    def _get_stylesheet(self) -> str:
        """Return the wizard stylesheet."""
        return """
            QDialog {
                background-color: #02061a;
                color: #f8fafc;
            }
            QLabel#wizard-title {
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#wizard-body {
                color: #cbd5f5;
                font-size: 13px;
                line-height: 1.5em;
            }
            QFrame#HeroCard {
                border: 1px solid #1d4ed8;
                border-radius: 18px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #172554, stop:1 #312e81
                );
            }
            QPushButton#WizardCTA {
                background-color: #dc2626;
                color: #fff;
                font-weight: 600;
                border-radius: 10px;
                padding: 8px 18px;
            }
        """

    def _setup_ui(self) -> None:
        """Build the wizard UI components."""
        layout = QVBoxLayout(self)

        # Hero card
        hero = self._build_hero_card()
        layout.addWidget(hero)

        # Step pages
        self.stack = QStackedWidget()
        for step in self.WIZARD_STEPS:
            page = self._build_step_page(step)
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        # Progress indicators
        progress_row = self._build_progress_row()
        layout.addLayout(progress_row)

        # Navigation controls
        controls = self._build_controls()
        layout.addLayout(controls)

        self._update_buttons()

    def _build_hero_card(self) -> QFrame:
        """
        Build the hero card with welcome message.
        
        Returns:
            QFrame containing the hero card
        """
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        
        hero_title = QLabel("התחלה מהירה בתוך 3 דקות")
        hero_title.setObjectName("wizard-title")
        
        hero_sub = QLabel(
            "עשינו אוטומציה לכל השלבים – אתם רק בוחרים תמלול, מדברים עם הבינה ולוחצים Play."
        )
        hero_sub.setWordWrap(True)
        
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_sub)
        return hero

    def _build_step_page(self, step: dict) -> QWidget:
        """
        Build a single step page.
        
        Args:
            step: Step configuration dict with icon, title, body
            
        Returns:
            QWidget containing the step page
        """
        page = QWidget()
        page_layout = QVBoxLayout(page)
        
        icon = QLabel(step["icon"])
        icon.setAlignment(Qt.AlignmentFlag.AlignLeft)
        icon.setStyleSheet("font-size: 28px;")
        
        title = QLabel(step["title"])
        title.setObjectName("wizard-title")
        
        body = QLabel(step["body"])
        body.setObjectName("wizard-body")
        body.setWordWrap(True)
        
        page_layout.addWidget(icon)
        page_layout.addWidget(title)
        page_layout.addWidget(body)
        page_layout.addStretch(1)
        
        return page

    def _build_progress_row(self) -> QHBoxLayout:
        """
        Build the progress indicator row.
        
        Returns:
            QHBoxLayout with progress label and bar
        """
        progress_row = QHBoxLayout()
        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_label)
        progress_row.addWidget(self.progress_bar)
        return progress_row

    def _build_controls(self) -> QHBoxLayout:
        """
        Build the navigation control buttons.
        
        Returns:
            QHBoxLayout with navigation buttons
        """
        controls = QHBoxLayout()
        
        self.prev_btn = QPushButton("הקודם")
        self.prev_btn.clicked.connect(self._go_prev)
        
        self.next_btn = QPushButton("הבא")
        self.next_btn.clicked.connect(self._go_next)
        
        self.cta_btn = QPushButton("יאללה, נתחיל")
        self.cta_btn.setObjectName("WizardCTA")
        self.cta_btn.clicked.connect(self.accept)
        
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.cta_btn)
        
        return controls

    def _go_prev(self) -> None:
        """Navigate to the previous step."""
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._update_buttons()

    def _go_next(self) -> None:
        """Navigate to the next step or finish."""
        if self.stack.currentIndex() == self.stack.count() - 1:
            self.accept()
            return
        self.stack.setCurrentIndex(
            min(self.stack.count() - 1, self.stack.currentIndex() + 1)
        )
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Update button states based on current step."""
        total = self.stack.count()
        index = self.stack.currentIndex()
        
        self.prev_btn.setEnabled(index > 0)
        
        at_end = index == total - 1
        self.next_btn.setVisible(not at_end)
        self.cta_btn.setVisible(at_end)
        
        if not at_end:
            self.next_btn.setText("הבא")
        
        self.progress_label.setText(f"שלב {index + 1} מתוך {total}")
        percent = int(((index + 1) / total) * 100)
        self.progress_bar.setValue(percent)

