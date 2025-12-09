"""
M.B.S Studio - Visual Settings Dialog
======================================

Dialog for configuring visual generation settings including
visual generator backend, Imagen model, and VEO model selection.

Author: M.B.S Studio
Version: 1.1.0
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Callable, Dict, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QScreen

from src.utils import Settings
from ..constants import VISUAL_GENERATORS, IMAGEN_MODELS, VEO_MODELS

# Module logger
_logger = logging.getLogger(__name__)


class VisualSettingsDialog(QDialog):
    """
    Dialog for configuring visual generation settings.
    
    Allows users to customize:
        - Visual generator backend (Manim, Google AI, Hybrid)
        - Imagen 4 model selection
        - VEO model selection
    
    Signals:
        ai_helper_requested: Emitted when user clicks "Continue to Chat" button
    
    Args:
        settings: Application settings object
        parent: Parent widget (optional)
    
    Example:
        >>> dialog = VisualSettingsDialog(settings=app_settings, parent=main_window)
        >>> dialog.ai_helper_requested.connect(on_ai_helper_requested)
        >>> if dialog.exec() == QDialog.DialogCode.Accepted:
        ...     values = dialog.selected_values()
        ...     settings.save_ui_preferences(values)
    """
    
    # Signal emitted when AI helper is requested - provides direct callback mechanism
    ai_helper_requested = pyqtSignal()

    def __init__(
        self,
        settings: Settings,
        parent: Optional[QWidget] = None,
        ai_helper_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize the visual settings dialog.
        
        Args:
            settings: Current application settings
            parent: Parent widget
            ai_helper_callback: Optional callback to trigger AI helper directly
        """
        super().__init__(parent)
        self.settings = settings
        self._ai_helper_callback = ai_helper_callback
        self._init_time = time.time()
        self._accepted_values: Optional[Dict[str, object]] = None
        self._auto_saved = False
        
        _logger.info("[VisualSettingsDialog] Initializing dialog (parent=%s)", 
                     type(parent).__name__ if parent else "None")
        
        self._setup_window()
        self._setup_ui()
        self._update_google_ai_visibility()
        
        _logger.debug("[VisualSettingsDialog] Dialog initialized in %.3fs", 
                      time.time() - self._init_time)

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("הגדרות ויזואליים")
        
        # Restore saved geometry if available
        try:
            saved_geo = getattr(self.settings, 'visual_settings_geometry', None)
            if saved_geo:
                self.restoreGeometry(bytes.fromhex(saved_geo))
            else:
                self.setMinimumWidth(450)
                self.setMinimumHeight(350)
                self.resize(500, 550)
        except Exception:
            self.setMinimumWidth(450)
            self.setMinimumHeight(350)
            self.resize(500, 550)
            
        self.setSizeGripEnabled(True)

    def accept(self) -> None:
        """Persist the selected values immediately when OK is clicked."""
        _logger.info("[VisualSettingsDialog.accept] Accept called - closing dialog")
        
        try:
            values = self.selected_values()
            self._accepted_values = values
            self.settings.save_ui_preferences(values)
            self._auto_saved = True
            _logger.info(
                "[VisualSettingsDialog.accept] Saved visual settings (image_count=%s, generator=%s)",
                values.get("image_count"),
                values.get("visual_generator"),
            )
        except Exception as e:
            self._auto_saved = False
            _logger.error("[VisualSettingsDialog.accept] Failed to save settings: %s", e)
        
        # Always call parent accept to close
        _logger.debug("[VisualSettingsDialog.accept] Calling super().accept()")
        super().accept()
        _logger.info("[VisualSettingsDialog.accept] Dialog accepted and closed")
    
    def closeEvent(self, event) -> None:
        """Save window geometry on close."""
        geo = bytes(self.saveGeometry().toHex()).decode("ascii")
        # Save to settings (in-memory)
        setattr(self.settings, 'visual_settings_geometry', geo)
        
        # Persist to disk immediately
        try:
            self.settings.save_ui_preferences({"visual_settings_geometry": geo})
        except Exception as e:
            print(f"Error saving visual settings geometry: {e}")
            
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        """Build the dialog UI components with scroll area."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        # Content widget inside scroll area
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title = QLabel("🎨 הגדרות יצירת ויזואליים")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "בחר את מנוע יצירת הויזואליים ואת המודלים לשימוש.\n"
            "Google AI דורש מפתח Gemini API פעיל."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(desc)

        # Visual Generator Group
        generator_group = QGroupBox("מנוע יצירת ויזואליים")
        generator_layout = QFormLayout(generator_group)
        
        self.generator_combo = QComboBox()
        for key, gen_data in VISUAL_GENERATORS.items():
            self.generator_combo.addItem(gen_data["name"], key)
        
        current_generator = getattr(self.settings, 'visual_generator', 'manim')
        gen_index = max(0, self.generator_combo.findData(current_generator))
        self.generator_combo.setCurrentIndex(gen_index)
        self.generator_combo.currentIndexChanged.connect(self._update_google_ai_visibility)
        
        generator_layout.addRow("מנוע:", self.generator_combo)
        
        # Description label for selected generator
        self.generator_desc = QLabel()
        self.generator_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        self.generator_desc.setWordWrap(True)
        generator_layout.addRow("", self.generator_desc)
        
        # Cost warning label for VEO/Hybrid modes
        self.veo_warning = QLabel(
            "💰 הערה: VEO יקר יותר (~$0.75 לשנייה של וידאו).\n"
            "בחירה זו תיצור עד 3 קליפים קצרים.\n"
            "אם VEO לא זמין, יווצרו וידאו placeholder עם אנימציות."
        )
        self.veo_warning.setStyleSheet(
            "color: #f59e0b; background: rgba(245, 158, 11, 0.1); "
            "padding: 8px; border-radius: 6px;"
        )
        self.veo_warning.setWordWrap(True)
        self.veo_warning.setVisible(False)
        generator_layout.addRow("", self.veo_warning)
        
        layout.addWidget(generator_group)

        # Google AI Models Group
        self.google_ai_group = QGroupBox("מודלי Google AI")
        google_layout = QFormLayout(self.google_ai_group)
        
        # Imagen Model Selection
        self.imagen_combo = QComboBox()
        for key, model_data in IMAGEN_MODELS.items():
            cost_str = f"${model_data['cost_per_image']:.2f}/תמונה"
            self.imagen_combo.addItem(f"{model_data['name']} ({cost_str})", key)
        
        current_imagen = getattr(self.settings, 'imagen_model', 'imagen-4.0-generate-001')
        imagen_index = max(0, self.imagen_combo.findData(current_imagen))
        self.imagen_combo.setCurrentIndex(imagen_index)
        
        google_layout.addRow("מודל Imagen 4:", self.imagen_combo)
        
        # Imagen description
        self.imagen_desc = QLabel()
        self.imagen_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        google_layout.addRow("", self.imagen_desc)
        self.imagen_combo.currentIndexChanged.connect(self._update_imagen_description)
        
        # VEO Model Selection
        self.veo_combo = QComboBox()
        for key, model_data in VEO_MODELS.items():
            cost_str = f"${model_data['cost_per_second']:.2f}/שנייה"
            self.veo_combo.addItem(f"{model_data['name']} ({cost_str})", key)
        
        current_veo = getattr(self.settings, 'veo_model', 'veo-2.0-generate-001')
        veo_index = max(0, self.veo_combo.findData(current_veo))
        self.veo_combo.setCurrentIndex(veo_index)
        
        google_layout.addRow("מודל VEO:", self.veo_combo)
        
        # VEO description
        self.veo_desc = QLabel()
        self.veo_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        google_layout.addRow("", self.veo_desc)
        self.veo_combo.currentIndexChanged.connect(self._update_veo_description)
        
        # Image count setting with enhanced controls
        image_count_row = QHBoxLayout()
        
        # Minus button
        self.image_minus_btn = QPushButton("−")
        self.image_minus_btn.setFixedSize(36, 36)
        self.image_minus_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 2px solid #475569;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #475569;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background: #1e293b;
            }
        """)
        self.image_minus_btn.clicked.connect(lambda: self.image_count_spin.setValue(
            max(1, self.image_count_spin.value() - 1)))
        image_count_row.addWidget(self.image_minus_btn)
        
        # Spinbox with enhanced styling
        self.image_count_spin = QSpinBox()
        self.image_count_spin.setRange(1, 20)
        initial_count = getattr(self.settings, 'image_count', 5)
        try:
            initial_count = int(initial_count)
        except (TypeError, ValueError):
            initial_count = 5
        initial_count = max(1, min(20, initial_count))
        self.image_count_spin.setValue(initial_count)
        _logger.debug("[VisualSettingsDialog] Loaded image_count=%s into spinbox", initial_count)
        self.image_count_spin.setSuffix(" תמונות")
        self.image_count_spin.setToolTip("מספר התמונות שיווצרו לכל פרויקט (1-20)")
        self.image_count_spin.setStyleSheet("""
            QSpinBox {
                padding: 8px 12px;
                background: #1e293b;
                border: 2px solid #475569;
                border-radius: 8px;
                color: #e2e8f0;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
            }
            QSpinBox:hover {
                border-color: #60a5fa;
            }
            QSpinBox:focus {
                border-color: #3b82f6;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 28px;
                border-left: 2px solid #475569;
                border-bottom: 1px solid #475569;
                border-top-right-radius: 6px;
                background: #334155;
            }
            QSpinBox::up-button:hover {
                background: #475569;
            }
            QSpinBox::up-arrow {
                width: 12px;
                height: 12px;
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-bottom: 8px solid #60a5fa;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 28px;
                border-left: 2px solid #475569;
                border-top: 1px solid #475569;
                border-bottom-right-radius: 6px;
                background: #334155;
            }
            QSpinBox::down-button:hover {
                background: #475569;
            }
            QSpinBox::down-arrow {
                width: 12px;
                height: 12px;
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #60a5fa;
            }
        """)
        image_count_row.addWidget(self.image_count_spin)
        
        # Plus button
        self.image_plus_btn = QPushButton("+")
        self.image_plus_btn.setFixedSize(36, 36)
        self.image_plus_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 2px solid #475569;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #475569;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background: #1e293b;
            }
        """)
        self.image_plus_btn.clicked.connect(lambda: self.image_count_spin.setValue(
            min(20, self.image_count_spin.value() + 1)))
        image_count_row.addWidget(self.image_plus_btn)
        
        image_count_row.addStretch()
        google_layout.addRow("כמות תמונות:", image_count_row)
        
        image_count_desc = QLabel(
            "מספר התמונות הלימודיות שיווצרו (מפות, דיאגרמות, איורים).\n"
            "💡 טיפ: לתוצאות מיטביות, הגדר key_concepts במטא-דאטה לפני הרצה."
        )
        image_count_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        image_count_desc.setWordWrap(True)
        google_layout.addRow("", image_count_desc)
        
        layout.addWidget(self.google_ai_group)
        
        # AI Helper Section - Always visible (outside google_ai_group)
        ai_group = QGroupBox("🤖 עזרת AI")
        ai_layout = QVBoxLayout(ai_group)
        
        ai_desc = QLabel(
            "השתמש ב-AI כדי להעשיר את המטא-דאטה עם מושגים מרכזיים,\n"
            "תיאורים ויזואליים ורעיונות לתמונות."
        )
        ai_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        ai_desc.setWordWrap(True)
        ai_layout.addWidget(ai_desc)
        
        self.ai_helper_btn = QPushButton("🤖 פתח שיחת AI להעשרת מטא-דאטה")
        self.ai_helper_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #8b5cf6, stop:1 #6366f1);
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #7c3aed, stop:1 #4f46e5);
            }
        """)
        self.ai_helper_btn.setToolTip(
            "לחץ כדי לפתוח שיחת AI שתעזור לך להוסיף:\n"
            "• מושגים מרכזיים (key_concepts)\n"
            "• תיאורים לויזואליזציה\n"
            "• שאלות להעשרת התוכן"
        )
        self.ai_helper_btn.clicked.connect(self._open_ai_helper)
        ai_layout.addWidget(self.ai_helper_btn)
        
        self.ai_request_sent = False  # Track if we should trigger AI on close
        
        layout.addWidget(ai_group)

        # Video Duration Settings
        duration_group = QGroupBox("הגדרות משך וידאו")
        duration_layout = QFormLayout(duration_group)
        
        # Duration explanation banner
        duration_info = QLabel(
            "ℹ️ איך זה עובד?\n"
            "• משך אוטומטי: הוידאו הסופי יהיה באורך האודיו של הפודקאסט\n"
            "• משך ידני: משפיע רק על אורך קליפי VEO שנוצרים ע\"י AI"
        )
        duration_info.setStyleSheet("""
            color: #94a3b8; 
            font-size: 11px; 
            background: rgba(56, 189, 248, 0.1);
            padding: 8px;
            border-radius: 6px;
            border-left: 3px solid #38bdf8;
        """)
        duration_info.setWordWrap(True)
        duration_layout.addRow(duration_info)
        
        # Auto duration checkbox with clear styling
        auto_row = QHBoxLayout()
        self.auto_duration_cb = QCheckBox("✅ משך אוטומטי (לפי האודיו)")
        self.auto_duration_cb.setChecked(getattr(self.settings, 'auto_video_duration', True))
        self.auto_duration_cb.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
                background: rgba(56, 189, 248, 0.15);
                border-radius: 6px;
            }
            QCheckBox:checked {
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.25);
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:checked {
                background: #38bdf8;
                border: 2px solid #38bdf8;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked {
                background: #1e293b;
                border: 2px solid #475569;
                border-radius: 4px;
            }
        """)
        self.auto_duration_cb.stateChanged.connect(self._update_duration_visibility)
        auto_row.addWidget(self.auto_duration_cb)
        auto_row.addStretch(1)
        
        # Auto mode description
        self.auto_desc = QLabel("מומלץ - הוידאו יהיה באורך האודיו")
        self.auto_desc.setStyleSheet("color: #22c55e; font-size: 11px; font-style: italic;")
        auto_row.addWidget(self.auto_desc)
        
        duration_layout.addRow(auto_row)
        
        # Manual duration input with enhanced styling
        duration_row = QHBoxLayout()
        
        # Minus button for duration
        self.duration_minus_btn = QPushButton("−")
        self.duration_minus_btn.setFixedSize(32, 32)
        self.duration_minus_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 2px solid #475569;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover { background: #475569; border-color: #60a5fa; }
            QPushButton:disabled { background: #1e293b; color: #475569; }
        """)
        self.duration_minus_btn.clicked.connect(lambda: self.duration_spin.setValue(
            max(10, self.duration_spin.value() - 10)))
        duration_row.addWidget(self.duration_minus_btn)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(10, 3600)  # 10 seconds to 1 hour
        self.duration_spin.setSuffix(" שניות")
        self.duration_spin.setValue(getattr(self.settings, 'video_duration_seconds', 300))
        self.duration_spin.setSingleStep(10)
        self.duration_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px 12px;
                background: #1e293b;
                border: 2px solid #475569;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 13px;
                font-weight: bold;
                min-width: 100px;
            }
            QDoubleSpinBox:hover { border-color: #60a5fa; }
            QDoubleSpinBox:disabled { background: #0f172a; color: #64748b; }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 24px;
                background: #334155;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background: #475569;
            }
        """)
        duration_row.addWidget(self.duration_spin)
        
        # Plus button for duration
        self.duration_plus_btn = QPushButton("+")
        self.duration_plus_btn.setFixedSize(32, 32)
        self.duration_plus_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 2px solid #475569;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover { background: #475569; border-color: #60a5fa; }
            QPushButton:disabled { background: #1e293b; color: #475569; }
        """)
        self.duration_plus_btn.clicked.connect(lambda: self.duration_spin.setValue(
            min(3600, self.duration_spin.value() + 10)))
        duration_row.addWidget(self.duration_plus_btn)
        
        self.duration_label = QLabel("(~5 דקות)")
        self.duration_label.setStyleSheet("color: #94a3b8; font-size: 12px; margin-left: 8px;")
        duration_row.addWidget(self.duration_label)
        duration_row.addStretch(1)
        
        duration_layout.addRow("משך ידני:", duration_row)
        self.duration_spin.valueChanged.connect(self._update_duration_label)
        
        # VEO clips explanation
        veo_note = QLabel(
            "💡 הערה: המשך הידני קובע את אורך כל קליפ VEO שנוצר.\n"
            "   אורך הוידאו הסופי תמיד מותאם לאורך האודיו."
        )
        veo_note.setStyleSheet("color: #f59e0b; font-size: 10px; font-style: italic;")
        veo_note.setWordWrap(True)
        duration_layout.addRow("", veo_note)
        
        layout.addWidget(duration_group)
        self._update_duration_visibility()

        # Cost estimate section
        cost_group = QGroupBox("הערכת עלויות")
        cost_layout = QVBoxLayout(cost_group)
        
        self.cost_label = QLabel()
        self.cost_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.cost_label.setWordWrap(True)
        cost_layout.addWidget(self.cost_label)
        
        layout.addWidget(cost_group)
        
        # Add stretch to push content up
        layout.addStretch(1)
        
        # Set content widget in scroll area
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # Dialog buttons (outside scroll area)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        # Connect buttons with logging
        def on_ok_clicked():
            _logger.info("[VisualSettingsDialog] OK button clicked")
            self.accept()
            
        def on_cancel_clicked():
            _logger.info("[VisualSettingsDialog] Cancel button clicked")
            self.reject()
        
        buttons.accepted.connect(on_ok_clicked)
        buttons.rejected.connect(on_cancel_clicked)
        buttons.setStyleSheet("""
            QDialogButtonBox {
                padding: 8px;
            }
            QPushButton {
                min-width: 80px;
                min-height: 32px;
                padding: 6px 16px;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(buttons)
        
        _logger.debug("[VisualSettingsDialog] Dialog buttons configured")
        
        # Initialize descriptions
        self._update_generator_description()
        self._update_imagen_description()
        self._update_veo_description()
        self._update_cost_estimate()

    def _update_google_ai_visibility(self) -> None:
        """Show/hide Google AI settings based on selected generator."""
        generator = self.generator_combo.currentData() or "manim"
        # Show Google AI settings for imagen, imagen_manim, veo, or hybrid modes
        show_google = generator in ("imagen", "imagen_manim", "veo", "hybrid")
        self.google_ai_group.setVisible(show_google)
        
        # Show VEO warning for veo or hybrid modes (not implemented)
        show_veo_warning = generator in ("veo", "hybrid")
        if hasattr(self, "veo_warning"):
            self.veo_warning.setVisible(show_veo_warning)
        
        self._update_generator_description()
        self._update_cost_estimate()
    
    def _open_ai_helper(self) -> None:
        """
        Open AI helper dialog for metadata enrichment.
        
        Shows a confirmation dialog and if user confirms:
        1. Sets ai_request_sent flag
        2. Emits ai_helper_requested signal
        3. Calls callback if provided
        4. Closes dialog with Accepted result
        """
        from PyQt6.QtWidgets import QMessageBox
        
        start_time = time.time()
        _logger.info("[VisualSettingsDialog._open_ai_helper] Opening AI helper confirmation dialog")
        
        try:
            # Show guidance and set flag for parent to trigger AI
            msg = QMessageBox(self)
            msg.setWindowTitle("🤖 עזרת AI לתמונות מיטביות")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                "כדי ליצור תמונות איכותיות, ה-AI צריך מידע על התוכן שלך.\n\n"
                "לחץ 'המשך' וה-AI ישאל אותך שאלות כדי להעשיר את המטא-דאטה עם:\n"
                "• מושגים מרכזיים (key_concepts) - חיוני לתמונות!\n"
                "• תיאורים ויזואליים\n"
                "• קשרים בין מושגים\n\n"
                "לאחר מכן, הפעל שוב את ה-Pipeline ליצירת תמונות מותאמות."
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            msg.button(QMessageBox.StandardButton.Ok).setText("המשך לצ'אט")
            msg.button(QMessageBox.StandardButton.Cancel).setText("ביטול")
            
            result = msg.exec()
            
            _logger.debug("[VisualSettingsDialog._open_ai_helper] Dialog result: %s (Ok=%s)", 
                         result, QMessageBox.StandardButton.Ok)
            
            if result == QMessageBox.StandardButton.Ok:
                _logger.info("[VisualSettingsDialog._open_ai_helper] User confirmed - triggering AI helper")
                
                # Set the flag BEFORE any other operations
                self.ai_request_sent = True
                _logger.debug("[VisualSettingsDialog._open_ai_helper] ai_request_sent set to True")
                
                # Show visual feedback
                self.ai_helper_btn.setText("⏳ מעביר לצ'אט...")
                self.ai_helper_btn.setEnabled(False)
                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()
                
                # Emit signal for direct connection (most reliable method)
                try:
                    self.ai_helper_requested.emit()
                    _logger.debug("[VisualSettingsDialog._open_ai_helper] ai_helper_requested signal emitted")
                except Exception as e:
                    _logger.error("[VisualSettingsDialog._open_ai_helper] Failed to emit signal: %s", e)
                
                # Call callback if provided (backup method)
                if self._ai_helper_callback:
                    try:
                        _logger.debug("[VisualSettingsDialog._open_ai_helper] Calling direct callback")
                        self._ai_helper_callback()
                    except Exception as e:
                        _logger.error("[VisualSettingsDialog._open_ai_helper] Callback failed: %s\n%s", 
                                     e, traceback.format_exc())
                
                # Close the main dialog and signal parent to trigger AI
                _logger.info("[VisualSettingsDialog._open_ai_helper] Closing dialog to continue to chat...")
                self.accept()
                
            else:
                _logger.info("[VisualSettingsDialog._open_ai_helper] User cancelled AI helper")
                self.ai_request_sent = False
                
        except Exception as e:
            _logger.error("[VisualSettingsDialog._open_ai_helper] Error in AI helper: %s\n%s", 
                         e, traceback.format_exc())
            self.ai_request_sent = False
            
        finally:
            elapsed = time.time() - start_time
            _logger.debug("[VisualSettingsDialog._open_ai_helper] Completed in %.3fs", elapsed)
    
    def should_trigger_ai_helper(self) -> bool:
        """
        Check if AI helper was requested.
        
        Returns:
            True if user clicked "Continue to Chat", False otherwise
        """
        result = getattr(self, "ai_request_sent", False)
        _logger.debug("[VisualSettingsDialog.should_trigger_ai_helper] Returning %s", result)
        return result

    def _update_generator_description(self) -> None:
        """Update the generator description label."""
        generator = self.generator_combo.currentData() or "manim"
        gen_data = VISUAL_GENERATORS.get(generator, {})
        self.generator_desc.setText(gen_data.get("description", ""))

    def _update_imagen_description(self) -> None:
        """Update the Imagen model description label."""
        model_key = self.imagen_combo.currentData() or "imagen-4.0-generate-001"
        model_data = IMAGEN_MODELS.get(model_key, {})
        self.imagen_desc.setText(model_data.get("description", ""))
        self._update_cost_estimate()

    def _update_veo_description(self) -> None:
        """Update the VEO model description label."""
        model_key = self.veo_combo.currentData() or "veo-2.0-generate-001"
        model_data = VEO_MODELS.get(model_key, {})
        self.veo_desc.setText(model_data.get("description", ""))
        self._update_cost_estimate()

    def _update_cost_estimate(self) -> None:
        """Update the cost estimate label."""
        generator = self.generator_combo.currentData() or "manim"
        
        if generator == "manim":
            self.cost_label.setText(
                "Manim הוא חינמי לשימוש (רינדור מקומי).\n"
                "עלות וידאו: רק עלות עיבוד מקומי."
            )
        else:
            imagen_key = self.imagen_combo.currentData() or "imagen-4.0-generate-001"
            veo_key = self.veo_combo.currentData() or "veo-2.0-generate-001"
            
            imagen_cost = IMAGEN_MODELS.get(imagen_key, {}).get("cost_per_image", 0.04)
            veo_cost = VEO_MODELS.get(veo_key, {}).get("cost_per_second", 0.75)
            
            estimate_images = 5  # Typical number of images per podcast
            estimate_video_seconds = 10  # Typical video clip length
            
            total_imagen = imagen_cost * estimate_images
            total_veo = veo_cost * estimate_video_seconds
            
            self.cost_label.setText(
                f"הערכת עלות לפודקאסט אחד:\n"
                f"• Imagen ({estimate_images} תמונות): ${total_imagen:.2f}\n"
                f"• VEO ({estimate_video_seconds} שניות וידאו): ${total_veo:.2f}\n"
                f"• סה\"כ משוער: ${total_imagen + total_veo:.2f}"
            )

    def _update_duration_visibility(self) -> None:
        """Show/hide manual duration based on auto checkbox."""
        auto = self.auto_duration_cb.isChecked()
        self.duration_spin.setEnabled(not auto)
        
        # Also enable/disable the +/- buttons
        if hasattr(self, 'duration_minus_btn'):
            self.duration_minus_btn.setEnabled(not auto)
        if hasattr(self, 'duration_plus_btn'):
            self.duration_plus_btn.setEnabled(not auto)
        
        # Update checkbox text to show state clearly
        if auto:
            self.auto_duration_cb.setText("✅ משך אוטומטי (לפי האודיו)")
            self.duration_label.setText("(אוטומטי)")
            if hasattr(self, 'auto_desc'):
                self.auto_desc.setText("מומלץ - הוידאו יהיה באורך האודיו")
                self.auto_desc.setStyleSheet("color: #22c55e; font-size: 11px; font-style: italic;")
        else:
            self.auto_duration_cb.setText("⬜ משך אוטומטי (לפי האודיו)")
            self._update_duration_label()
            if hasattr(self, 'auto_desc'):
                self.auto_desc.setText("משך ידני - הגדר משך קבוע")
                self.auto_desc.setStyleSheet("color: #f59e0b; font-size: 11px; font-style: italic;")

    def _update_duration_label(self) -> None:
        """Update the duration label with human-readable format."""
        seconds = self.duration_spin.value()
        if seconds < 60:
            self.duration_label.setText(f"({int(seconds)} שניות)")
        else:
            minutes = seconds / 60
            self.duration_label.setText(f"(~{minutes:.1f} דקות)")

    def selected_values(self) -> Dict[str, object]:
        """
        Get the selected visual settings values.
        
        Returns:
            Dict containing all visual generation settings
        """
        # Get current geometry to save it
        geo = bytes(self.saveGeometry().toHex()).decode("ascii")
        
        values = {
            "visual_generator": self.generator_combo.currentData() or "manim",
            "imagen_model": self.imagen_combo.currentData() or "imagen-4.0-generate-001",
            "veo_model": self.veo_combo.currentData() or "veo-2.0-generate-001",
            "auto_video_duration": self.auto_duration_cb.isChecked(),
            "video_duration_seconds": self.duration_spin.value(),
            "image_count": self.image_count_spin.value(),
            "visual_settings_geometry": geo,
        }
        
        _logger.debug(
            "[VisualSettingsDialog] selected_values -> image_count=%s, generator=%s",
            values["image_count"],
            values["visual_generator"],
        )
        
        return values

    def get_saved_values(self) -> Dict[str, object]:
        """Return the last values saved during accept(), or current selections."""
        if self._accepted_values is not None:
            return self._accepted_values
        return self.selected_values()

