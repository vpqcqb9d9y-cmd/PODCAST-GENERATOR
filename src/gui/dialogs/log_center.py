"""
M.B.S Studio - Log Center Dialog
==================================

Log viewer dialog with copy and export functionality.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogCenterDialog(QDialog):
    """
    Log viewer dialog with copy and export capabilities.
    
    Displays the current log buffer contents with options to
    copy to clipboard or save to a file.
    
    Args:
        log_buffer: List of log lines to display
        section_label_factory: Function to create section labels
        parent: Parent widget (optional)
    
    Example:
        >>> dialog = LogCenterDialog(
        ...     log_buffer=self.log_buffer,
        ...     section_label_factory=self._section_label,
        ...     parent=main_window
        ... )
        >>> dialog.exec()
    """

    def __init__(
        self,
        log_buffer: List[str],
        section_label_factory: Callable[[str], QLabel],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the log center dialog.
        
        Args:
            log_buffer: Current log buffer contents
            section_label_factory: Factory for section labels
            parent: Parent widget
        """
        super().__init__(parent)
        self.log_buffer = log_buffer
        self._section_label = section_label_factory
        
        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("מרכז לוגים")
        self.resize(760, 520)

    def _setup_ui(self) -> None:
        """Build the dialog UI components."""
        layout = QVBoxLayout(self)
        
        # Section header
        layout.addWidget(self._section_label("לוג ריצה אחרון"))
        
        # Log text display
        log_text = (
            "\n".join(self.log_buffer)
            if self.log_buffer
            else "עדיין אין לוגים להצגה."
        )
        self.log_view = QPlainTextEdit(log_text)
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogCenterView")
        layout.addWidget(self.log_view, 1)
        
        # Button row
        button_row = QHBoxLayout()
        
        copy_btn = QPushButton("העתק ללוח")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        
        save_btn = QPushButton("שמור לקובץ...")
        save_btn.clicked.connect(self._save_to_file)
        
        close_btn = QPushButton("סגור")
        close_btn.clicked.connect(self.accept)
        
        button_row.addWidget(copy_btn)
        button_row.addWidget(save_btn)
        button_row.addStretch(1)
        button_row.addWidget(close_btn)
        
        layout.addLayout(button_row)

    def _copy_to_clipboard(self) -> None:
        """Copy log contents to clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.log_view.toPlainText())

    def _save_to_file(self) -> None:
        """Save log contents to a file."""
        text = self.log_view.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "לוג ריק", "אין תוכן לשמור.")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            "שמור לוג",
            "run_log.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return
        
        try:
            Path(path).write_text(text, encoding="utf-8")
            QMessageBox.information(self, "נשמר", f"לוג נשמר אל {path}")
        except OSError as exc:
            QMessageBox.warning(self, "שגיאה", f"לא ניתן לשמור:\n{exc}")

    def update_log(self, log_buffer: List[str]) -> None:
        """
        Update the displayed log content.
        
        Args:
            log_buffer: New log buffer contents
        """
        self.log_buffer = log_buffer
        log_text = (
            "\n".join(log_buffer)
            if log_buffer
            else "עדיין אין לוגים להצגה."
        )
        self.log_view.setPlainText(log_text)

