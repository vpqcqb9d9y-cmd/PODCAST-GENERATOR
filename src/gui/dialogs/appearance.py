"""
M.B.S Studio - Chat Appearance Dialog
======================================

Dialog for customizing chat display settings including
font, theme, background, and visual preferences.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from src.utils import Settings
from ..constants import CHAT_THEMES


class ChatAppearanceDialog(QDialog):
    """
    Dialog for configuring chat display appearance.
    
    Allows users to customize:
        - Chat font family and size
        - Color theme (dark/light)
        - Background brightness
        - Background color theme (preset colors)
    
    Args:
        settings: Application settings object
        font_library: Path to the font library directory
        load_fonts: Callable that returns available font options
        parent: Parent widget (optional)
    
    Example:
        >>> dialog = ChatAppearanceDialog(
        ...     settings=app_settings,
        ...     font_library=FONT_LIBRARY_DIR,
        ...     load_fonts=self._chat_font_options,
        ...     parent=main_window
        ... )
        >>> if dialog.exec() == QDialog.DialogCode.Accepted:
        ...     values = dialog.selected_values()
        ...     settings.save_ui_preferences(values)
    """

    def __init__(
        self,
        settings: Settings,
        font_library: Path,
        load_fonts: Callable[[], List[Dict[str, object]]],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the appearance dialog.
        
        Args:
            settings: Current application settings
            font_library: Directory containing custom fonts
            load_fonts: Function to load available font options
            parent: Parent widget
        """
        super().__init__(parent)
        self.settings = settings
        self.font_library = font_library
        self._load_fonts = load_fonts
        self._font_options: List[Dict[str, object]] = []
        
        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("הגדרות תצוגה")
        self.resize(520, 400)

    def _setup_ui(self) -> None:
        """Build the dialog UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("⚙️ הגדרות תצוגת שיחה")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        # Font library hint
        hint = QLabel(
            f"💡 להוספת פונטים בעברית, גררו קבצי .ttf/.otf אל: {self.font_library}"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(hint)

        # Font selection
        layout.addLayout(self._build_font_row())
        
        # Font size
        layout.addLayout(self._build_font_size_row())
        
        # Theme selection
        layout.addLayout(self._build_theme_row())
        
        # Brightness slider
        layout.addLayout(self._build_brightness_row())
        
        # Background color theme
        layout.addLayout(self._build_background_theme_row())

        # Bubble color selection
        layout.addLayout(self._build_bubble_color_row())

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_font_row(self) -> QHBoxLayout:
        """Build the font selection row."""
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("פונט שיחה"))
        
        self.font_combo = QComboBox()
        self.import_font_btn = QPushButton("ייבא פונט...")
        self.import_font_btn.clicked.connect(self._import_font)
        
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(self.import_font_btn)
        
        self._populate_fonts(self._load_fonts())
        return font_row

    def _build_font_size_row(self) -> QHBoxLayout:
        """Build the font size selection row."""
        font_size_row = QHBoxLayout()
        font_size_row.addWidget(QLabel("גודל פונט"))
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 28)
        self.font_size_spin.setValue(
            int(getattr(self.settings, "chat_font_size", 13) or 13)
        )
        
        font_size_row.addWidget(self.font_size_spin, 1)
        return font_size_row

    def _build_theme_row(self) -> QHBoxLayout:
        """Build the theme selection row."""
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("ערכת צבע"))
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("כהה", "dark")
        self.theme_combo.addItem("בהירה", "light")
        
        current_theme = (self.settings.chat_theme or "dark").lower()
        index = max(0, self.theme_combo.findData(current_theme))
        self.theme_combo.setCurrentIndex(index)
        
        theme_row.addWidget(self.theme_combo, 1)
        return theme_row

    def _build_brightness_row(self) -> QHBoxLayout:
        """Build the brightness slider row."""
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(QLabel("בהירות רקע"))
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(20, 100)
        
        initial_brightness = int(
            max(20, min(100, round(
                float(self.settings.chat_banner_brightness or 0.85) * 100
            )))
        )
        self.brightness_slider.setValue(initial_brightness)
        
        self.brightness_label = QLabel(f"{initial_brightness}%")
        self.brightness_slider.valueChanged.connect(
            lambda value: self.brightness_label.setText(f"{value}%")
        )
        
        brightness_row.addWidget(self.brightness_slider, 1)
        brightness_row.addWidget(self.brightness_label)
        return brightness_row

    def _build_background_theme_row(self) -> QHBoxLayout:
        """Build the background color theme selection row."""
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("🎨 ערכת רקע"))
        
        self.bg_theme_combo = QComboBox()
        
        # Add theme options from constants
        for key, theme_data in CHAT_THEMES.items():
            self.bg_theme_combo.addItem(theme_data["name"], key)
        
        # Set current selection
        current_bg_theme = getattr(self.settings, "chat_bg_theme", "midnight") or "midnight"
        theme_index = max(0, self.bg_theme_combo.findData(current_bg_theme))
        self.bg_theme_combo.setCurrentIndex(theme_index)
        
        theme_row.addWidget(self.bg_theme_combo, 1)
        return theme_row

    def _color_palette(self) -> List[Dict[str, str]]:
        """Preset palette for chat bubbles."""
        return [
            {"label": "טורקיז (ברירת מחדל)", "hex": "#0f766e"},
            {"label": "סגול עמוק", "hex": "#4c1d95"},
            {"label": "כחול רויאל", "hex": "#2563eb"},
            {"label": "ירוק", "hex": "#16a34a"},
            {"label": "כתום", "hex": "#ea580c"},
            {"label": "ענבר", "hex": "#f59e0b"},
            {"label": "ורוד פוקסיה", "hex": "#c026d3"},
            {"label": "טורקיז בהיר", "hex": "#0891b2"},
            {"label": "אפור בהיר", "hex": "#e2e8f0"},
        ]

    def _default_bubble_colors(self) -> Dict[str, str]:
        """Return default colors based on current theme."""
        theme = (self.settings.chat_theme or "dark").lower()
        if theme == "light":
            return {"assistant": "#e2e8f0", "user": "#0d9488"}
        return {"assistant": "#4c1d95", "user": "#0f766e"}

    def _build_bubble_color_row(self) -> QVBoxLayout:
        """Build combo boxes for user/assistant bubble colors."""
        container = QVBoxLayout()
        container.setSpacing(6)

        defaults = self._default_bubble_colors()
        current_user = getattr(self.settings, "chat_user_bubble", "") or defaults["user"]
        current_ai = getattr(self.settings, "chat_assistant_bubble", "") or defaults["assistant"]

        def _make_row(label_text: str, current_hex: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            combo = QComboBox()
            for option in self._color_palette():
                combo.addItem(f"{option['label']} ({option['hex']})", option["hex"])
            idx = max(0, combo.findData(current_hex, Qt.ItemDataRole.UserRole))
            combo.setCurrentIndex(idx)
            row.addWidget(combo, 1)
            return row, combo

        user_row, self.user_color_combo = _make_row("צבע בועת משתמש", current_user)
        ai_row, self.assistant_color_combo = _make_row("צבע בועת עוזר (AI)", current_ai)

        container.addLayout(user_row)
        container.addLayout(ai_row)
        return container

    def _populate_fonts(
        self,
        options: List[Dict[str, object]],
        preferred_path: Optional[str] = None,
    ) -> None:
        """
        Populate the font combo box with available fonts.
        
        Args:
            options: List of font option dicts
            preferred_path: Path to pre-select (optional)
        """
        self._font_options = options
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        
        selected_index = 0
        for option in options:
            self.font_combo.addItem(option["label"], option)
            is_selected = option.get("selected", False)
            if preferred_path is not None:
                is_selected = str(option.get("path", "")) == str(preferred_path)
            if is_selected:
                selected_index = self.font_combo.count() - 1
        
        self.font_combo.setCurrentIndex(
            selected_index if self.font_combo.count() else -1
        )
        self.font_combo.blockSignals(False)

    def _current_font_data(self) -> Dict[str, object]:
        """Get the currently selected font data."""
        data = self.font_combo.currentData()
        if isinstance(data, dict):
            return data
        return {
            "family": self.settings.chat_font_family or "Assistant",
            "path": "",
        }

    def _import_font(self) -> None:
        """Import a font file to the font library."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "ייבוא פונט",
            str(self.font_library),
            "Fonts (*.ttf *.otf *.ttc)",
        )
        if not path:
            return
        
        source = Path(path)
        destination = self.font_library / source.name
        
        # Handle duplicate names
        counter = 1
        while destination.exists():
            destination = self.font_library / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        
        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            QMessageBox.warning(self, "שגיאה", f"ייבוא הפונט נכשל:\n{exc}")
            return
        
        options = self._load_fonts()
        self._populate_fonts(options, preferred_path=str(destination))
        QMessageBox.information(
            self,
            "הושלם",
            f"הפונט '{destination.name}' נוסף לספריית הצ'אט.",
        )
        self._font_options = options

    def selected_values(self) -> Dict[str, object]:
        """
        Get the selected appearance values.
        
        Returns:
            Dict containing all appearance settings
        """
        font_data = self._current_font_data()
        theme_value = self.theme_combo.currentData() or "dark"
        bg_theme_value = self.bg_theme_combo.currentData() or "midnight"
        
        return {
            "chat_font_family": font_data.get(
                "family",
                self.settings.chat_font_family or "Assistant",
            ),
            "chat_font_path": font_data.get("path", ""),
            "chat_font_size": self.font_size_spin.value(),
            "chat_theme": theme_value,
            "chat_banner_brightness": self.brightness_slider.value() / 100,
            "chat_bg_theme": bg_theme_value,
            "chat_user_bubble": self.user_color_combo.currentData(),
            "chat_assistant_bubble": self.assistant_color_combo.currentData(),
        }

