"""
M.B.S Studio - About Dialog
============================

Simple about dialog showing version and application information.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants import APP_BUILD_DATE, APP_DISPLAY_NAME, APP_VERSION


class AboutDialog(QDialog):
    """
    Simple about dialog displaying application information.
    
    Shows:
        - Application name and version
        - Build date
        - Credits
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("אודות")
        self.setFixedSize(350, 250)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # App name
        name_label = QLabel(f"🎙️ {APP_DISPLAY_NAME}")
        name_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #38bdf8;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        
        # Version
        version_label = QLabel(f"גרסה {APP_VERSION}")
        version_label.setStyleSheet("font-size: 16px; color: #22c55e;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        # Build date
        build_label = QLabel(f"תאריך בנייה: {APP_BUILD_DATE}")
        build_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(build_label)
        
        layout.addSpacing(10)
        
        # Description
        desc_label = QLabel(
            "מערכת מתקדמת ליצירת פודקאסטים\n"
            "ווידאו מתומללים בעברית עם AI"
        )
        desc_label.setStyleSheet("color: #e2e8f0;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # Credits
        credits_label = QLabel("© 2025 M.B.S Studio. כל הזכויות שמורות.")
        credits_label.setStyleSheet("font-size: 10px; color: #64748b;")
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_label)
        
        # Close button
        close_btn = QPushButton("סגור")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

