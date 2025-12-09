"""
M.B.S Studio - Quality Report Dialog
=====================================

Dialog for displaying quality verification results with visual indicators.

Author: M.B.S Studio
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QFrame,
    QProgressBar,
    QMessageBox,
)

if TYPE_CHECKING:
    from src.utils import Settings, QualityChecker, QualityReport


class QualityCheckWorker(QThread):
    """Background worker for running quality checks."""
    
    finished = pyqtSignal(object)  # QualityChecker
    progress = pyqtSignal(str)  # Status message
    error = pyqtSignal(str)
    
    def __init__(
        self,
        settings: "Settings",
        output_dir: Optional[Path] = None,
        check_quota: bool = True,
    ):
        super().__init__()
        self.settings = settings
        self.output_dir = output_dir
        self.check_quota = check_quota
    
    def run(self):
        try:
            from src.utils import QualityChecker
            
            self.progress.emit("מאתחל בדיקות איכות...")
            checker = QualityChecker(self.settings)
            
            # Run preflight checks
            self.progress.emit("מריץ בדיקות לפני הרצה...")
            checker.run_preflight_checks(
                estimated_characters=0,
                skip_quota_check=not self.check_quota,
            )
            
            # Run postprocess checks if output_dir provided
            if self.output_dir and self.output_dir.exists():
                self.progress.emit("מריץ בדיקות פלט...")
                checker.run_postprocess_checks(run_dir=self.output_dir)
            
            self.progress.emit("בדיקות הושלמו!")
            self.finished.emit(checker)
            
        except Exception as e:
            self.error.emit(str(e))


class QualityReportDialog(QDialog):
    """
    Dialog for displaying quality verification results.
    
    Features:
        - Pre-flight check results with status indicators
        - Post-processing check results
        - Recommendations list
        - Export report functionality
    """
    
    STATUS_COLORS = {
        "PASS": "#22c55e",     # Green
        "FAIL": "#ef4444",     # Red
        "WARNING": "#f59e0b",  # Orange
        "SKIP": "#6b7280",     # Gray
        "PENDING": "#3b82f6",  # Blue
    }
    
    STATUS_ICONS = {
        "PASS": "✅",
        "FAIL": "❌",
        "WARNING": "⚠️",
        "SKIP": "⏭️",
        "PENDING": "⏳",
    }
    
    def __init__(
        self,
        parent=None,
        settings: "Settings" = None,
        output_dir: Optional[Path] = None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.output_dir = output_dir
        self.checker = None
        self.worker = None
        
        self.setWindowTitle("בדיקת איכות מערכת - M.B.S Studio")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self._setup_ui()
        
        # Auto-run checks when dialog opens
        if settings:
            self._start_quality_check()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("🔍 בדיקת איכות מערכת")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Run type (Preview/Full)
        self.run_type_label = QLabel("")
        self.run_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.run_type_label)
        
        # Status label
        self.status_label = QLabel("מתכונן לבדיקות...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar (shown during checks)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress_bar)
        
        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setSpacing(12)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.results_widget)
        layout.addWidget(scroll, 1)
        
        # Overall status banner (hidden until checks complete)
        self.overall_banner = QFrame()
        self.overall_banner.setObjectName("OverallBanner")
        banner_layout = QHBoxLayout(self.overall_banner)
        self.overall_status_label = QLabel()
        self.overall_status_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.overall_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner_layout.addWidget(self.overall_status_label)
        self.overall_banner.setVisible(False)
        layout.addWidget(self.overall_banner)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.rerun_btn = QPushButton("🔄 הרץ שוב")
        self.rerun_btn.clicked.connect(self._start_quality_check)
        self.rerun_btn.setEnabled(False)
        buttons_layout.addWidget(self.rerun_btn)
        
        self.export_btn = QPushButton("📄 ייצא דו\"ח")
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setEnabled(False)
        buttons_layout.addWidget(self.export_btn)
        
        buttons_layout.addStretch()
        
        self.close_btn = QPushButton("סגור")
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)
        
        layout.addLayout(buttons_layout)
        
        # Styling
        self.setStyleSheet("""
            QDialog {
                background: #0f172a;
            }
            QLabel {
                color: #e2e8f0;
            }
            QFrame#OverallBanner {
                border-radius: 8px;
                padding: 12px;
            }
            QFrame#CheckCard {
                background: #1e293b;
                border-radius: 8px;
                padding: 8px;
            }
            QFrame#CheckCard QLabel {
                color: #e2e8f0;
            }
            QPushButton {
                background: #1f2937;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #374151;
            }
            QPushButton:disabled {
                background: #111827;
                color: #4b5563;
            }
            QScrollArea {
                background: transparent;
            }
        """)
    
    def _start_quality_check(self):
        """Start the quality check worker."""
        # Clear previous results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.overall_banner.setVisible(False)
        self.progress_bar.setVisible(True)
        self.rerun_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status_label.setText("מריץ בדיקות איכות...")
        
        # Start worker
        self.worker = QualityCheckWorker(
            settings=self.settings,
            output_dir=self.output_dir,
            check_quota=True,
        )
        self.worker.finished.connect(self._on_check_finished)
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_progress(self, message: str):
        """Update progress status."""
        self.status_label.setText(message)
    
    def _on_error(self, error: str):
        """Handle check error."""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"שגיאה: {error}")
        self.rerun_btn.setEnabled(True)
        
        QMessageBox.warning(self, "שגיאה בבדיקות", f"הבדיקות נכשלו:\n{error}")
    
    def _on_check_finished(self, checker: "QualityChecker"):
        """Handle completed checks."""
        self.checker = checker
        self.progress_bar.setVisible(False)
        self.rerun_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        report = checker.report
        run_type = getattr(report, "run_type", "FULL") or "FULL"
        self.run_type_label.setText(f"סוג ריצה: {run_type}")
        
        # Update overall status banner
        overall_status = report.overall_status
        color = self.STATUS_COLORS.get(overall_status, "#3b82f6")
        icon = self.STATUS_ICONS.get(overall_status, "?")
        
        self.overall_banner.setStyleSheet(f"""
            QFrame#OverallBanner {{
                background: {color}20;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        
        status_text = {
            "PASS": "כל הבדיקות עברו בהצלחה!",
            "FAIL": "נמצאו בעיות שיש לפתור",
            "WARNING": "עברו עם אזהרות",
            "PENDING": "בדיקות בתהליך...",
        }.get(overall_status, overall_status)
        
        self.overall_status_label.setText(f"{icon} {status_text}")
        self.overall_status_label.setStyleSheet(f"color: {color};")
        self.overall_banner.setVisible(True)
        
        # Add preflight checks section
        if report.preflight_checks:
            section_label = QLabel("📋 בדיקות לפני הרצה")
            section_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.results_layout.addWidget(section_label)
            
            for check in report.preflight_checks:
                self._add_check_card(check)
        
        # Add postprocess checks section
        if report.postprocess_checks:
            section_label = QLabel("📊 בדיקות פלט")
            section_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.results_layout.addWidget(section_label)
            
            for check in report.postprocess_checks:
                self._add_check_card(check)
        
        # Add recommendations
        if report.recommendations:
            section_label = QLabel("💡 המלצות")
            section_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.results_layout.addWidget(section_label)
            
            for rec in report.recommendations:
                rec_label = QLabel(f"• {rec}")
                rec_label.setWordWrap(True)
                rec_label.setStyleSheet("color: #fbbf24; padding-left: 12px;")
                self.results_layout.addWidget(rec_label)
        
        self.status_label.setText(f"בדיקות הושלמו: {overall_status}")
    
    def _add_check_card(self, check):
        """Add a check result card to the results."""
        card = QFrame()
        card.setObjectName("CheckCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        
        # Status icon
        icon = self.STATUS_ICONS.get(check.status, "?")
        color = self.STATUS_COLORS.get(check.status, "#6b7280")
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 18px; color: {color};")
        card_layout.addWidget(icon_label)
        
        # Check info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(check.name)
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {color};")
        info_layout.addWidget(name_label)
        
        message_label = QLabel(check.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_layout.addWidget(message_label)
        
        card_layout.addLayout(info_layout, 1)
        
        self.results_layout.addWidget(card)
    
    def _export_report(self):
        """Export the quality report to file."""
        if not self.checker:
            return
        
        if self.output_dir and self.output_dir.exists():
            report_path = self.checker.report.save(self.output_dir)
            QMessageBox.information(
                self,
                "דו\"ח נשמר",
                f"הדו\"ח נשמר ב:\n{report_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "לא ניתן לשמור",
                "אין תיקיית פלט פעילה לשמירת הדו\"ח."
            )

