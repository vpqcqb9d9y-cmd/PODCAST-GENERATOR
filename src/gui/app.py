"""
M.B.S Studio - Main Application Window
========================================

The primary GUI application for the M.B.S Studio podcast generation system.
Provides a three-panel interface for project management, AI chat workspace,
and pipeline control with live progress tracking.

Features:
    - Projects Hub: Browse, load, and manage previous runs
    - Workspace: AI-powered chat for metadata generation
    - Control Panel: Pipeline configuration and execution
    - Cost Center: Budget tracking and analytics
    - Log Center: Real-time log viewing and export

Author: M.B.S Studio
Version: 2.0.0 (Refactored)
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, QByteArray, QThread, QObject, pyqtSignal
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QKeyEvent,
    QPdfWriter,
    QPixmap,
    QResizeEvent,
    QTextDocument,
    QTextOption,
    QCloseEvent,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Internal imports from extracted modules
from src.metadata import MetadataChatSession
from src.outputs import NetworkMapExporter, SlideDeckExporter, StoryExporter
from src.utils import HistoryManager, Settings, VoiceProfileManager, validate_history_entry_paths, get_valid_run_dir
from src.utils.storage import _slugify
from src.audio.voice_manager import VoiceLabService

# GUI module imports
from .constants import (
    APP_DISPLAY_NAME,
    APP_ASSISTANT_NAME,
    APP_LOGO_PATH,
    FONT_LIBRARY_DIR,
    SYSTEM_CHAT_FONTS,
    PIPELINE_STAGES,
    CHAT_THEMES,
    WORDS_PER_MINUTE,
    TOKENS_PER_WORD,
    OUTPUT_TOKEN_RATIO,
    CHARS_PER_WORD,
    AZURE_GPT_INPUT_COST,
    AZURE_GPT_OUTPUT_COST,
    GEMINI_INPUT_COST,
    GEMINI_OUTPUT_COST,
    TTS_COST_PER_MILLION,
    VIDEO_OVERHEAD_COST,
    PPT_EXTRA_COST,
    LOG_BUFFER_MAX_SIZE,
)
from .workers import PipelineWorker, ChatWorker, MetadataSeedWorker, VisualMetadataWorker
from .widgets import SmoothScrollArea, ChatBubbleDelegate, _text_is_rtl
from .dialogs import (
    AboutDialog,
    BackupRestoreDialog,
    ChatAppearanceDialog,
    CostCenterDialog,
    LogCenterDialog,
    OnboardingWizard,
    QualityReportDialog,
    VisualSettingsDialog,
)
from .panels import build_projects_panel, build_workspace_panel, build_summary_panel, build_control_panel


class RecordingWorker(QObject):
    """
    Offloads 60s microphone recording to a worker thread so the UI stays responsive.
    Emits status updates and completion/error signals for the Voice Lab flow.
    """

    status = pyqtSignal(str)
    finished = pyqtSignal(Path, int)
    error = pyqtSignal(str)

    def __init__(self, duration: int = 60, samplerate: int = 44100, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.duration = duration
        self.samplerate = samplerate
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True
        try:
            import sounddevice as sd  # type: ignore
            sd.stop()
        except Exception:
            pass

    def run(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np  # type: ignore
            from scipy.io import wavfile  # type: ignore
        except Exception as exc:
            self.error.emit(f"Missing recording dependencies: {exc}")
            return

        try:
            self.status.emit("מקליט... לחצו שוב להפסקה.")
            frames = int(self.duration * self.samplerate)
            data = sd.rec(frames, samplerate=self.samplerate, channels=1, dtype="float32")
            sd.wait()

            if self._stop_requested:
                self.status.emit("הקלטה הופסקה.")
                self.finished.emit(Path(), 0)
                return

            temp_path = Path("temp_recording.wav")
            wavfile.write(temp_path, self.samplerate, (data * 32767).astype(np.int16))
            self.status.emit("Recording saved: temp_recording.wav")
            self.finished.emit(temp_path, len(data))
        except Exception as exc:
            self.error.emit(str(exc))


class PodcastGeneratorWindow(QMainWindow):
    """
    Main application window for the M.B.S Studio podcast generator.
    
    This window provides a comprehensive three-panel interface for:
    - Projects Hub: Browse, load, and manage previous pipeline runs
    - Workspace: AI-powered chat for metadata generation and content planning
    - Control Panel: Configure and execute the podcast pipeline
    
    The window integrates with backend services for:
    - AI-powered dialogue generation (Azure GPT/Gemini)
    - Text-to-speech synthesis (Azure Neural TTS)
    - Video composition with Manim animations
    - PPTX slide deck generation
    
    Features:
    - Real-time pipeline progress tracking with ETA
    - Cost center for budget management and analytics
    - Log center for debugging and troubleshooting
    - History management for previous runs
    - RTL/LTR language support for Hebrew/English
    
    Signals:
        - Pipeline status updates propagate to header status bar
        - Chat messages update metadata in real-time
        - File changes trigger automatic metadata seeding
    
    Example:
        >>> app = QApplication(sys.argv)
        >>> window = PodcastGeneratorWindow()
        >>> window.show()
        >>> sys.exit(app.exec())
    
    Attributes:
        settings (Settings): Application configuration
        voice_manager (VoiceProfileManager): Voice profile handler
        history (HistoryManager): Pipeline run history
        chat_session (MetadataChatSession): AI chat session
        current_metadata (dict): Current metadata being built
        pipeline_stages (list): Pipeline progress tracking stages
    """
    
    def __init__(self) -> None:
        super().__init__()
        
        # Initialize logger for this instance
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("[PodcastGeneratorWindow] Initializing main window")

        self.settings = self._load_settings()
        has_saved_geometry = bool(
            getattr(self.settings, "main_window_geometry", "") or
            getattr(self.settings, "main_window_state", "")
        )

        self.setWindowTitle(f"{APP_DISPLAY_NAME} - יצירת פודקאסטים")
        # Fallback size in case no saved preferences exist
        self.resize(1600, 950)
        if not has_saved_geometry:
            # Preserve user-defined geometry on subsequent launches
            self.setWindowState(Qt.WindowState.WindowMaximized)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.show()
        self.worker: Optional[PipelineWorker] = None
        self.voice_manager = VoiceProfileManager(
            self.settings.voice_profile_path, self.settings.default_voice_profile
        )
        try:
            self.voice_lab_service: Optional[VoiceLabService] = VoiceLabService(self.settings)
        except ValueError:
            self.voice_lab_service = None
        self.history = HistoryManager(self.settings.output_base_dir)
        self.chat_session = MetadataChatSession(self.settings)
        self.chat_worker: Optional[ChatWorker] = None
        self.network_exporter = NetworkMapExporter()
        self.seed_worker: Optional[MetadataSeedWorker] = None
        self._chat_busy_counter = 0
        self._active_transcript: Optional[str] = None
        self.current_metadata = self.chat_session.export_metadata()
        self.metadata_temp_path = self.settings.output_base_dir / "_gui_metadata.json"
        self.cost_totals = {"openai_cost_usd": 0.0, "tts_characters": 0}
        self.template_buttons: List[QPushButton] = []
        self.logo_path = APP_LOGO_PATH
        self.font_library_dir = FONT_LIBRARY_DIR
        self.font_library_dir.mkdir(parents=True, exist_ok=True)
        self._font_cache: Dict[str, List[str]] = {}
        if self.logo_path.exists():
            self.setWindowIcon(QIcon(str(self.logo_path)))
        self.metadata_dirty = False
        self._suppress_metadata_signal = False
        self.history_index: Dict[str, Dict[str, object]] = {}
        self.active_history_entry: Optional[Dict[str, object]] = None
        self._geometry_restored = False
        self._gemini_probe_scheduled = False
        self.pending_run_dir: Optional[Path] = None
        self.log_buffer: List[str] = []
        self.log_console: Optional[QPlainTextEdit] = None
        self.run_status_card: Optional[QFrame] = None
        self.project_card_entries: List[Dict[str, object]] = []
        self.run_stage_label: Optional[QLabel] = None
        self.run_timer_label: Optional[QLabel] = None
        self.run_progress_bar: Optional[QProgressBar] = None
        self.chat_card: Optional[QFrame] = None
        self.chat_delegate: Optional[ChatBubbleDelegate] = None
        self.header_status_frame: Optional[QFrame] = None
        self.header_stage_label: Optional[QLabel] = None
        self.header_timer_label: Optional[QLabel] = None
        self.header_progress_bar: Optional[QProgressBar] = None
        self.system_badge_label: Optional[QLabel] = None
        self.system_status_banner: Optional[QFrame] = None
        self.header_status_hide_timer: Optional[QTimer] = None
        self.pipeline_status_timer: Optional[QTimer] = None
        self._record_thread: Optional[QThread] = None
        self._record_worker: Optional[RecordingWorker] = None
        # Use pipeline stages from constants (includes icons for enhanced progress display)
        self.pipeline_stages = PIPELINE_STAGES
        self.pipeline_stage_index = 0
        self._system_badge_values = {"cpu": "CPU --", "mem": "MEM --", "net": "NET --"}
        self.pipeline_start_time: Optional[float] = None
        self._current_stage_start: Optional[float] = None
        self._performance_averages: Dict[str, float] = {}
        self._latest_visual_metadata: Optional[Dict[str, object]] = None
        self._latest_visual_metadata_path: Optional[Path] = None
        self._system_metrics_timer: Optional[QTimer] = None
        self._battery_label: Optional[QLabel] = None
        self._cpu_label: Optional[QLabel] = None
        self._memory_label: Optional[QLabel] = None
        self._network_label: Optional[QLabel] = None
        self._last_cpu_percent: float = 0.0
        self._visual_meta_spinner_timer: Optional[QTimer] = None
        self._visual_meta_spinner_step: int = 0
        self._visual_meta_spinner_base: str = ""
        self._chat_resized_once: bool = False
        self._psutil_mod = None
        self._psutil_retry_scheduled = False
        self._psutil_last_error: Optional[str] = None
        self._psutil_attempts: int = 0
        self.voice_lab_file_path: Optional[Path] = None
        self.voice_lab_status_label: Optional[QLabel] = None
        self.voice_lab_quota_label: Optional[QLabel] = None
        self.voice_lab_file_label: Optional[QLabel] = None

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.addWidget(self._build_header())

        self.projects_panel = self._build_projects_panel()
        self.workspace_panel = self._build_workspace_panel()
        self.summary_panel = self._build_summary_panel()
        self.voice_lab_panel = self._build_voice_lab_panel()

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(6)
        self.content_splitter.setMinimumWidth(720)
        self.workspace_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.summary_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.voice_lab_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.workspace_scroll = self._wrap_scroll_area(self.workspace_panel)
        self.workspace_scroll.setMinimumWidth(620)

        self.summary_scroll = self._wrap_scroll_area(self.summary_panel)
        self.summary_scroll.setMinimumWidth(300)

        self.voice_lab_scroll = self._wrap_scroll_area(self.voice_lab_panel)

        self.control_tabs = QTabWidget()
        self.control_tabs.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        # Keep right rail tall but cap width to avoid bleeding into workspace
        self.control_tabs.setMinimumWidth(300)
        self.control_tabs.setMaximumWidth(360)
        self.control_tabs.addTab(self.summary_scroll, "🧭 Control Panel")
        self.control_tabs.addTab(self.voice_lab_scroll, "🎙️ Voice Lab")

        self.content_splitter.addWidget(self.workspace_scroll)
        self.content_splitter.addWidget(self.control_tabs)
        # Bias space toward the workspace; right rail keeps a bounded width
        self.content_splitter.setStretchFactor(0, 10)
        self.content_splitter.setStretchFactor(1, 3)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setMinimumWidth(960)
        # Left panel directly without scroll area
        self.main_splitter.addWidget(self.projects_panel)
        self.main_splitter.addWidget(self.content_splitter)
        self.main_splitter.setStretchFactor(0, 0)  # Fixed width
        self.main_splitter.setStretchFactor(1, 1)  # Expandable
        self.main_splitter.splitterMoved.connect(self._schedule_layout_save)
        self.content_splitter.splitterMoved.connect(self._schedule_layout_save)
        # Apply saved splitter layout (falls back to safe defaults)
        self._restore_splitter_sizes()
        root_layout.addWidget(self.main_splitter, 1)
        self.system_status_banner = self._build_system_status_banner()
        root_layout.addWidget(self.system_status_banner)
        # Apply UI preferences after all widgets are built
        self._apply_chat_preferences()
        self.setStyleSheet(
            """
            QPushButton#run_pipeline_btn {
                background-color: #dc2626 !important;
                color: white !important;
                border: 1px solid #b91c1c;
                border-radius: 10px;
                font-weight: bold;
                padding: 12px 20px;
            }
            QPushButton#run_pipeline_btn:hover {
                background-color: #ef4444 !important;
            }
            QPushButton#run_pipeline_btn:disabled {
                background: #475569 !important;
                color: #cbd5e1 !important;
                border: 1px solid #334155 !important;
            }
            QPushButton#VoiceFab {
                border-radius: 40px;
                font-size: 32px;
                color: white;
                border: none;
            }
            QLabel#VoiceTimer {
                font-size: 24px;
                font-weight: bold;
                color: #cbd5e1;
            }
            QWidget {
                font-family: 'Segoe UI', 'Assistant', sans-serif;
                font-size: 13px;
                background-color: #020617;
                color: #e2e8f0;
            }
            QLabel#WindowTitle {
                color: #f8fafc;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel.section-title {
                font-size: 14px;
                color: #cbd5f5;
                font-weight: 600;
            }
            QLabel.helper {
                font-size: 12px;
                color: #94a3b8;
            }
            QFrame#Card {
                border: 1px solid #1e293b;
                border-radius: 16px;
                background: #0f172a;
            }
            QFrame#BudgetBanner {
                border: 1px solid #1d4ed8;
                border-radius: 14px;
                background: #020c1f;
            }
            QListWidget {
                border: 1px solid #1e293b;
                background: #030b1d;
                color: #e2e8f0;
            }
            QListWidget::item:selected {
                background: #1e3a8a;
            }
            QPlainTextEdit,
            QTextEdit,
            QLineEdit {
                background: #020c1f;
                border: 1px solid #1e293b;
                border-radius: 10px;
                color: #f1f5f9;
                padding: 10px;
                font-size: 13px;
            }
            QPlainTextEdit#MetadataPreview {
                background: #010b1a;
                border: 1px solid #1d4ed8;
            }
            QComboBox,
            QSpinBox,
            QDoubleSpinBox {
                background: #0b1220;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 8px;
                color: #f1f5f9;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }
            QPushButton#PrimaryButton {
                background-color: #dc2626;
                color: white;
                padding: 10px 24px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #b91c1c;
            }
            QPushButton#PrimaryButton:disabled {
                background: #475569;
                color: #94a3b8;
            }
            QPushButton#Chip {
                background: #1e3a8a;
                color: #f8fafc;
                border-radius: 16px;
                padding: 8px 16px;
            }
            QPushButton#Chip:hover {
                background: #1d4ed8;
            }
            QPushButton {
                background: #1f2937;
                border: 1px solid #334155;
                border-radius: 10px;
                color: #e2e8f0;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background: #374151;
            }
            QPushButton:checked {
                background-color: #2563eb;
                border: 2px solid #60a5fa;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QScrollArea {
                border: none;
            }
            QCheckBox {
                spacing: 8px;
                color: #e2e8f0;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #475569;
                background: #0f172a;
            }
            QCheckBox::indicator:checked {
                background: #22c55e;
                border: 1px solid #22c55e;
                image: url(assets/check.svg);
            }
            QProgressBar {
                border: 1px solid #1f2937;
                background: #030712;
                padding: 3px;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 6px;
            }
            QFrame#HeaderStatus {
                border: 1px solid #1e3a8a;
                border-radius: 14px;
                background: #0f172a;
                padding: 6px 16px;
            }
            QFrame#HeaderStatus QLabel {
                color: #f8fafc;
            }
            QFrame#SystemStatusBanner {
                border: 1px solid #1e293b;
                border-radius: 14px;
                background: #010a18;
            }
            QFrame#SystemStatusBanner QLabel {
                color: #e2e8f0;
            }
            QFrame#ChatCard {
                border: 1px solid #1e293b;
                border-radius: 16px;
            }
            QFrame#ChatCard QListWidget#ChatHistory {
                background: transparent;
                border: none;
            }
            """
        )

        if has_saved_geometry:
            self._restore_window_geometry()
            self._geometry_restored = True

        self._refresh_history()
        self._sync_materials_to_session()
        self._update_metadata_preview()
        self._update_content_layout_mode()
        QTimer.singleShot(200, self._update_gemini_status_banner)
        
        # Initialize system status bar after window is shown
        # Use QTimer to ensure window is fully initialized
        QTimer.singleShot(100, self._init_system_status_bar)

    # --- UI builders -------------------------------------------------
    def _build_header(self) -> QWidget:
        from .constants import APP_VERSION
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        if APP_LOGO_PATH.exists():
            logo_pixmap = QPixmap(str(APP_LOGO_PATH))
            if not logo_pixmap.isNull():
                logo = QLabel()
                logo.setPixmap(
                    logo_pixmap.scaled(
                        140,
                        80,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                logo.setFixedSize(150, 80)
                logo.setStyleSheet("border:none;")
                layout.addWidget(logo)
        
        # Title with version
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel(f"{APP_DISPLAY_NAME} Workspace")
        title.setObjectName("WindowTitle")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_col.addWidget(title)
        
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("color: #64748b; font-size: 11px;")
        title_col.addWidget(self.version_label)
        layout.addLayout(title_col)
        
        layout.addStretch(1)

        # Main action buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        
        # Backup button
        self.backup_btn = QPushButton("💾")
        self.backup_btn.setToolTip("גיבוי ושחזור")
        self.backup_btn.setFixedWidth(40)
        self.backup_btn.clicked.connect(self._open_backup_dialog)
        buttons_row.addWidget(self.backup_btn)
        
        # Reload/Refresh button
        self.reload_btn = QPushButton("🔄")
        self.reload_btn.setToolTip("רענן ובדוק עדכונים")
        self.reload_btn.setFixedWidth(40)
        self.reload_btn.clicked.connect(self._reload_application)
        buttons_row.addWidget(self.reload_btn)
        
        # About button
        self.about_btn = QPushButton("ℹ️")
        self.about_btn.setToolTip("אודות")
        self.about_btn.setFixedWidth(40)
        self.about_btn.clicked.connect(self._open_about_dialog)
        buttons_row.addWidget(self.about_btn)
        
        self.cost_center_btn = QPushButton("מרכז עלויות")
        self.cost_center_btn.setObjectName("PrimaryButton")
        self.cost_center_btn.clicked.connect(self._open_cost_center)
        buttons_row.addWidget(self.cost_center_btn)
        
        self.chat_settings_btn = QPushButton("הגדרות תצוגה")
        self.chat_settings_btn.clicked.connect(self._open_chat_settings)
        buttons_row.addWidget(self.chat_settings_btn)
        
        self.visual_settings_btn = QPushButton("🎨 הגדרות ויזואליים")
        self.visual_settings_btn.clicked.connect(self._open_visual_settings)
        buttons_row.addWidget(self.visual_settings_btn)
        
        self.log_center_btn = QPushButton("מרכז לוגים")
        self.log_center_btn.clicked.connect(self._open_log_center)
        buttons_row.addWidget(self.log_center_btn)
        
        layout.addLayout(buttons_row)

        self.header_status_frame = self._build_header_status_badge()
        layout.addWidget(self.header_status_frame)
        return container

    def _build_header_status_badge(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderStatus")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)
        status_icon = QLabel("●")
        status_icon.setStyleSheet("color:#38bdf8;font-size:18px;")
        layout.addWidget(status_icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self.header_stage_label = QLabel("Pipeline ממתין...")
        self.header_stage_label.setStyleSheet("font-weight:600;")
        text_col.addWidget(self.header_stage_label)
        self.header_timer_label = QLabel("")
        self.header_timer_label.setProperty("class", "helper")
        text_col.addWidget(self.header_timer_label)
        layout.addLayout(text_col)

        self.header_progress_bar = QProgressBar()
        self.header_progress_bar.setRange(0, 100)
        self.header_progress_bar.setTextVisible(False)
        self.header_progress_bar.setFixedWidth(140)
        layout.addWidget(self.header_progress_bar)

        self.header_status_hide_timer = QTimer(self)
        self.header_status_hide_timer.setSingleShot(True)
        self.header_status_hide_timer.timeout.connect(self._hide_header_status)

        # Timer to refresh pipeline status/ETA even when log output is quiet
        self.pipeline_status_timer = QTimer(self)
        self.pipeline_status_timer.setInterval(1000)
        self.pipeline_status_timer.timeout.connect(self._on_pipeline_status_tick)

        # Default state: hidden until a run actually starts
        self.header_stage_label.setText("Pipeline idle")
        if self.header_timer_label:
            self.header_timer_label.setText("Waiting for first run")
        self.header_progress_bar.setValue(0)
        frame.setVisible(False)
        return frame

    def _build_system_status_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("SystemStatusBanner")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.setSpacing(24)

        def _make_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet("font-weight:600; color:#94a3b8; padding:0 8px;")
            return label

        self._cpu_label = _make_label("🧠 --%")
        self._memory_label = _make_label("💾 --%")
        self._battery_label = _make_label("🔋 --%")
        self._network_label = _make_label("🌐 בודק...")

        for widget in (self._cpu_label, self._memory_label, self._battery_label, self._network_label):
            layout.addWidget(widget)

        layout.addStretch(1)
        banner.setVisible(True)
        return banner

    def _build_projects_panel(self) -> QWidget:
        """Build the projects panel using the extracted panel builder."""
        return build_projects_panel(
            self,
            self._section_label,
            self._card_widget,
            self._add_stat_chip,
        )

    def _build_workspace_panel(self) -> QWidget:
        """Build the workspace panel using the extracted panel builder."""
        panel = build_workspace_panel(
            self,
            self._section_label,
            self._card_widget,
        )
        self._apply_chat_preferences()
        return panel

    def _build_summary_panel(self) -> QWidget:
        """Build the control panel (grouped inputs/settings/actions)."""
        panel = build_control_panel(
            self,
            self._section_label,
            self._helper_label,
            self._inline_row,
        )
        # --- RE-BINDING CRITICAL WIDGETS ---
        self.control_run_btn = panel.findChild(QPushButton, "run_pipeline_btn")
        self.open_output_btn = panel.findChild(QPushButton, "open_output_btn")
        self.preview_mode_cb = panel.findChild(QCheckBox, "preview_mode_cb")
        self.elevenlabs_voices_btn = panel.findChild(QPushButton, "elevenlabs_voices_btn")
        self.voice_combo = panel.findChild(QComboBox, "voice_combo")
        self.tts_provider_combo = panel.findChild(QComboBox, "tts_provider_combo")
        self.azure_voice_combo = panel.findChild(QComboBox, "azure_voice_combo")
        self.output_mode_combo = panel.findChild(QComboBox, "output_mode_combo")
        self.custom_project_name = panel.findChild(QLineEdit, "custom_project_name")
        if self.custom_project_name:
            self.custom_project_name.textChanged.connect(self._on_custom_project_name_changed)
        self.run_dir_preview = panel.findChild(QLabel, "run_dir_preview")
        # -----------------------------------
        self._reset_pipeline_status()
        if self.tts_provider_combo:
            self._handle_tts_provider_change()
        if self.output_mode_combo:
            saved_mode = getattr(self.settings, "output_mode", "video_audio") or "video_audio"
            idx = self.output_mode_combo.findData(saved_mode)
            if idx < 0:
                # Prefer video as the default so visuals are included
                idx = self.output_mode_combo.findData("video_audio")
            if idx >= 0:
                self.output_mode_combo.setCurrentIndex(idx)
        if hasattr(self, "include_visuals_cb") and self.include_visuals_cb:
            try:
                self.include_visuals_cb.setChecked(bool(getattr(self.settings, "include_visuals", True)))
            except Exception:
                self.include_visuals_cb.setChecked(True)
        if self.output_mode_combo:
            self.output_mode_combo.currentIndexChanged.connect(self._handle_output_mode_change)
            self._handle_output_mode_change()
        return panel

    def _build_voice_lab_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        back_btn = QPushButton("⬅️ חזרה ל-Control Panel")
        back_btn.setToolTip("חזרה ללשונית הבקרה הראשית.")
        back_btn.clicked.connect(lambda: self.control_tabs.setCurrentIndex(0))
        layout.addWidget(back_btn)

        layout.addWidget(self._section_label("🎙️ Voice Lab"))
        layout.addWidget(
            self._helper_label(
                "הקלט 60 שניות בסגנון WhatsApp, האזן, מחק או שכפל עם ElevenLabs."
            )
        )

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(10)

        timer_label = QLabel("00:00")
        timer_label.setObjectName("VoiceTimer")
        timer_label.setVisible(False)
        timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mic_btn = QPushButton("Record")
        mic_btn.setObjectName("VoiceFab")
        mic_btn.setCheckable(True)
        mic_btn.setFixedHeight(44)
        mic_btn.clicked.connect(self._on_record_clicked)

        stop_btn = QPushButton("Stop")
        stop_btn.setObjectName("voice_stop_btn")
        stop_btn.setFixedHeight(44)
        stop_btn.setEnabled(False)
        stop_btn.clicked.connect(self._stop_voice_recording)

        trash_btn = QPushButton("Delete")
        trash_btn.setObjectName("voice_trash_btn")
        trash_btn.setFixedHeight(36)
        trash_btn.setToolTip("נקה את ההקלטה הנוכחית.")
        trash_btn.clicked.connect(self._reset_voice_lab_file)

        record_controls = QWidget()
        record_controls_layout = QHBoxLayout(record_controls)
        record_controls_layout.setContentsMargins(0, 0, 0, 0)
        record_controls_layout.setSpacing(12)
        record_controls_layout.addWidget(trash_btn)
        record_controls_layout.addWidget(timer_label, 1)
        record_controls_layout.addWidget(mic_btn)
        record_controls_layout.addWidget(stop_btn)

        review_controls = QWidget()
        review_layout = QHBoxLayout(review_controls)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(10)

        play_btn = QPushButton("Play Preview")
        play_btn.setObjectName("PlayButton")
        play_btn.setFixedHeight(44)
        play_btn.clicked.connect(self._toggle_voice_preview)

        review_trash_btn = QPushButton("Delete")
        review_trash_btn.setObjectName("voice_review_trash_btn")
        review_trash_btn.setFixedHeight(44)
        review_trash_btn.clicked.connect(self._reset_voice_lab_file)

        self.voice_lab_clone_btn = QPushButton("Clone / Use")
        self.voice_lab_clone_btn.setObjectName("PrimaryButton")
        self.voice_lab_clone_btn.clicked.connect(self._handle_clone_voice)
        self.voice_lab_clone_btn.setEnabled(False)

        review_layout.addWidget(play_btn)
        review_layout.addWidget(review_trash_btn)
        review_layout.addWidget(self.voice_lab_clone_btn)
        review_layout.addStretch(1)
        review_controls.hide()

        content_layout.addWidget(record_controls)
        content_layout.addWidget(review_controls)
        layout.addWidget(content)

        self.voice_lab_file_label = QLabel("לא נבחר קובץ")
        self.voice_lab_file_label.setStyleSheet("color:#94a3b8;")
        layout.addWidget(self.voice_lab_file_label)

        self.voice_lab_status_label = self._helper_label("הקש על 🎙️ להקלטה או העלה קובץ.")
        layout.addWidget(self.voice_lab_status_label)

        upload_btn = QPushButton("העלה קובץ (WAV/MP3)")
        upload_btn.clicked.connect(self._select_voice_sample)
        layout.addWidget(upload_btn)

        quota_box = QGroupBox("מכסת תווים נותרת (ElevenLabs)")
        quota_layout = QVBoxLayout(quota_box)
        self.voice_lab_quota_label = QLabel("בודק מכסה...")
        quota_layout.addWidget(self.voice_lab_quota_label)
        layout.addWidget(quota_box)

        layout.addStretch(1)

        if not self.voice_lab_service:
            self.voice_lab_clone_btn.setEnabled(False)
            self.voice_lab_status_label.setText("נדרש ELEVENLABS_API_KEY כדי לשכפל קול.")
            self.voice_lab_quota_label.setText("מכסה לא זמינה ללא מפתח API.")
        else:
            self._refresh_voice_quota()

        self.voice_lab_mic_btn = mic_btn
        self.voice_lab_trash_btn = trash_btn
        self.voice_lab_timer_label = timer_label
        self.voice_lab_record_controls = record_controls
        self.voice_lab_review_controls = review_controls
        self.voice_lab_review_trash_btn = review_trash_btn
        self.voice_lab_play_btn = play_btn
        self.voice_lab_stop_btn = stop_btn
        self.voice_lab_state = "idle"
        self.voice_lab_timer = QTimer(self)
        self.voice_lab_timer.timeout.connect(self._tick_voice_timer)
        self.voice_lab_record_start: Optional[float] = None
        self.voice_playback_player = None
        self._set_voice_lab_state("idle")
        return panel

    def _on_record_clicked(self) -> None:
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np  # type: ignore
            from scipy.io import wavfile  # type: ignore
        except Exception:
            reply = QMessageBox.question(
                self,
                "נדרשת התקנה",
                "ספריות הקלטה חסרות. האם להתקין אותן כעת? (sounddevice, numpy, scipy)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "sounddevice", "numpy", "scipy"]
                    )
                    QMessageBox.information(
                        self, "התקנה הושלמה", "ספריות ההקלטה הותקנו בהצלחה."
                    )
                except Exception as exc_install:
                    QMessageBox.warning(
                        self,
                        "שגיאת התקנה",
                        f"נכשל בהתקנת ספריות ההקלטה:\n{exc_install}",
                    )
            btn.setChecked(False)
            return

        if btn.isChecked():
            if self._record_thread and self._record_thread.isRunning():
                btn.setChecked(True)
                self.voice_lab_status_label.setText("הקלטה כבר פעילה...")
                return
            self._set_voice_lab_state("recording")
            if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
                self.voice_lab_clone_btn.setEnabled(False)
            self._record_thread = QThread(self)
            self._record_worker = RecordingWorker(duration=60, samplerate=44100)
            self._record_worker.moveToThread(self._record_thread)

            self._record_thread.started.connect(self._record_worker.run)
            self._record_worker.status.connect(self.voice_lab_status_label.setText)
            self._record_worker.finished.connect(lambda path, frames: self._on_recording_finished(path, frames, btn))
            self._record_worker.error.connect(lambda msg: self._on_recording_error(msg, btn))
            self._record_worker.finished.connect(self._record_thread.quit)
            self._record_worker.error.connect(self._record_thread.quit)
            self._record_thread.finished.connect(self._record_worker.deleteLater)
            self._record_thread.finished.connect(self._record_thread.deleteLater)
            self._record_thread.finished.connect(self._clear_recording_refs)

            self._record_thread.start()
        else:
            if self._record_thread and self._record_thread.isRunning() and self._record_worker:
                self.voice_lab_status_label.setText("עוצר הקלטה...")
                self._record_worker.request_stop()
            btn.setChecked(False)
            self._set_voice_lab_state("idle")

    def _on_recording_finished(self, path: Path, frames: int, btn: QPushButton) -> None:
        btn.setChecked(False)
        if path and path.exists() and frames > 0:
            self.voice_lab_file_path = path
            self.voice_lab_file_label.setText(f"נשמר: {path.name}")
            self.voice_lab_status_label.setText("Recording saved: temp_recording.wav")
            if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
                self.voice_lab_clone_btn.setEnabled(True)
            self._set_voice_lab_state("review")
        else:
            self.voice_lab_status_label.setText("הקלטה הופסקה.")
            if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
                self.voice_lab_clone_btn.setEnabled(False)
            self._set_voice_lab_state("idle")
        self._clear_recording_refs()

    def _on_recording_error(self, message: str, btn: QPushButton) -> None:
        btn.setChecked(False)
        self.voice_lab_status_label.setText(f"שגיאת הקלטה: {message}")
        if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
            self.voice_lab_clone_btn.setEnabled(False)
        self._clear_recording_refs()
        self._set_voice_lab_state("idle")

    def _clear_recording_refs(self) -> None:
        if self._record_thread and self._record_thread.isRunning():
            self._record_thread.quit()
            self._record_thread.wait(1500)
        self._record_thread = None
        self._record_worker = None

    def _stop_voice_recording(self) -> None:
        """Stop recording safely from the UI (Stop button)."""
        if self._record_worker:
            self.voice_lab_status_label.setText("עוצר הקלטה...")
            self._record_worker.request_stop()
        btn = getattr(self, "voice_lab_mic_btn", None)
        if btn and btn.isChecked():
            btn.setChecked(False)

    def _reset_voice_lab_file(self) -> None:
        """Clear current voice sample and disable clone until a new file is selected."""
        if self.voice_lab_file_path and self.voice_lab_file_path.exists():
            try:
                self.voice_lab_file_path.unlink()
            except Exception:
                pass
        self.voice_lab_file_path = None
        if self.voice_lab_file_label:
            self.voice_lab_file_label.setText("לא נבחר קובץ")
        if self.voice_lab_status_label:
            self.voice_lab_status_label.setText("בחר/י קובץ או הקלט מחדש.")
        if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
            self.voice_lab_clone_btn.setEnabled(False)
        self._set_voice_lab_state("idle")
        self._stop_voice_playback()

    def _play_voice_preview(self) -> None:
        """Open the recorded/selected file in the default media player."""
        if not self.voice_lab_file_path or not self.voice_lab_file_path.exists():
            QMessageBox.information(self, "קובץ חסר", "אין קובץ להשמעה כרגע.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self.voice_lab_file_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.voice_lab_file_path)])
            else:
                subprocess.Popen(["xdg-open", str(self.voice_lab_file_path)])
        except Exception as exc:
            QMessageBox.warning(self, "השמעה נכשלה", f"לא ניתן להשמיע את הקובץ:\n{exc}")

    def _toggle_voice_preview(self) -> None:
        """Play/pause the recorded file inline using QMediaPlayer."""
        if not self.voice_lab_file_path or not self.voice_lab_file_path.exists():
            QMessageBox.information(self, "קובץ חסר", "אין קובץ להשמעה כרגע.")
            return
        try:
            if self.voice_playback_player is None:
                self.voice_playback_player = QMediaPlayer()
                self.voice_audio_output = QAudioOutput()
                self.voice_playback_player.setAudioOutput(self.voice_audio_output)
                self.voice_playback_player.mediaStatusChanged.connect(
                    lambda _: self._update_voice_play_button_icon()
                )
            self.voice_playback_player.setSource(QUrl.fromLocalFile(str(self.voice_lab_file_path)))
            if self.voice_playback_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.voice_playback_player.pause()
            else:
                self.voice_playback_player.play()
            self._update_voice_play_button_icon()
        except Exception as exc:
            QMessageBox.warning(self, "השמעה נכשלה", f"לא ניתן להשמיע את הקובץ:\n{exc}")

    def _stop_voice_playback(self) -> None:
        if self.voice_playback_player and self.voice_playback_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            try:
                self.voice_playback_player.stop()
            except Exception:
                pass
        self._update_voice_play_button_icon(reset=True)

    def _update_voice_play_button_icon(self, reset: bool = False) -> None:
        btn = getattr(self, "voice_lab_play_btn", None)
        if not btn:
            return
        if reset or not self.voice_playback_player or self.voice_playback_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            btn.setText("Play Preview")
        else:
            btn.setText("Pause")

    # --- UI helpers --------------------------------------------------
    def _card_widget(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        return frame

    def _wrap_scroll_area(self, widget: QWidget, widget_resizable: bool = True) -> QScrollArea:
        """
        Wrap a widget in a scroll area with predictable vertical scrolling.

        We force widget-resizable mode and an expanding container so that tall
        content grows to its natural height and scrollbars appear as needed.
        """
        area = SmoothScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Ensure the inner widget is allowed to expand vertically
        policy = widget.sizePolicy()
        policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        widget.setSizePolicy(policy)

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        layout.addStretch(1)

        area.setWidget(container)
        area.verticalScrollBar().setSingleStep(12)

        min_width = widget.minimumWidth()
        if min_width > 0:
            area.setMinimumWidth(min_width)
        area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return area

    def _chat_font_options(self) -> List[Dict[str, object]]:
        options: List[Dict[str, object]] = []
        current_family = (self.settings.chat_font_family or "Assistant").strip()
        current_path = (getattr(self.settings, "chat_font_path", "") or "").strip()
        current_family_lower = current_family.lower()
        selected_index = -1

        def add_option(label: str, family: str, path: str) -> None:
            nonlocal selected_index
            option = {
                "label": label,
                "family": family,
                "path": path,
            }
            if path:
                is_selected = path == current_path
            else:
                is_selected = not current_path and family.lower() == current_family_lower
            if is_selected:
                option["selected"] = True
                if selected_index == -1:
                    selected_index = len(options)
            options.append(option)

        # System fonts
        seen_families = set()
        for family in SYSTEM_CHAT_FONTS:
            clean_family = family.strip()
            if not clean_family:
                continue
            seen_families.add(clean_family.lower())
            add_option(f"{clean_family} (מערכת)", clean_family, "")

        if not current_path and current_family_lower not in seen_families:
            add_option(current_family or "Assistant", current_family or "Assistant", "")

        if self.font_library_dir.exists():
            font_files: List[Path] = []
            for pattern in ("*.ttf", "*.otf", "*.ttc"):
                font_files.extend(sorted(self.font_library_dir.glob(pattern)))
            for font_file in font_files:
                families = self._font_families_from_file(font_file)
                if not families:
                    continue
                family = families[0]
                label = f"{font_file.stem} ({family})"
                add_option(label, family, str(font_file))

        if not options:
            add_option("Assistant (מערכת)", "Assistant", "")

        # Ensure at least one item marked selected
        if selected_index == -1 and options:
            options[0]["selected"] = True
        return options

    def _font_families_from_file(self, font_path: Path) -> List[str]:
        key = str(font_path)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        if not font_path.exists():
            self._font_cache[key] = []
            return []
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            families: List[str] = []
        else:
            families = QFontDatabase.applicationFontFamilies(font_id)
        self._font_cache[key] = families
        return families

    def _resolve_chat_font(self) -> QFont:
        font_path = getattr(self.settings, "chat_font_path", "") or ""
        family = self.settings.chat_font_family or "Assistant"
        size = int(getattr(self.settings, "chat_font_size", 13) or 13)
        if font_path:
            families = self._font_families_from_file(Path(font_path))
            if families:
                family = families[0]
        font = QFont(family, size)
        return font

    def resizeEvent(self, event: QResizeEvent) -> None:  # pragma: no cover - GUI runtime
        super().resizeEvent(event)
        self._update_content_layout_mode()

    def _update_content_layout_mode(self) -> None:
        if not hasattr(self, "content_splitter"):
            return
        available_width = self.width()
        target = Qt.Orientation.Horizontal if available_width >= 1350 else Qt.Orientation.Vertical
        if self.content_splitter.orientation() != target:
            self.content_splitter.setOrientation(target)

    def showEvent(self, event: QShowEvent) -> None:  # pragma: no cover - GUI runtime
        super().showEvent(event)
        if not self._geometry_restored:
            self._geometry_restored = True
            self._restore_window_geometry()
            self._restore_splitter_sizes()
        self._enforce_control_panel_bounds()

    def closeEvent(self, event: QCloseEvent) -> None:  # pragma: no cover - GUI runtime
        try:
            self._persist_window_layout()
            self._persist_chat_preferences()
        except Exception as exc:  # pragma: no cover - best effort only
            self.logger.warning("Failed to persist window layout: %s", exc)
        super().closeEvent(event)

    def _restore_window_geometry(self) -> None:
        """Restore window geometry and state from saved preferences."""
        geo_hex = getattr(self.settings, "main_window_geometry", "") or ""
        if geo_hex:
            try:
                geo_bytes = QByteArray.fromHex(geo_hex.encode("ascii"))
                if not geo_bytes.isEmpty():
                    self.restoreGeometry(geo_bytes)
            except Exception as exc:
                self.logger.warning("Invalid main_window_geometry preference: %s", exc)

        state_hex = getattr(self.settings, "main_window_state", "") or ""
        if state_hex:
            try:
                state_bytes = QByteArray.fromHex(state_hex.encode("ascii"))
                if not state_bytes.isEmpty():
                    self.restoreState(state_bytes)
            except Exception as exc:
                self.logger.warning("Invalid main_window_state preference: %s", exc)

    def _restore_splitter_sizes(self) -> None:
        """Restore splitter sizes or fall back to defaults."""
        def _restore_state(splitter: Optional[QSplitter], hex_value: str) -> bool:
            if not splitter or not hex_value:
                return False
            try:
                data = QByteArray.fromHex(hex_value.encode("ascii"))
                if data.isEmpty():
                    return False
                return splitter.restoreState(data)
            except Exception as exc:
                self.logger.debug("Unable to restore splitter state: %s", exc)
                return False

        def _apply_sizes(splitter: Optional[QSplitter], values: object) -> bool:
            if not splitter or not isinstance(values, (list, tuple)):
                return False
            try:
                parsed = [max(48, int(v)) for v in values if isinstance(v, (int, float))]
            except Exception:
                return False
            if not parsed:
                return False
            splitter.setSizes(parsed)
            return True

        # Try to restore from persisted preferences; fall back to safe defaults below
        applied_main = _apply_sizes(self.main_splitter, getattr(self.settings, "main_splitter_sizes", []))
        applied_content = _apply_sizes(self.content_splitter, getattr(self.settings, "content_splitter_sizes", []))

        # Prefer full state restore if available (includes handle positions)
        if not applied_main:
            applied_main = _restore_state(self.main_splitter, getattr(self.settings, "main_splitter_state", ""))
        if not applied_content:
            applied_content = _restore_state(self.content_splitter, getattr(self.settings, "content_splitter_state", ""))

        # If no explicit splitter sizes were stored, respect a persisted right panel width
        if not applied_content and hasattr(self, "content_splitter"):
            right_pref = getattr(self.settings, "right_panel_width", None)
            if isinstance(right_pref, (int, float)):
                right_target = max(300, min(360, int(right_pref)))
                sizes = self.content_splitter.sizes()
                total = sum(sizes) or max(self.width(), right_target * 2)
                left_target = max(220, total - right_target)
                self.content_splitter.setSizes([left_target, right_target])
                applied_content = True

        def _is_invalid_content_split() -> bool:
            if not self.content_splitter:
                return True
            sizes = self.content_splitter.sizes()
            if len(sizes) < 2:
                return True
            left, right = sizes[0], sizes[1]
            total = sum(sizes) or 1
            # Only treat as invalid if clearly broken
            return min(left, right) < 240 or total < 500

        def _is_invalid_main_split() -> bool:
            if not self.main_splitter:
                return True
            sizes = self.main_splitter.sizes()
            if len(sizes) < 2:
                return True
            left, rest = sizes[0], sizes[1]
            total = sum(sizes) or 1
            return min(left, rest) < 80 or total < 250

        if (not applied_main or not applied_content) or _is_invalid_content_split() or _is_invalid_main_split():
            self._apply_default_splitter_sizes()

        self._enforce_control_panel_bounds()
        self._ensure_sidebar_width()

    def _apply_default_splitter_sizes(self) -> None:
        """
        Prioritize the Center Workspace.
        Left Panel: small (~230px).
        Right Panel: capped (~340px) for forms.
        Center Panel: takes remaining space.
        """
        total_width = self.width()

        # Define ideal widths for side panels
        left_width = 230
        right_width = 340  # Keep the right rail compact (max ~360px)

        # Calculate center
        center_width = total_width - left_width - right_width

        # Safety check: ensure center has at least some space
        if center_width < 100:
            center_width = total_width // 3
            right_width = total_width // 3
            left_width = total_width // 3

        # Apply to Content Splitter (Center vs Right)
        if self.content_splitter:
            # Note: content_splitter holds [Workspace, Control_Panel]
            self.content_splitter.setSizes([center_width, right_width])

        # Apply to Main Splitter (Left vs (Center+Right))
        if self.main_splitter:
            # Note: main_splitter holds [Projects, Content_Splitter]
            self.main_splitter.setSizes([left_width, center_width + right_width])

    def _enforce_control_panel_bounds(self) -> None:
        """Keep the control panel within sensible bounds without hard caps."""
        if not hasattr(self, "content_splitter"):
            return

        sizes = self.content_splitter.sizes()
        if len(sizes) < 2:
            return

        right_width = sizes[1]
        total = sum(sizes)
        if total <= 0:
            return

        min_right = 300
        max_right = 360
        target_right = right_width

        if right_width < min_right:
            target_right = min_right
        elif right_width > max_right:
            target_right = max_right

        if target_right != right_width:
            target_left = max(220, total - target_right)
            self.content_splitter.setSizes([target_left, target_right])

    def _ensure_sidebar_width(self) -> None:
        """Force a healthy right panel width even if saved state is bad."""
        if not self.content_splitter:
            return
        sizes = self.content_splitter.sizes()
        if len(sizes) < 2:
            return
        total = sum(sizes) or 1
        right_width = sizes[1]
        min_right = 300
        max_right = 360

        if right_width < min_right or right_width > max_right:
            target_right = max(min_right, min(max_right, int(total * 0.32)))
            target_left = max(240, total - target_right)
            self.content_splitter.setSizes([target_left, target_right])

    def _schedule_layout_save(self) -> None:
        """Debounce layout saves so slight drags still persist."""
        if not hasattr(self, "_layout_save_timer"):
            self._layout_save_timer = QTimer(self)
            self._layout_save_timer.setSingleShot(True)
            self._layout_save_timer.timeout.connect(self._persist_window_layout)
        # restart debounce timer (200ms)
        self._layout_save_timer.start(200)

    def _persist_window_layout(self) -> None:
        """Persist the current window geometry/splitter sizes to preferences."""
        payload: Dict[str, object] = {}

        try:
            geometry_bytes = self.saveGeometry()
            if not geometry_bytes.isEmpty():
                payload["main_window_geometry"] = bytes(geometry_bytes.toHex()).decode("ascii")
        except Exception as exc:
            self.logger.debug("Unable to capture window geometry: %s", exc)

        try:
            state_bytes = self.saveState()
            if not state_bytes.isEmpty():
                payload["main_window_state"] = bytes(state_bytes.toHex()).decode("ascii")
        except Exception as exc:
            self.logger.debug("Unable to capture window state: %s", exc)

        if getattr(self, "main_splitter", None):
            payload["main_splitter_sizes"] = self.main_splitter.sizes()
            try:
                state_bytes = self.main_splitter.saveState()
                if not state_bytes.isEmpty():
                    payload["main_splitter_state"] = bytes(state_bytes.toHex()).decode("ascii")
            except Exception as exc:
                self.logger.debug("Unable to capture main splitter state: %s", exc)
        if getattr(self, "content_splitter", None):
            content_sizes = self.content_splitter.sizes()
            payload["content_splitter_sizes"] = content_sizes
            if len(content_sizes) >= 2:
                # Track right rail width explicitly for persistence
                payload["right_panel_width"] = max(300, min(360, int(content_sizes[1])))
            try:
                c_state = self.content_splitter.saveState()
                if not c_state.isEmpty():
                    payload["content_splitter_state"] = bytes(c_state.toHex()).decode("ascii")
            except Exception as exc:
                self.logger.debug("Unable to capture content splitter state: %s", exc)

        if payload:
            self.settings.save_ui_preferences(payload)

    def _persist_chat_preferences(self) -> None:
        """Persist chat appearance preferences so font/size/theme survive restarts."""
        payload: Dict[str, object] = {
            "chat_font_family": getattr(self.settings, "chat_font_family", None),
            "chat_font_path": getattr(self.settings, "chat_font_path", ""),
            "chat_font_size": getattr(self.settings, "chat_font_size", None),
            "chat_theme": getattr(self.settings, "chat_theme", None),
            "chat_banner_brightness": getattr(self.settings, "chat_banner_brightness", None),
            "chat_bg_theme": getattr(self.settings, "chat_bg_theme", None),
        }
        filtered = {k: v for k, v in payload.items() if v not in (None, "")}
        if filtered:
            self.settings.save_ui_preferences(filtered)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "chat_input", None) and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                send_on_enter = getattr(self, "send_on_enter_cb", None)
                shift_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                if send_on_enter and send_on_enter.isChecked() and not shift_pressed:
                    self._send_chat_message()
                    return True
        return super().eventFilter(obj, event)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "section-title")
        return label

    def _helper_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "helper")
        label.setWordWrap(True)
        return label

    def _add_stat_chip(self, container: QHBoxLayout, title: str) -> QLabel:
        frame = self._card_widget()
        frame.setFixedHeight(60)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        label = QLabel(title)
        label.setStyleSheet("color:#64748b;font-size:11px;")
        value = QLabel("0")
        value.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(label)
        layout.addWidget(value)
        container.addWidget(frame)
        return value

    def _inline_row(self, label: str, widget: QWidget, button: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(widget, 1)
        row.addWidget(button)
        return row

    def _select_voice_sample(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "בחר קובץ קול (עד 60 שניות)",
            str(self.settings.output_base_dir),
            "Audio Files (*.wav *.mp3)",
        )
        if not file_path:
            return
        self.voice_lab_file_path = Path(file_path)
        if self.voice_lab_file_label:
            self.voice_lab_file_label.setText(f"נבחר: {self.voice_lab_file_path.name}")
        if self.voice_lab_status_label:
            self.voice_lab_status_label.setText("מוכן לשיכפול קולות.")
        if hasattr(self, "voice_lab_clone_btn") and self.voice_lab_clone_btn:
            self.voice_lab_clone_btn.setEnabled(True)
        self._set_voice_lab_state("review")

    def _refresh_voice_profiles_combo(self, select_profile: Optional[str] = None) -> None:
        if not hasattr(self, "voice_combo"):
            return
        current = self.voice_combo.currentText() if self.voice_combo.count() else ""
        self.voice_manager._load()
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        for name in (
            self.voice_manager.profile_names
            or [self.voice_manager.default_profile_name]
        ):
            self.voice_combo.addItem(name)
        target_profile = select_profile or current
        target_index = self.voice_combo.findText(target_profile)
        if target_index >= 0:
            self.voice_combo.setCurrentIndex(target_index)
        self.voice_combo.blockSignals(False)

    def _refresh_voice_quota(self) -> None:
        if not self.voice_lab_quota_label or not self.voice_lab_service:
            return
        try:
            quota = self.voice_lab_service.get_subscription_quota()
            remaining = quota["character_limit"] - quota["character_count"]
            remaining = max(0, remaining)
            self.voice_lab_quota_label.setText(
                f"נותרו {remaining:,} / {quota['character_limit']:,} תווים החודש"
            )
        except Exception as exc:  # pragma: no cover - UI only
            self.voice_lab_quota_label.setText(f"שגיאה בשליפת מכסה: {exc}")

    def _handle_clone_voice(self) -> None:
        if not self.voice_lab_service:
            QMessageBox.warning(
                self,
                "API Key חסר",
                "נדרש ELEVENLABS_API_KEY כדי לשכפל קול.",
            )
            return
        if not self.settings.elevenlabs_api_key:
            QMessageBox.warning(
                self,
                "API Key חסר",
                "נדרש ELEVENLABS_API_KEY כדי לשכפל קול.",
            )
            return
        if not self.voice_lab_file_path or not self.voice_lab_file_path.exists():
            QMessageBox.warning(
                self,
                "קובץ חסר",
                "בחר/י קובץ WAV או MP3 (עד 60 שניות) לפני השיכפול.",
            )
            return

        self.voice_lab_clone_btn.setEnabled(False)
        try:
            voice_id = self.voice_lab_service.clone_instant_voice(
                self.voice_lab_file_path, voice_name="Custom Voice"
            )
            self.voice_lab_service.save_custom_voice_profile(voice_id)
            self._refresh_voice_profiles_combo(select_profile="Custom")
            if self.voice_lab_status_label:
                self.voice_lab_status_label.setText(
                    f"✅ קול שוכפל ונשמר כפרופיל 'Custom' (ID: {voice_id[:10]}...)"
                )
            QMessageBox.information(
                self,
                "Voice Cloned",
                "הקול שוכפל בהצלחה ונשמר כפרופיל 'Custom' ב-voice_profiles.json.",
            )
        except Exception as exc:
            if self.voice_lab_status_label:
                self.voice_lab_status_label.setText(f"❌ שגיאה: {exc}")
            QMessageBox.critical(self, "כישלון בשיכפול קול", str(exc))
        finally:
            self.voice_lab_clone_btn.setEnabled(True)
            self._refresh_voice_quota()

    def _predict_run_dir(self, metadata: Dict, base_dir: Path) -> Path:
        date_str = metadata.get("date") or datetime.now().strftime("%Y-%m-%d")
        
        # Check for custom project name first
        custom_name = ""
        if hasattr(self, "custom_project_name"):
            custom_name = self.custom_project_name.text().strip()
        
        if custom_name:
            # Use custom project name
            slug = _slugify(custom_name)
        else:
            # Fall back to topic-based name
            topic = metadata.get("topic") or "project"
            slug = _slugify(str(topic))
        
        run_dir = base_dir / f"{date_str}_{slug}"
        return run_dir

    def _on_custom_project_name_changed(self, text: str) -> None:
        """Keep metadata and output preview in sync with the project name field."""
        topic = text.strip() or self.current_metadata.get("topic", "")
        if topic:
            self.current_metadata["topic"] = topic
            self._update_metadata_preview()
        try:
            base_dir = Path(self.output_dir_edit.text().strip() or self.settings.output_base_dir)
        except Exception:
            base_dir = self.settings.output_base_dir
        run_dir = self._predict_run_dir(self.current_metadata, base_dir)
        label = getattr(self, "run_dir_preview", None)
        if isinstance(label, QLabel):
            label.setText(f"נתיב פלט צפוי: {run_dir}")

    def _handle_output_mode_change(self) -> None:
        """Sync include_visuals/export_ppt based on the output mode combo."""
        if not hasattr(self, "output_mode_combo") or self.output_mode_combo is None:
            return
        mode = self.output_mode_combo.currentData() or "video_audio"
        if mode == "audio":
            self.include_visuals_cb.setChecked(False)
            self.export_ppt_cb.setChecked(False)
        elif mode == "presentation":
            self.include_visuals_cb.setChecked(False)
            self.export_ppt_cb.setChecked(True)
        elif mode == "video_audio":
            self.include_visuals_cb.setChecked(True)
            self.export_ppt_cb.setChecked(False)
        else:  # "all" or fallback
            self.include_visuals_cb.setChecked(True)
            self.export_ppt_cb.setChecked(True)
        # Persist user choice so next launch keeps visuals preference
        try:
            self.settings.save_ui_preferences(
                {
                    "output_mode": mode,
                    "include_visuals": bool(self.include_visuals_cb.isChecked()),
                }
            )
        except Exception:
            # Best-effort persistence; do not block UI
            pass

    def _set_voice_lab_state(self, state: str) -> None:
        """State machine: idle -> recording -> review."""
        self.voice_lab_state = state
        if state == "idle":
            if self.voice_lab_timer.isActive():
                self.voice_lab_timer.stop()
            self.voice_lab_record_start = None
            self.voice_lab_timer_label.setText("00:00")
            self.voice_lab_timer_label.setVisible(False)
            if self.voice_lab_record_controls:
                self.voice_lab_record_controls.setVisible(True)
            if self.voice_lab_review_controls:
                self.voice_lab_review_controls.setVisible(False)
            self.voice_lab_trash_btn.setVisible(True)
            if self.voice_lab_mic_btn:
                self.voice_lab_mic_btn.setChecked(False)
                self.voice_lab_mic_btn.setVisible(True)
                self.voice_lab_mic_btn.setText("Record")
                self.voice_lab_mic_btn.setStyleSheet("background-color: #25D366;")
            if self.voice_lab_stop_btn:
                self.voice_lab_stop_btn.setEnabled(False)
            self._stop_voice_playback()
        elif state == "recording":
            self.voice_lab_record_start = time.time()
            self.voice_lab_timer.start(1000)
            self.voice_lab_timer_label.setVisible(True)
            if self.voice_lab_record_controls:
                self.voice_lab_record_controls.setVisible(True)
            if self.voice_lab_review_controls:
                self.voice_lab_review_controls.setVisible(False)
            self.voice_lab_trash_btn.setVisible(True)
            if self.voice_lab_mic_btn:
                self.voice_lab_mic_btn.setVisible(True)
                self.voice_lab_mic_btn.setChecked(True)
                self.voice_lab_mic_btn.setText("Recording...")
                self.voice_lab_mic_btn.setStyleSheet("background-color: #ef4444;")
            if self.voice_lab_stop_btn:
                self.voice_lab_stop_btn.setEnabled(True)
        elif state == "review":
            if self.voice_lab_timer.isActive():
                self.voice_lab_timer.stop()
            self.voice_lab_timer_label.setVisible(False)
            if self.voice_lab_record_controls:
                self.voice_lab_record_controls.setVisible(False)
            if self.voice_lab_review_controls:
                self.voice_lab_review_controls.setVisible(True)
            self.voice_lab_trash_btn.setVisible(True)
            if self.voice_lab_mic_btn:
                self.voice_lab_mic_btn.setChecked(False)
                self.voice_lab_mic_btn.setVisible(False)
            if self.voice_lab_stop_btn:
                self.voice_lab_stop_btn.setEnabled(False)
        self._update_voice_play_button_icon(reset=True)

    def _tick_voice_timer(self) -> None:
        if not self.voice_lab_record_start:
            self.voice_lab_timer_label.setText("00:00")
            return
        elapsed = int(time.time() - self.voice_lab_record_start)
        mins, secs = divmod(elapsed, 60)
        self.voice_lab_timer_label.setText(f"{mins:02d}:{secs:02d}")

    def _handle_voice_profile_change(self) -> None:
        """Handle voice profile selection change and sync TTS provider."""
        if not hasattr(self, "voice_combo"):
            return
        profile_name = self.voice_combo.currentText()
        
        # Get the profile's preferred provider
        profile = self.voice_manager.get(profile_name)
        profile_provider = getattr(profile, 'provider', 'azure')
        
        # Auto-sync TTS provider if profile has a specific provider
        if hasattr(self, "tts_provider_combo"):
            current_provider = self.tts_provider_combo.currentData()
            if profile_provider != current_provider:
                # Find and select the matching provider
                idx = self.tts_provider_combo.findData(profile_provider)
                if idx >= 0:
                    self.tts_provider_combo.setCurrentIndex(idx)
                    provider_name = "ElevenLabs" if profile_provider == "elevenlabs" else "Azure Neural TTS"
                    self._append_log(f"פרופיל '{profile_name}' - ספק דיבור שונה אוטומטית ל-{provider_name}")

    def _handle_tts_provider_change(self) -> None:
        """Handle TTS provider selection change."""
        if not hasattr(self, "tts_provider_combo"):
            return
        provider = self.tts_provider_combo.currentData()
        # Save preference
        self.settings.save_ui_preferences({"default_tts_provider": provider})
        # Update status
        provider_name = "ElevenLabs" if provider == "elevenlabs" else "Azure Neural TTS"
        self._append_log(f"ספק דיבור שונה ל-{provider_name}")
        # Show/hide ElevenLabs voice selector button (dynamic lookup to avoid None)
        btn = getattr(self, "elevenlabs_voices_btn", None) or self.findChild(QPushButton, "elevenlabs_voices_btn")
        is_eleven = provider == "elevenlabs"
        if btn:
            btn.setVisible(is_eleven)
        azure_combo = getattr(self, "azure_voice_combo", None)
        if azure_combo:
            azure_combo.setVisible(not is_eleven)
        
        # Suggest matching voice profile if available
        if hasattr(self, "voice_combo"):
            current_profile = self.voice_combo.currentText()
            profile = self.voice_manager.get(current_profile)
            profile_provider = getattr(profile, 'provider', 'azure')
            
            # If current profile doesn't match provider, suggest a matching one
            if profile_provider != provider:
                for name in self.voice_manager.profile_names:
                    p = self.voice_manager.get(name)
                    if getattr(p, 'provider', 'azure') == provider:
                        idx = self.voice_combo.findText(name)
                        if idx >= 0:
                            self.voice_combo.blockSignals(True)
                            self.voice_combo.setCurrentIndex(idx)
                            self.voice_combo.blockSignals(False)
                            break

    def _open_elevenlabs_voice_selector(self) -> None:
        """Open the ElevenLabs voice selector dialog."""
        from .dialogs import ElevenLabsVoiceSelectorDialog
        dialog = ElevenLabsVoiceSelectorDialog(self.settings, parent=self)
        if dialog.exec():
            selected = dialog.get_selected_voices()
            if selected:
                # Store the selected voices for use in pipeline
                self._elevenlabs_voices = selected
                self.settings.elevenlabs_voice_overrides = selected
                overrides = getattr(self.settings, "elevenlabs_voice_overrides", {})
                if overrides:
                    details = ", ".join(
                        f"{speaker}→{cfg.get('voice_id', 'ברירת מחדל')[:8]}"
                        for speaker, cfg in overrides.items()
                    )
                    self._append_log(f"נשמרו קולות ElevenLabs מותאמים: {details}")

    # --- Actions -----------------------------------------------------
    def _send_template_prompt(self, template: str) -> None:
        self.chat_input.setPlainText(template)
        self._send_chat_message()

    def _open_onboarding_wizard(self) -> None:
        wizard = OnboardingWizard(self)
        wizard.exec()

    def _send_chat_message(self) -> None:
        """Send a chat message to the AI assistant."""
        # Check if already busy
        if (self.chat_worker and self.chat_worker.isRunning()) or (
            self.seed_worker and self.seed_worker.isRunning()
        ):
            self.logger.debug("[_send_chat_message] Skipped - worker already running")
            return
            
        text = self.chat_input.toPlainText().strip()
        if not text:
            self.logger.debug("[_send_chat_message] Skipped - empty message")
            return
            
        model_choice = self.chat_model_combo.currentData()
        self.logger.info("[_send_chat_message] Sending message (%d chars) to %s", len(text), model_choice)
        
        self._append_chat_bubble("אני", text, is_user=True)
        self.chat_input.clear()
        self._sync_materials_to_session()
        self._set_chat_busy(True)
        
        try:
            self.chat_worker = ChatWorker(self.chat_session, text, str(model_choice))
            self.chat_worker.result.connect(self._handle_chat_result)
            self.chat_worker.error.connect(self._handle_chat_error)
            self.chat_worker.finished.connect(self._chat_finished)
            self.chat_worker.start()
            self.logger.debug("[_send_chat_message] ChatWorker started successfully")
        except Exception as e:
            self.logger.error("[_send_chat_message] Failed to start ChatWorker: %s", e)
            self._set_chat_busy(False)
    
    def _trigger_ai_image_enrichment(self) -> None:
        """
        Trigger AI to help enrich metadata with visual concepts for better images.
        
        This function:
        1. Validates chat session and worker availability
        2. Prepares the chat UI
        3. Sends an enrichment prompt to the AI
        4. Handles all errors with proper logging
        """
        start_time = time.time()
        self.logger.info("[_trigger_ai_image_enrichment] ========== STARTING ==========")
        self.logger.debug("[_trigger_ai_image_enrichment] Call stack:\n%s", 
                         ''.join(traceback.format_stack()[-5:]))
        self._log("🎨 מתחיל תהליך העשרת תמונות...")
        
        try:
            # Check if AI is busy
            if hasattr(self, 'chat_worker') and self.chat_worker and self.chat_worker.isRunning():
                self.logger.warning("[_trigger_ai_image_enrichment] ChatWorker already running")
                QMessageBox.information(
                    self, "המתן", "ה-AI עסוק כרגע. נסה שוב בעוד רגע."
                )
                return
            if hasattr(self, 'seed_worker') and self.seed_worker and self.seed_worker.isRunning():
                self.logger.warning("[_trigger_ai_image_enrichment] SeedWorker already running")
                QMessageBox.information(
                    self, "המתן", "ה-AI עסוק כרגע. נסה שוב בעוד רגע."
                )
                return
            
            # Ensure chat session is ready
            if not hasattr(self, "chat_session") or not self.chat_session:
                self.logger.warning("[_trigger_ai_image_enrichment] Chat session not initialized, attempting recovery")
                try:
                    from src.metadata.chat import MetadataChatSession
                    self.chat_session = MetadataChatSession(self.settings)
                    self.logger.info("[_trigger_ai_image_enrichment] Chat session re-initialized successfully")
                except Exception as e:
                    error_msg = f"Chat Session לא מאותחל ולא ניתן לאתחול: {e}"
                    self.logger.error("[_trigger_ai_image_enrichment] %s\n%s", error_msg, traceback.format_exc())
                    self._log(f"⚠️ שגיאה: {error_msg}")
                    QMessageBox.warning(self, "שגיאה", f"תקלה פנימית: Chat Session אינו זמין.\n{str(e)}")
                    return
            
            # Verify session has required methods
            if not hasattr(self.chat_session, 'send'):
                error_msg = "Chat session missing 'send' method"
                self.logger.error("[_trigger_ai_image_enrichment] %s", error_msg)
                self._log(f"⚠️ שגיאה: {error_msg}")
                QMessageBox.warning(self, "שגיאה", "תקלה פנימית: Chat Session לא תקין.")
                return
        
            # Specialized prompt for image enrichment
            enrichment_prompt = """🎨 עזרת AI להעשרת מטא-דאטה לתמונות

אני רוצה ליצור תמונות איכותיות עבור הפודקאסט שלי.
עזור לי להעשיר את המטא-דאטה עם מידע שיעזור ליצור תמונות טובות יותר.

בבקשה:
1. שאל אותי 3-5 שאלות על התוכן שלי כדי להבין טוב יותר את הנושא
2. הצע לי מושגים מרכזיים (key_concepts) שמתאימים לויזואליזציה  
3. הצע רעיונות לתמונות או דיאגרמות שיכולות להמחיש את התוכן
4. עדכן את המטא-דאטה עם המידע החדש

התחל בשאלות!"""
            
            # Get model choice, default to azure if not set
            model_choice = "azure"
            if hasattr(self, 'chat_model_combo') and self.chat_model_combo:
                model_choice = self.chat_model_combo.currentData() or "azure"
            
            self.logger.info("[_trigger_ai_image_enrichment] Using model: %s", model_choice)
            
            # Ensure window is active and visible first
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()
            
            # Show visual feedback that we're starting
            self._log("⏳ מכין את הצ'אט להעשרת תמונות...")
            
            # Ensure UI is ready and visible
            chat_card_ready = False
            if hasattr(self, "chat_card") and self.chat_card:
                self.chat_card.setVisible(True)
                self.chat_card.show()
                chat_card_ready = self.chat_card.isVisible()
                self.logger.debug("[_trigger_ai_image_enrichment] chat_card visible: %s", chat_card_ready)
                self._log("✅ כרטיס הצ'אט מוכן")
                
                # Scroll the workspace scroll area to show chat
                if hasattr(self, "workspace_scroll") and self.workspace_scroll:
                    self.logger.debug("[_trigger_ai_image_enrichment] Scrolling to chat_card")
                    self.workspace_scroll.ensureWidgetVisible(self.chat_card)
                    scrollbar = self.workspace_scroll.verticalScrollBar()
                    if scrollbar:
                        chat_pos = self.chat_card.mapTo(self.workspace_scroll.widget(), self.chat_card.rect().topLeft())
                        scrollbar.setValue(max(0, chat_pos.y() - 50))
                    QApplication.processEvents()
            else:
                self.logger.warning("[_trigger_ai_image_enrichment] chat_card not found!")
                self._log("⚠️ לא נמצא כרטיס צ'אט")
            
            # Focus chat input
            chat_input_ready = False
            if hasattr(self, "chat_input") and self.chat_input:
                self.chat_input.setFocus()
                self.chat_input.activateWindow()
                chat_input_ready = self.chat_input.hasFocus()
                self.logger.debug("[_trigger_ai_image_enrichment] chat_input focused: %s", chat_input_ready)
            else:
                self.logger.warning("[_trigger_ai_image_enrichment] chat_input not found!")
                
            # Force multiple UI updates
            QApplication.processEvents()
            QTimer.singleShot(100, lambda: QApplication.processEvents())
            
            # Add the user message to chat display
            self._append_chat_bubble("אני", enrichment_prompt, is_user=True)
            self.logger.debug("[_trigger_ai_image_enrichment] User message added to chat")
            
            # Sync materials and start AI
            self._sync_materials_to_session()
            self._set_chat_busy(True)
            
            # Create and start the chat worker with explicit error handling
            self.logger.info("[_trigger_ai_image_enrichment] Creating ChatWorker...")
            self._log("📡 מתחבר ל-AI...")
            try:
                self.chat_worker = ChatWorker(self.chat_session, enrichment_prompt, str(model_choice))
                self.logger.debug("[_trigger_ai_image_enrichment] ChatWorker created successfully")
            except Exception as e:
                error_msg = f"Failed to create ChatWorker: {e}"
                self.logger.error("[_trigger_ai_image_enrichment] %s\n%s", error_msg, traceback.format_exc())
                self._log(f"❌ שגיאה: {error_msg}")
                self._set_chat_busy(False)
                QMessageBox.critical(self, "שגיאה", f"לא ניתן ליצור ChatWorker:\n{e}")
                return
            
            # Connect signals
            self.chat_worker.result.connect(self._handle_chat_result)
            self.chat_worker.error.connect(self._handle_chat_error)
            self.chat_worker.finished.connect(self._chat_finished)
            
            # Start the worker and verify it started
            self.logger.info("[_trigger_ai_image_enrichment] Starting ChatWorker...")
            self.chat_worker.start()
            
            # Give the worker a moment to start
            QApplication.processEvents()
            time.sleep(0.1)
            
            # Verify worker is actually running
            if not self.chat_worker.isRunning():
                error_msg = "ChatWorker failed to start - thread not running"
                self.logger.error("[_trigger_ai_image_enrichment] %s", error_msg)
                self._log(f"❌ שגיאה: {error_msg}")
                self._set_chat_busy(False)
                QMessageBox.critical(self, "שגיאה", "ChatWorker לא התחיל. בדוק את הלוגים לפרטים נוספים.")
                return
            
            self.logger.info("[_trigger_ai_image_enrichment] ChatWorker started successfully")
            
            # Log the action
            self._append_log("🎨 AI helper triggered for image metadata enrichment")
            self._log("🎨 בקשה נשלחה ל-AI, ממתין לתשובה...")
            
        except Exception as e:
            error_details = traceback.format_exc()
            self.logger.error("[_trigger_ai_image_enrichment] Error: %s\n%s", e, error_details)
            self._log(f"❌ שגיאה בהפעלת AI Helper: {e}")
            self._set_chat_busy(False)
            QMessageBox.critical(self, "שגיאה", f"אירעה שגיאה בהפעלת הצ'אט:\n{e}\n\nפרטים נוספים בלוג.")
            
        finally:
            elapsed = time.time() - start_time
            self.logger.info("[_trigger_ai_image_enrichment] Completed in %.3fs", elapsed)

    def _append_chat_bubble(self, speaker: str, text: str, is_user: bool = None) -> None:
        """Add a chat bubble with alignment based on speaker (user vs AI)."""
        # Check if chat_history exists
        if not hasattr(self, "chat_history") or self.chat_history is None:
            self._append_log(f"[Chat] {speaker}: {text[:100]}...")
            return
        self._ensure_chat_area_resized()
        
        # Check scroll position before adding
        scrollbar = self.chat_history.verticalScrollBar()
        # If scrollbar is maxed out or close to it, we should scroll to bottom
        # Using a small tolerance (e.g. 20 pixels)
        was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 20)
        
        item = QListWidgetItem(f"{speaker}: {text}")
        
        # Determine if this is a user message based on speaker name
        if is_user is None:
            # User speakers: "אני", "You", "User", "משתמש"
            user_speakers = {"אני", "you", "user", "משתמש"}
            is_user = speaker.lower() in user_speakers or speaker == "אני"
        
        # User messages: RIGHT (teal color), AI messages: LEFT (purple color)
        if is_user:
            alignment = Qt.AlignmentFlag.AlignRight
        else:
            alignment = Qt.AlignmentFlag.AlignLeft
        
        item.setTextAlignment(alignment)
        self.chat_history.addItem(item)
        
        # Only scroll if we were at the bottom, OR if it's a user message (always show what I just sent)
        if was_at_bottom or is_user:
            self.chat_history.scrollToBottom()

    def _handle_chat_result(self, response: str, metadata: Dict[str, object]) -> None:
        """Handle successful AI chat response."""
        self.logger.debug("[_handle_chat_result] Received response (%d chars)", len(response))
        self.current_metadata = metadata or {}
        self._append_chat_bubble(APP_ASSISTANT_NAME, response, is_user=False)
        self._update_metadata_preview()

    def _handle_chat_error(self, message: str) -> None:
        """Handle AI chat error."""
        self.logger.error("[_handle_chat_error] Chat error: %s", message)
        self._append_chat_bubble(APP_ASSISTANT_NAME, f"שגיאה: {message}", is_user=False)

    def _chat_finished(self) -> None:
        """Called when chat worker completes (success or error)."""
        self.logger.debug("[_chat_finished] Chat worker completed")
        self._set_chat_busy(False)
        self.chat_worker = None
        
        # Save chat history after each interaction
        try:
            self._save_chat_to_history()
        except Exception as e:
            self.logger.warning("[_chat_finished] Failed to save chat history: %s", e)

    def _set_chat_busy(self, busy: bool) -> None:
        if busy:
            self._chat_busy_counter += 1
            # Add feedback
            if hasattr(self, "statusBar") and self.statusBar():
                self.statusBar().showMessage("🤔 ה-AI חושב...", 0)  # Permanent until cleared
            self._ensure_chat_area_resized()
            
            # Add thinking bubble if not present
            if hasattr(self, "chat_history") and self.chat_history:
                # Check scroll position
                scrollbar = self.chat_history.verticalScrollBar()
                was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 20)

                # Check if last item is already thinking (avoid duplicates)
                count = self.chat_history.count()
                if count == 0 or self.chat_history.item(count - 1).text() != "...":
                    item = QListWidgetItem("...")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)  # AI side
                    self.chat_history.addItem(item)
                    
                    if was_at_bottom:
                        self.chat_history.scrollToBottom()
                        
                    self._thinking_item = item
        else:
            self._chat_busy_counter = max(0, self._chat_busy_counter - 1)
            
            # Remove feedback
            if hasattr(self, "statusBar") and self.statusBar():
                self.statusBar().clearMessage()
            
            # Remove thinking bubble
            if hasattr(self, "chat_history") and hasattr(self, "_thinking_item") and self._thinking_item:
                row = self.chat_history.row(self._thinking_item)
                if row >= 0:
                    self.chat_history.takeItem(row)
                self._thinking_item = None

        enabled = self._chat_busy_counter == 0
        if hasattr(self, "chat_send_btn"):
            self.chat_send_btn.setEnabled(enabled)
        if hasattr(self, "chat_input"):
            self.chat_input.setEnabled(enabled)
        for btn in getattr(self, "template_buttons", []):
            btn.setEnabled(enabled)
        self._update_gallery_buttons()

    def _ensure_chat_area_resized(self) -> None:
        """Gently expand chat height once a conversation starts, respecting font size."""
        if self._chat_resized_once:
            return
        chat = getattr(self, "chat_history", None)
        if not chat:
            return
        metrics = chat.fontMetrics()
        line = max(16, metrics.lineSpacing())
        # Aim for ~14 lines visible, capped for large fonts
        target_max = min(640, int(line * 14 + 80))
        target_min = max(200, int(line * 10))
        changed = False
        if chat.minimumHeight() < target_min:
            chat.setMinimumHeight(target_min)
            changed = True
        if chat.maximumHeight() < target_max or chat.maximumHeight() == 16777215:
            chat.setMaximumHeight(target_max)
            changed = True
        if changed and hasattr(self, "chat_card") and self.chat_card:
            self.chat_card.setMinimumHeight(target_min + 40)
        if changed:
            self._chat_resized_once = True

    # --- System status bar -------------------------------------------------
    def _init_system_status_bar(self) -> None:
        """Initialize the bottom system status banner with live metrics."""
        banner_ready = all(
            widget is not None
            for widget in (self.system_status_banner, self._cpu_label, self._memory_label, self._battery_label, self._network_label)
        )
        if not banner_ready:
            self.logger.warning("[System Status] Banner widgets not ready")
            return

        self.logger.info("[System Status] Initializing system status banner")
        self._psutil_attempts += 1

        psutil_mod = self._load_psutil_module()
        if not psutil_mod:
            self.logger.warning("[System Status] psutil not available - will retry")
            for label in (self._cpu_label, self._memory_label, self._battery_label, self._network_label):
                if label:
                    label.setText("psutil חסר")
                    label.setStyleSheet("font-weight:600; color:#94a3b8; padding:0 8px;")
            if self.system_status_banner:
                tooltip = "psutil לא הותקן או לא נטען. התקן עם: pip install psutil"
                if self._psutil_last_error:
                    tooltip += f"\nשגיאה: {self._psutil_last_error}"
                self.system_status_banner.setToolTip(tooltip)
            if self.statusBar():
                msg = "psutil חסר – התקן psutil בסביבה (pip install psutil)"
                if self._psutil_last_error:
                    msg += f" ({self._psutil_last_error})"
                self.statusBar().showMessage(msg, 8000)

            # אל תרוץ בלי סוף: נסה פעמיים בלבד
            if self._psutil_attempts >= 2:
                self._psutil_retry_scheduled = False
                return

            if not self._psutil_retry_scheduled:
                self._psutil_retry_scheduled = True
                QTimer.singleShot(4000, self._init_system_status_bar)
            return
        self._psutil_mod = psutil_mod
        self._psutil_retry_scheduled = False

        self._system_metrics_timer = QTimer(self)
        self._system_metrics_timer.setInterval(2500)
        self._system_metrics_timer.timeout.connect(self._update_system_metrics)
        QTimer.singleShot(400, self._update_system_metrics)
        self._system_metrics_timer.start()
        self.logger.info("[System Status] System metrics timer started")

    def _status_label_style(self, severity: float) -> str:
        """Return a color style string based on severity (0=good, 1=bad)."""
        if severity < 0.5:
            color = "#34d399"  # green
        elif severity < 0.8:
            color = "#fbbf24"  # yellow
        else:
            color = "#f87171"  # red
        return f"padding:0 8px; font-weight:600; color:{color};"

    def _update_system_badge(
        self,
        cpu_text: Optional[str] = None,
        mem_text: Optional[str] = None,
        net_text: Optional[str] = None,
    ) -> None:
        """Render the compact system badge in the header."""
        if not self.system_badge_label:
            return
        if cpu_text:
            self._system_badge_values["cpu"] = cpu_text
        if mem_text:
            self._system_badge_values["mem"] = mem_text
        if net_text:
            self._system_badge_values["net"] = net_text
        badge_text = (
            f"{self._system_badge_values['cpu']}  |  "
            f"{self._system_badge_values['mem']}  |  "
            f"{self._system_badge_values['net']}"
        )
        self.system_badge_label.setText(badge_text)

    def _update_system_metrics(self) -> None:
        """Update system metrics (CPU, battery, network) in the status bar."""
        # Check if labels are initialized
        if not hasattr(self, '_cpu_label') or not self._cpu_label:
            self.logger.debug("[System Status] Labels not initialized yet")
            return
        if not (self._cpu_label and self._memory_label and self._battery_label and self._network_label):
            self.logger.debug("[System Status] Some labels are None")
            return
        
        # Try to import psutil
        psutil = self._psutil_mod or self._load_psutil_module()
        if not psutil:
            self.logger.debug("[System Status] psutil still missing during metrics update")
            for label in (self._cpu_label, self._memory_label, self._battery_label, self._network_label):
                if label:
                    label.setText("psutil חסר")
                    label.setStyleSheet("font-weight:600; color:#fbbf24; padding:0 8px;")
            return

        try:
            # CPU usage - first call with interval=None may return None, so use a small interval
            # Store last CPU value to avoid blocking
            if not hasattr(self, '_last_cpu_percent'):
                # First call - use small interval to get initial value
                cpu_usage = psutil.cpu_percent(interval=0.1)
                self._last_cpu_percent = cpu_usage if cpu_usage is not None else 0.0
            else:
                # Subsequent calls - non-blocking
                cpu_usage = psutil.cpu_percent(interval=None)
                if cpu_usage is None:
                    cpu_usage = self._last_cpu_percent
                else:
                    self._last_cpu_percent = cpu_usage
            
            if cpu_usage < 0:
                cpu_usage = 0.0
            
            cpu_display = f"🧠 {cpu_usage:.0f}%"
            if self._cpu_label:
                self._cpu_label.setText(cpu_display)
                self._cpu_label.setStyleSheet(self._status_label_style(min(cpu_usage / 100.0, 1.0)))
            self._update_system_badge(cpu_text=f"CPU {cpu_usage:.0f}%")
        except Exception as e:
            self.logger.warning("[System Status] CPU metric error: %s", e, exc_info=True)
            if self._cpu_label:
                self._cpu_label.setText("🧠 --")
                self._cpu_label.setStyleSheet(self._status_label_style(1.0))
            self._update_system_badge(cpu_text="CPU --")

        try:
            memory = psutil.virtual_memory()
            mem_usage = getattr(memory, "percent", None)
            if mem_usage is None:
                raise RuntimeError("virtual_memory.percent unavailable")
            if self._memory_label:
                self._memory_label.setText(f"💾 {mem_usage:.0f}%")
                self._memory_label.setStyleSheet(self._status_label_style(min(mem_usage / 100.0, 1.0)))
            self._update_system_badge(mem_text=f"MEM {mem_usage:.0f}%")
        except Exception as e:
            self.logger.warning("[System Status] Memory metric error: %s", e)
            if self._memory_label:
                self._memory_label.setText("💾 --")
                self._memory_label.setStyleSheet(self._status_label_style(1.0))
            self._update_system_badge(mem_text="MEM --")

        try:
            battery = psutil.sensors_battery()
            if self._battery_label:
                if battery:
                    icon = "🔌" if battery.power_plugged else "🔋"
                    percent = battery.percent if battery.percent is not None else 100
                    self._battery_label.setText(f"{icon} {percent:.0f}%")
                    severity = 1 - min(percent / 100.0, 1.0)
                    self._battery_label.setStyleSheet(self._status_label_style(severity))
                else:
                    self._battery_label.setText("🔌 AC")
                    self._battery_label.setStyleSheet("padding:0 8px; font-weight:600; color:#38bdf8;")
        except Exception as e:
            self.logger.warning("[System Status] Battery metric error: %s", e)
            if self._battery_label:
                self._battery_label.setText("🔋 --")
                self._battery_label.setStyleSheet(self._status_label_style(1.0))

        try:
            online, latency_ms = self._probe_internet_latency()
            if self._network_label:
                if online:
                    self._network_label.setText(f"🌐 {latency_ms:.0f}ms")
                    severity = min(latency_ms / 250.0, 1.0)
                    self._network_label.setStyleSheet(self._status_label_style(severity))
                    self._update_system_badge(net_text=f"NET {latency_ms:.0f}ms")
                else:
                    self._network_label.setText("🌐 ללא רשת")
                    self._network_label.setStyleSheet(self._status_label_style(1.0))
                    self._update_system_badge(net_text="NET offline")
        except Exception as e:
            self.logger.warning("[System Status] Network metric error: %s", e)
            if self._network_label:
                self._network_label.setText("🌐 --")
                self._network_label.setStyleSheet(self._status_label_style(1.0))
            self._update_system_badge(net_text="NET --")

    def _load_psutil_module(self):
        """Attempt to import psutil, including common local/venv paths."""
        import importlib
        candidates = []
        self._psutil_last_error = None
        try:
            import psutil  # type: ignore
            return psutil
        except ImportError as exc:
            self._psutil_last_error = str(exc)
        except Exception as exc:
            self._psutil_last_error = str(exc)
            self.logger.error("[System Status] Unexpected psutil import error: %s", exc, exc_info=True)
            return None

        # Build candidate site-packages paths
        project_root = Path(__file__).resolve().parents[2]
        venv_env = os.getenv("VIRTUAL_ENV")
        exe_path = Path(sys.executable).resolve()
        for base in filter(None, [
            venv_env,
            project_root / ".venv",
            project_root / "venv",
            exe_path.parent.parent,  # typical <python>/Lib/site-packages
        ]):
            for lib_dir in ("Lib", "lib"):
                candidate = Path(base) / lib_dir / "site-packages"
                candidates.append(candidate)

        for path in candidates:
            if not path or not Path(path).exists():
                continue
            try:
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
                spec = importlib.util.find_spec("psutil")
                if spec is None:
                    continue
                import psutil  # type: ignore
                return psutil
            except Exception as exc:  # pragma: no cover - best effort
                self._psutil_last_error = str(exc)
                self.logger.debug("[System Status] psutil load failed from %s: %s", path, exc)
                continue

        try:
            import psutil  # type: ignore
            return psutil
        except Exception as exc:
            self._psutil_last_error = str(exc)
            self.logger.error("[System Status] psutil import final fail: %s", exc, exc_info=True)
            return None

    def _probe_internet_latency(self, timeout: float = 1.5) -> tuple[bool, float]:
        """Probe internet connectivity and measure latency."""
        try:
            start = time.perf_counter()
            with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
                latency = (time.perf_counter() - start) * 1000
            return True, latency
        except (OSError, TimeoutError) as e:
            self.logger.debug("[System Status] Network probe failed: %s", e)
            return False, 0.0
        except Exception as e:
            self.logger.warning("[System Status] Unexpected network probe error: %s", e)
            return False, 0.0

    def _handle_transcript_changed(self) -> None:
        self._update_onboarding_tip()
        path_text = self.transcript_edit.text().strip()
        if not path_text:
            self._active_transcript = None
            return
        path = Path(path_text)
        if not path.exists():
            return
        canonical = str(path.resolve())
        
        if canonical != self._active_transcript:
            # Logic for managing chat/metadata reset when transcript changes
            has_content = hasattr(self, "chat_history") and self.chat_history.count() > 0
            is_replacement = bool(self._active_transcript)
            
            # Case 1: Attaching a transcript to an existing session that didn't have one (e.g. missing import)
            if not is_replacement and has_content:
                self._active_transcript = canonical
                self._log(f"תמלול שויך לפרויקט: {path.name}")
                # Do NOT reset session, just associate the file
                return

            # Case 2: Replacing an existing transcript with a new one
            if is_replacement and has_content:
                reply = QMessageBox.question(
                    self,
                    "שינוי תמלול",
                    "החלפת קובץ תמלול.\nהאם לאפס את השיחה והמטא-דאטה להתחלה נקייה?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    # User chose NOT to reset. Update path but keep session.
                    self._active_transcript = canonical
                    self._log(f"תמלול הוחלף ל-{path.name} (השיחה נשמרה).")
                    return
                
                # If Yes, fall through to reset

            # Case 3: Fresh start or User confirmed reset
            self._active_transcript = canonical
            self._reset_metadata_session()

        if not self._should_auto_seed():
            return
        snippet = self._read_transcript_snippet(path)
        if snippet:
            self._start_transcript_seed(snippet)

    def _read_transcript_snippet(self, path: Path, limit: int = 16000) -> str:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return handle.read(limit)
        except OSError as exc:
            self._append_log(f"[Seed] לא ניתן לקרוא את התמלול: {exc}")
            return ""

    def _start_transcript_seed(self, transcript_text: str) -> None:
        if not transcript_text.strip():
            return
        if self.seed_worker and self.seed_worker.isRunning():
            return
        self._set_chat_busy(True)
        self.seed_worker = MetadataSeedWorker(self.chat_session, transcript_text)
        self.seed_worker.result.connect(self._handle_seed_result)
        self.seed_worker.error.connect(self._handle_seed_error)
        self.seed_worker.finished.connect(self._seed_finished)
        self.seed_worker.start()

    def _handle_seed_result(self, payload: object) -> None:
        if not isinstance(payload, dict):
            payload = {}
        self.current_metadata = self.chat_session.export_metadata()
        self._update_metadata_preview()
        for key in ("assistant", "bilingual_hint"):
            message = payload.get(key)
            if message:
                self._append_chat_bubble(APP_ASSISTANT_NAME, message)

    def _handle_seed_error(self, message: str) -> None:
        warning = f"[Seed] {message}"
        self._append_log(warning)
        self._append_chat_bubble(APP_ASSISTANT_NAME, "יצירת המטא-דאטה האוטומטית נכשלה. נסה שוב ידנית.")

    def _seed_finished(self) -> None:
        self._set_chat_busy(False)
        self.seed_worker = None

    def _reset_metadata_session(self) -> None:
        self.chat_session.reset()
        self.current_metadata = self.chat_session.export_metadata()
        if hasattr(self, "chat_history"):
            self.chat_history.clear()
        self._update_metadata_preview()

    def _should_auto_seed(self) -> bool:
        no_materials = self.materials_list.count() == 0 if hasattr(self, "materials_list") else True
        no_urls = not self.urls_edit.toPlainText().strip() if hasattr(self, "urls_edit") else True
        metadata_empty = not (self.current_metadata.get("topic") or self.current_metadata.get("summary"))
        return no_materials and no_urls and metadata_empty

    def _apply_text_direction(self, widget: QPlainTextEdit | QTextEdit, text: str) -> None:
        direction = Qt.LayoutDirection.RightToLeft if _text_is_rtl(text) else Qt.LayoutDirection.LeftToRight
        widget.setLayoutDirection(direction)
        option: QTextOption = widget.document().defaultTextOption()
        alignment = Qt.AlignmentFlag.AlignRight if direction == Qt.LayoutDirection.RightToLeft else Qt.AlignmentFlag.AlignLeft
        option.setAlignment(alignment)
        widget.document().setDefaultTextOption(option)

    def _update_gallery_buttons(self) -> None:
        if not hasattr(self, "gallery_open_btn"):
            return
        selection = self.gallery_list.selectedItems() if hasattr(self, "gallery_list") else []
        raw_path = selection[0].data(Qt.ItemDataRole.UserRole) if selection else ""
        path_available = bool(raw_path and Path(raw_path).exists())
        self.gallery_open_btn.setEnabled(path_available)
        preview_text = getattr(self, "gallery_preview", None)
        if hasattr(self, "gallery_export_btn"):
            self.gallery_export_btn.setEnabled(bool(preview_text and preview_text.toPlainText().strip()))

    def _open_selected_gallery_item(self) -> None:
        if not hasattr(self, "gallery_list"):
            return
        selection = self.gallery_list.selectedItems()
        if not selection:
            QMessageBox.information(self, "מידע", "בחרו פריט מהרשימה.")
            return
        path = selection[0].data(Qt.ItemDataRole.UserRole)
        if not path:
            QMessageBox.information(self, "מידע", "הפריט שנבחר עדיין לא נוצר.")
            return
        self._open_path(Path(path))

    def _export_gallery_pdf(self) -> None:
        if not hasattr(self, "gallery_preview"):
            return
        text = self.gallery_preview.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "מידע", "אין תוכן לייצוא. הריצו צ'אט או Pipeline תחילה.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא PDF", "MBS_story.pdf", "PDF (*.pdf)")
        if not path:
            return
        writer = QPdfWriter(path)
        doc = QTextDocument()
        doc.setPlainText(text)
        doc.print(writer)
        QMessageBox.information(self, "נשמר", f"PDF נשמר אל {path}")

    def _update_metadata_preview(self) -> None:
        if not hasattr(self, "metadata_preview") or self.metadata_preview is None:
            return
        pretty = json.dumps(self.current_metadata, ensure_ascii=False, indent=2)
        self._suppress_metadata_signal = True
        self.metadata_preview.setPlainText(pretty)
        self._suppress_metadata_signal = False
        if hasattr(self, "meta_save_btn"):
            self.meta_save_btn.setEnabled(False)
        if hasattr(self, "meta_revert_btn"):
            self.meta_revert_btn.setEnabled(False)

        # Auto-fill custom project name with topic if field is empty
        if hasattr(self, "custom_project_name"):
            current_text = self.custom_project_name.text().strip()
            topic = self.current_metadata.get("topic", "").strip()
            if not current_text and topic:
                self.custom_project_name.setText(topic)
                self.logger.debug("[_update_metadata_preview] Auto-filled custom_project_name: %s", topic)

        self._apply_text_direction(self.metadata_preview, pretty)
        self._update_story_preview()
        self._update_output_gallery()
        self._update_onboarding_tip()

    def _update_story_preview(self, entry: Optional[Dict] = None) -> None:
        if not hasattr(self, "story_preview"):
            return
        metadata = dict(self.current_metadata or {})

        def merge_field(key: str, source_value: object) -> None:
            if source_value and not metadata.get(key):
                metadata[key] = source_value

        if entry:
            merge_field("topic", entry.get("topic"))
            merge_field("date", entry.get("date"))
            merge_field("summary", entry.get("summary"))
            merge_field("key_concepts", entry.get("key_concepts"))
            merge_field("labs", entry.get("labs"))
            merge_field("reading_list", entry.get("reading_list"))
            run_dir = entry.get("run_dir")
            if run_dir:
                meta_path = Path(run_dir) / "metadata.json"
                if meta_path.exists():
                    try:
                        meta_from_file = json.loads(meta_path.read_text(encoding="utf-8"))
                        for key in ("topic", "date", "summary", "key_concepts", "labs", "reading_list"):
                            merge_field(key, meta_from_file.get(key))
                    except Exception:
                        pass

        topic = metadata.get("topic", "לא צוין")
        date = metadata.get("date", "")
        key_concepts = metadata.get("key_concepts") or []
        labs = metadata.get("labs") or []
        summary = metadata.get("summary") or "טרם נכתב תקציר."

        lines = [
            f"נושא: {topic}",
            f"תאריך: {date}",
            "",
            "מושגים מרכזיים:",
        ]
        lines.extend(f"- {concept}" for concept in key_concepts[:5])
        if labs:
            lines.append("")
            lines.append("מעבדות:")
            lines.extend(f"- {lab}" for lab in labs[:5])
        lines.append("")
        lines.append("תקציר:")
        lines.append(summary)
        story_text = "\n".join(lines)
        self.story_preview.setPlainText(story_text)
        self._apply_text_direction(self.story_preview, story_text)

    def _update_output_gallery(self, entry: Optional[Dict] = None) -> None:
        if not hasattr(self, "gallery_list"):
            return
        if entry is not None:
            self.active_history_entry = entry
            self._update_story_preview(entry)
        data_source = self.active_history_entry
        self.gallery_list.clear()
        if not data_source:
            placeholder_text = "אין עדיין ריצות טעונות. בחרו פרויקט קיימת או הריצו Pipeline כדי לראות תוצרים."
            placeholder = QListWidgetItem(placeholder_text)
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.gallery_list.addItem(placeholder)
            self.gallery_preview.setPlainText("גלריית התוצרים תופיע כאן לאחר שנטען או ניצור פרויקט חדש.")
            self._update_gallery_buttons()
            return
        artifacts = [
            ("Mixdown MP3", self._resolve_artifact_path(data_source, "final_audio")),
            ("סרטון", self._resolve_artifact_path(data_source, "final_video")),
            ("מצגת PPTX", self._resolve_artifact_path(data_source, "slide_deck")),
            ("Notebook Story", self._resolve_artifact_path(data_source, "story")),
        ]
        for label, path in artifacts:
            exists = bool(path and Path(path).exists())
            status = "זמין" if exists else "טרם נוצר"
            item = QListWidgetItem(f"{label} · {status}")
            if exists:
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setForeground(QColor("#22c55e"))
            else:
                item.setData(Qt.ItemDataRole.UserRole, "")
                item.setForeground(QColor("#f97316"))
            self.gallery_list.addItem(item)
        metadata = self.current_metadata or {}
        slides_preview: List[str] = [
            f"נושא: {metadata.get('topic', 'לא צוין')}",
            f"תאריך: {metadata.get('date', '')}",
            "",
            "שקופיות מוצעות:",
        ]
        concepts = metadata.get("key_concepts", [])[:5]
        if concepts:
            for idx, concept in enumerate(concepts, start=1):
                slides_preview.append(f"{idx}. {concept}")
        labs = metadata.get("labs", [])[:4]
        if labs:
            slides_preview.append("")
            slides_preview.append("Labs / פעילויות:")
            for lab in labs:
                slides_preview.append(f"- {lab}")
        reading = metadata.get("reading_list", [])[:4]
        if reading:
            slides_preview.append("")
            slides_preview.append("קריאה מומלצת:")
            for ref in reading:
                slides_preview.append(f"• {ref}")
        summary = metadata.get("summary")
        if summary:
            slides_preview.append("")
            slides_preview.append("תקציר למצגת:")
            slides_preview.append(summary)
        gallery_text = "\n".join(slides_preview)
        self.gallery_preview.setPlainText(gallery_text)
        self._apply_text_direction(self.gallery_preview, gallery_text)
        self._update_gallery_buttons()

    def _resolve_artifact_path(self, entry: Dict, key: str) -> str:
        recorded = entry.get(key)
        if recorded and Path(recorded).exists():
            return recorded
        run_dir = entry.get("run_dir")
        if not run_dir:
            return recorded or ""
        run_path = Path(run_dir)
        date = entry.get("date", "")
        slug = f"lecture_{date}_summary" if date else ""
        candidates = []
        if key == "final_audio":
            if slug:
                candidates.append(run_path / f"{slug}.mp3")
            candidates.extend(run_path.glob("*.mp3"))
        elif key == "final_video":
            if slug:
                candidates.append(run_path / f"{slug}.mp4")
            candidates.extend(run_path.glob("*.mp4"))
        elif key == "slide_deck":
            candidates.append(run_path / "summary.pptx")
        elif key == "story":
            candidates.append(run_path / "story.md")
            candidates.append(run_path / "story.json")
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return recorded or ""

    def _update_onboarding_tip(self) -> None:
        if not hasattr(self, "onboarding_label"):
            return
        tips: List[str] = []
        if not self.transcript_edit.text().strip():
            tips.append("בחר תמלול כדי להתחיל.")
        if not self.materials_list.count() and not self.urls_edit.toPlainText().strip():
            tips.append("העלה קבצים או הדבק קישורים להעשיר את המטא-דאטה.")
        if not self.chat_history.count():
            tips.append("פתח את הצ'אט וספר לבינה על הקורס.")
        if not tips:
            tips.append("מוכן להרצה! לחצו 'הפעל Pipeline'.")
        self.onboarding_label.setText(" • ".join(tips))

    def _export_metadata_to_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא מטא-דאטה", "metadata.json", "JSON (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps(self.current_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "נשמר", f"קובץ נשמר אל {path}")

    def _export_network_map(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "ייצוא מפת רשת",
            "network_map.mmd",
            "Mermaid (*.mmd);;Markdown (*.md);;All Files (*)",
        )
        if not path:
            return
        try:
            self.network_exporter.export(self.current_metadata, Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "שגיאה", f"נכשלה יצירת מפת הרשת:\n{exc}")
            return
        QMessageBox.information(self, "נשמר", f"מפת רשת נוצרה ב-{path}")

    def _handle_metadata_editor_change(self) -> None:
        if getattr(self, "_suppress_metadata_signal", False):
            return
        editor_text = self.metadata_preview.toPlainText().strip()
        canonical = json.dumps(self.current_metadata, ensure_ascii=False, indent=2).strip()
        dirty = editor_text != canonical
        if hasattr(self, "meta_save_btn"):
            self.meta_save_btn.setEnabled(dirty)
        if hasattr(self, "meta_revert_btn"):
            self.meta_revert_btn.setEnabled(dirty)

    def _save_metadata_from_editor(self) -> None:
        raw = self.metadata_preview.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "שגיאה", "לא ניתן לשמור מטא-דאטה ריק.")
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "שגיאה", f"JSON לא תקין:\n{exc}")
            return
        if not isinstance(payload, dict):
            QMessageBox.warning(self, "שגיאה", "המטא-דאטה חייב להיות אובייקט JSON ({}).")
            return
        self.current_metadata = payload
        self.chat_session.import_metadata(payload)
        self._update_metadata_preview()

    def _revert_metadata_editor(self) -> None:
        self._update_metadata_preview()

    # --- File pickers ------------------------------------------------
    def _pick_file(self, line_edit: QLineEdit, filter_str: str = "All Files (*)") -> None:
        path, _ = QFileDialog.getOpenFileName(self, "בחר קובץ", "", filter_str)
        if path:
            line_edit.setText(path)

    def _pick_directory(self, line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "בחר תיקייה", line_edit.text() or "")
        if path:
            line_edit.setText(path)

    def _add_materials(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "בחר קבצים",
            "",
            "Documents (*.pdf *.docx *.pptx *.txt *.md);;All Files (*)",
        )
        for file in files:
            if file and not any(self.materials_list.item(i).text() == file for i in range(self.materials_list.count())):
                self.materials_list.addItem(file)
        self._sync_materials_to_session()

    def _remove_materials(self) -> None:
        for item in self.materials_list.selectedItems():
            row = self.materials_list.row(item)
            self.materials_list.takeItem(row)
        self._sync_materials_to_session()

    def _sync_materials_to_session(self) -> None:
        paths = [Path(self.materials_list.item(i).text()) for i in range(self.materials_list.count())]
        urls = [line.strip() for line in self.urls_edit.toPlainText().splitlines() if line.strip()]
        
        # Track previously known URLs to detect new additions
        prev_urls = getattr(self, "_known_urls", set())
        new_urls = set(urls) - prev_urls
        self._known_urls = set(urls)
        
        # Notify chat about new URLs
        for url in new_urls:
            if url.startswith("http"):
                self._append_chat_bubble(
                    APP_ASSISTANT_NAME, 
                    f"📎 קישור נוסף: {url}\nהמטא-דאטה יועשר עם תוכן מהקישור בהרצת ה-Pipeline.",
                    is_user=False
                )
        
        self.chat_session.attach_materials(paths)
        self.chat_session.attach_urls(urls)
        self._update_onboarding_tip()
        self._update_materials_card_size()

    def _update_materials_card_size(self) -> None:
        """
        Keep the attachments card compact when many files/URLs are attached.
        Shrinks only when the content list grows, to free vertical space for chat.
        """
        if not hasattr(self, "attachments_card"):
            return

        file_count = self.materials_list.count() if hasattr(self, "materials_list") else 0
        url_rows = (
            len([line for line in self.urls_edit.toPlainText().splitlines() if line.strip()])
            if hasattr(self, "urls_edit")
            else 0
        )
        crowded = (file_count + url_rows) >= 4

        if crowded:
            # Compact mode to leave more room for the rest of the workspace
            self.attachments_card.setMinimumHeight(0)
            self.attachments_card.setMaximumHeight(200)
            if hasattr(self, "materials_list"):
                self.materials_list.setMaximumHeight(140)
            if hasattr(self, "urls_edit"):
                self.urls_edit.setMaximumHeight(120)
        else:
            # Reset to normal sizing when there aren't many attachments
            self.attachments_card.setMinimumHeight(0)
            self.attachments_card.setMaximumHeight(240)
            if hasattr(self, "materials_list"):
                self.materials_list.setMaximumHeight(200)
            if hasattr(self, "urls_edit"):
                self.urls_edit.setMaximumHeight(160)

    def _open_voice_profiles(self) -> None:
        try:
            self.voice_manager.open_in_explorer()
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "שגיאה", f"לא ניתן לפתוח קובץ קולות:\n{exc}")

    # --- Pipeline invocation ----------------------------------------
    def _collect_command(self) -> Optional[List[str]]:
        """
        Collect and validate all command-line arguments for the pipeline.
        
        Validates:
            - Transcript file exists and is readable
            - Output directory is writable
            - Metadata is complete
            - Voice profile exists
            - TTS provider is configured
            
        Returns:
            List of command arguments if validation passes, None otherwise
        """
        self.logger.info("[_collect_command] Collecting pipeline command arguments")
        validation_errors: List[str] = []
        
        # Validate transcript
        transcript = self.transcript_edit.text().strip()
        if not transcript:
            validation_errors.append("לא נבחר קובץ תמלול")
            self.logger.error("[_collect_command] No transcript selected")
        elif not Path(transcript).exists():
            validation_errors.append(f"קובץ תמלול לא נמצא: {transcript}")
            self.logger.error("[_collect_command] Transcript file not found: %s", transcript)
        elif not Path(transcript).is_file():
            validation_errors.append(f"הנתיב אינו קובץ: {transcript}")
            self.logger.error("[_collect_command] Transcript path is not a file: %s", transcript)
        else:
            # Check file is readable
            try:
                size = Path(transcript).stat().st_size
                if size == 0:
                    validation_errors.append("קובץ תמלול ריק")
                    self.logger.error("[_collect_command] Transcript file is empty")
                else:
                    self.logger.debug("[_collect_command] Transcript validated: %s (%d bytes)", 
                                     Path(transcript).name, size)
            except OSError as e:
                validation_errors.append(f"לא ניתן לקרוא את התמלול: {e}")
                self.logger.error("[_collect_command] Cannot read transcript: %s", e)
        
        # Validate output directory
        output_dir_str = self.output_dir_edit.text().strip() or str(self.settings.output_base_dir)
        try:
            output_dir_path = Path(output_dir_str).expanduser().resolve()
            output_dir_path.mkdir(parents=True, exist_ok=True)
            self.output_dir_edit.setText(str(output_dir_path))
            self.logger.debug("[_collect_command] Output directory: %s", output_dir_path)
        except OSError as e:
            validation_errors.append(f"לא ניתן ליצור תיקיית פלט: {e}")
            self.logger.error("[_collect_command] Cannot create output directory: %s", e)
            
        # Report validation errors
        if validation_errors:
            error_msg = "\n".join(f"• {err}" for err in validation_errors)
            self.logger.error("[_collect_command] Validation failed:\n%s", error_msg)
            QMessageBox.warning(self, "שגיאות אימות", f"נמצאו בעיות:\n\n{error_msg}")
            return None

        # Apply custom project name if provided
        if hasattr(self, "custom_project_name"):
            custom_name = self.custom_project_name.text().strip()
            if custom_name:
                self.logger.debug("[_collect_command] Using custom project name: %s", custom_name)
                self.current_metadata["topic"] = custom_name
                self._update_metadata_preview()

        metadata_path = self._write_metadata_file()
        self._ensure_visual_metadata_ready(output_dir_path)
        visual_meta_path = (self.metadata_temp_path.parent / "visual_metadata.json")
        if self.include_visuals_cb.isChecked() and visual_meta_path.exists():
            self._latest_visual_metadata_path = visual_meta_path
            self.logger.info("[_collect_command] Using existing visual_metadata.json (preview=%s)", self.settings.preview_mode)
            self._append_log("Using custom visual_metadata prompts (כולל מצב טיוטה).")
        if self.include_visuals_cb.isChecked():
            visual_gen = getattr(self.settings, 'visual_generator', 'manim')
            requires_google_ai = visual_gen in ("imagen", "imagen_manim", "veo", "hybrid")
            if requires_google_ai:
                ok, status_msg = self._check_google_ai_status()
                if not ok:
                    self.logger.warning("[_collect_command] Google AI status check failed: %s", status_msg)
                    reply = QMessageBox.question(
                        self,
                        "בעיה עם Google Imagen",
                        f"לא ניתן לאמת את החיבור ל-Google Imagen:\n{status_msg}\n\n"
                        "להמשיך בכל זאת (תיתכן יצירת placeholders)?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return None
                else:
                    self._log(f"Google Imagen מוכן ({status_msg})")
        cmd: List[str] = [
            sys.executable,
            "-m",
            "scripts.generate_podcast",
            transcript,
            metadata_path,
            "--output-dir",
            str(output_dir_path),
        ]
        if self.include_visuals_cb.isChecked():
            cmd.append("--include-visuals")
        else:
            cmd.append("--skip-visuals")
        voice_profile = self.voice_combo.currentText().strip()
        if voice_profile:
            cmd.extend(["--voice-profile", voice_profile])
        # Preview mode (credit saver)
        preview_mode = getattr(self, "preview_mode_cb", None)
        self.settings.preview_mode = bool(preview_mode.isChecked()) if preview_mode else False
        self.logger.info("[_collect_command] preview_mode=%s", self.settings.preview_mode)
        if self.settings.preview_mode:
            cmd.append("--preview")
        # TTS provider selection
        if hasattr(self, "tts_provider_combo"):
            tts_provider = self.tts_provider_combo.currentData()
            if tts_provider:
                self.logger.info("[_collect_command] tts_provider=%s", tts_provider)
                cmd.extend(["--tts-provider", tts_provider])
        for i in range(self.materials_list.count()):
            path = self.materials_list.item(i).text().strip()
            if path:
                cmd.extend(["--material", path])
        urls = [line.strip() for line in self.urls_edit.toPlainText().splitlines() if line.strip()]
        for url in urls:
            cmd.extend(["--url", url])
        if self.skip_cache_cb.isChecked():
            cmd.append("--skip-cache")
        if self.force_cb.isChecked():
            cmd.append("--force")
        if self.dry_run_cb.isChecked():
            cmd.append("--dry-run")
        if self.export_ppt_cb.isChecked():
            cmd.append("--export-ppt")
        
        # Explicitly pass visual settings to ensure subprocess gets them
        visual_gen = getattr(self.settings, 'visual_generator', 'manim')
        if visual_gen:
            cmd.extend(["--visual-generator", visual_gen])
            
        # Override image_count from GUI control (UI wins over .env/default)
        image_count = getattr(self.settings, 'image_count', 5)
        if hasattr(self, "image_count_spin") and self.image_count_spin:
            gui_image_count = self.image_count_spin.value()
            image_count = gui_image_count
            setattr(self.settings, "image_count", image_count)
            self.logger.info("INFO: Overriding default image count with GUI value: %s", image_count)
            self._append_log(f"Overriding default image count with GUI value: {image_count}")
        self._log(f"Using image_count: {image_count}")  # Debug log
        if image_count:
            cmd.extend(["--image-count", str(image_count)])
            
        if not getattr(self.settings, 'auto_video_duration', True):
            duration = getattr(self.settings, 'video_duration_seconds', 300.0)
            self.logger.info("[_collect_command] manual video_duration=%s", duration)
            cmd.extend(["--video-duration", str(duration)])
            
        self.pending_run_dir = self._predict_run_dir(self.current_metadata, output_dir_path)
        if not self._confirm_budget_allowance():
            return None
        return cmd

    def _set_pipeline_buttons_state(self, enabled: bool) -> None:
        """Enable/disable all run controls together to keep them in sync."""
        # Explicitly toggle both top and bottom run buttons to avoid double-activation
        for attr in ("quick_run_btn", "control_run_btn"):
            btn = getattr(self, attr, None)
            if btn:
                btn.setEnabled(enabled)
        # Also handle named run_btn in control panel if present
        try:
            run_btn = self.findChild(QPushButton, "run_pipeline_btn")
            if run_btn:
                run_btn.setEnabled(enabled)
        except Exception:
            pass

    def _write_metadata_file(self) -> str:
        self.metadata_temp_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_temp_path.write_text(json.dumps(self.current_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.metadata_temp_path)

    def _run_pipeline(self) -> None:
        """
        Execute the complete podcast generation pipeline.
        
        Validates inputs, collects command parameters, and starts the
        pipeline worker thread. Progress is tracked via the status card
        and header status bar.
        
        The pipeline performs these stages:
        1. Metadata ingestion from transcript
        2. AI-powered dialogue generation
        3. Text-to-speech synthesis
        4. Audio mixing and stitching
        5. Video composition (if enabled)
        6. PPTX export (if enabled)
        
        Results are saved to the output directory and logged to history.
        """
        self.logger.info("[_run_pipeline] Starting pipeline execution")
        self._set_pipeline_buttons_state(False)
        
        if self.worker and self.worker.isRunning():
            self.logger.warning("[_run_pipeline] Pipeline already running, skipping")
            QMessageBox.information(self, "מתבצע", "תהליך כבר רץ.")
            return

        if not self._ensure_visual_generator_ready():
            return

        # Normalize and persist Imagen/VEO selections for the subprocess (env-based Settings.load)
        imagen_model = getattr(self.settings, "imagen_model", "imagen-4.0-generate-001") or "imagen-4.0-generate-001"
        deprecated_imagen = "imagen-3.0-fast-generate-001"
        if imagen_model == deprecated_imagen:
            self._append_log("מעדכן דגם Imagen ישן ל-imagen-4.0-generate-001")
            imagen_model = "imagen-4.0-generate-001"
            setattr(self.settings, "imagen_model", imagen_model)
            try:
                self.settings.save_ui_preferences({"imagen_model": imagen_model})
            except Exception:
                pass
        os.environ["IMAGEN_MODEL"] = imagen_model
        self.logger.info("[_run_pipeline] Using imagen_model=%s", imagen_model)
        veo_model = getattr(self.settings, "veo_model", "veo-2.0-generate-001") or "veo-2.0-generate-001"
        os.environ["VEO_MODEL"] = veo_model
        self.logger.info("[_run_pipeline] Using veo_model=%s", veo_model)

        command = self._collect_command()
        if not command:
            self.logger.warning("[_run_pipeline] Command collection failed, aborting")
            return
            
        self.logger.info("[_run_pipeline] Command: %s", " ".join(command))
        self.logger.debug("[_run_pipeline] pending_run_dir: %s", self.pending_run_dir)
        
        console = getattr(self, "log_console", None)
        if console:
            console.clear()
            
        self._start_run_log()
        if self.pipeline_status_timer:
            self.pipeline_status_timer.start()
        self._start_pipeline_status()
        self._append_log(f"מריץ: {' '.join(command)}")
        self._set_pipeline_buttons_state(False)
        self.open_output_btn.setEnabled(False)
        
        try:
            self.worker = PipelineWorker(command, cwd=Path(__file__).resolve().parents[2])
            self.worker.output.connect(self._append_log)
            self.worker.finished.connect(self._run_finished)
            self.worker.heartbeat.connect(self._on_worker_heartbeat)
            self.worker.stall_detected.connect(self._on_worker_stall)
            self.worker.sleep_recovery.connect(self._on_worker_sleep_recovery)
            self.worker.start()
            self.logger.info("[_run_pipeline] PipelineWorker started successfully")
        except Exception as e:
            self.logger.error("[_run_pipeline] Failed to start PipelineWorker: %s\n%s", e, traceback.format_exc())
            self._set_pipeline_buttons_state(True)
            self.open_output_btn.setEnabled(True)
            QMessageBox.critical(self, "שגיאה", f"נכשל בהפעלת Pipeline:\n{e}")

    def _run_finished(self, code: int) -> None:
        """Handle pipeline completion."""
        status = "הצליח" if code == 0 else f"נכשל (קוד {code})"
        self.logger.info("[_run_finished] Pipeline finished with code %d (%s)", code, status)
        
        self._append_log(f"תהליך הסתיים: {status}")
        
        if code == 0:
            self.logger.info("[_run_finished] Persisting run context to history")
            success_box = QMessageBox(self)
            success_box.setIcon(QMessageBox.Icon.Information)
            success_box.setWindowTitle("הושלם")
            success_box.setText("Pipeline הושלם בהצלחה")
            success_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            success_box.exec()

            # Save performance data for ETA improvements
            self._save_performance_data()

            self._persist_run_context_to_history()
            self._refresh_history()
            latest = self.history.all()
            if latest:
                self._update_output_gallery(latest[0])
            self.pending_run_dir = None
        else:
            self.logger.warning("[_run_finished] Pipeline failed, saving failure log")
            failure_box = QMessageBox(self)
            failure_box.setIcon(QMessageBox.Icon.Warning)
            failure_box.setWindowTitle("שגיאה")
            failure_box.setText("Pipeline הסתיים עם שגיאה")
            failure_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            failure_box.exec()
            self._save_failure_log()
            
        self._set_pipeline_buttons_state(True)
        self.open_output_btn.setEnabled(True)
        self._finalize_pipeline_status(code == 0)

    def _save_performance_data(self) -> None:
        """Save pipeline performance data for ETA improvements."""
        try:
            from .constants import save_performance_data

            # Collect stage timing data
            stage_times = {}
            if hasattr(self, 'pipeline_stage_timestamps'):
                for stage_name, timestamp in self.pipeline_stage_timestamps.items():
                    stage_times[stage_name] = timestamp

            # Collect content statistics
            content_stats = {
                "transcript_length": getattr(self, '_estimated_transcript_length', 0),
                "dialogue_entries": getattr(self, '_estimated_dialogue_entries', 0),
                "image_count": getattr(self, '_estimated_image_count', 10),
            }

            # Save the data
            save_performance_data(stage_times, content_stats)
            self.logger.debug("[_save_performance_data] Performance data saved for ETA improvements")

        except Exception as e:
            self.logger.warning("[_save_performance_data] Failed to save performance data: %s", e)

    def _start_visual_meta_spinner(self, base_text: str) -> None:
        if not hasattr(self, "visual_meta_status") or self.visual_meta_status is None:
            return
        if self._visual_meta_spinner_timer is None:
            self._visual_meta_spinner_timer = QTimer(self)
            self._visual_meta_spinner_timer.timeout.connect(self._tick_visual_meta_spinner)
        self._visual_meta_spinner_base = base_text
        self._visual_meta_spinner_step = 0
        self.visual_meta_status.setText(base_text + " •")
        self._visual_meta_spinner_timer.start(350)

    def _tick_visual_meta_spinner(self) -> None:
        if not hasattr(self, "visual_meta_status") or self.visual_meta_status is None:
            return
        if not self._visual_meta_spinner_timer or not self._visual_meta_spinner_timer.isActive():
            return
        self._visual_meta_spinner_step = (self._visual_meta_spinner_step + 1) % 4
        dots = "•" * max(1, self._visual_meta_spinner_step)
        self.visual_meta_status.setText(f"{self._visual_meta_spinner_base} {dots}")

    def _stop_visual_meta_spinner(self) -> None:
        if self._visual_meta_spinner_timer:
            self._visual_meta_spinner_timer.stop()
        self._visual_meta_spinner_base = ""
        self._visual_meta_spinner_step = 0

    def _generate_visual_metadata(self) -> None:
        """
        Generate detailed visual metadata for image/video generation.
        
        Uses the AI to create professional prompts for 10 images and 1 video,
        including styles, moods, color palettes, and contextual meanings.
        The result is saved to visual_metadata.json for use by the pipeline.
        """
        self.logger.info("[_generate_visual_metadata] Starting visual metadata generation")
        
        # Check if we have transcript text
        transcript_text = getattr(self, "transcript_edit", None)
        if not transcript_text or not transcript_text.text().strip():
            QMessageBox.warning(
                self,
                "חסר תמלול",
                "יש לטעון קובץ תמלול לפני יצירת מטא-דאטה ויזואלית."
            )
            return
        
        # Check if we have metadata
        if not self.chat_session.current_metadata.get("topic"):
            QMessageBox.warning(
                self,
                "חסר מטא-דאטה",
                "יש ליצור מטא-דאטה בסיסי קודם (לדבר עם הבינה או לטעון קובץ)."
            )
            return
        
        # Update status
        spinner_text = "מייצר מטא-דאטה ויזואלית (עד 2 דקות)"
        if hasattr(self, "visual_meta_status"):
            self.visual_meta_status.setText(spinner_text)
        if hasattr(self, "visual_meta_btn"):
            self.visual_meta_btn.setEnabled(False)
        self._start_visual_meta_spinner(spinner_text)

        metadata_snapshot = copy.deepcopy(self.chat_session.export_metadata())
        
        # Read transcript
        try:
            transcript_path = Path(transcript_text.text().strip())
            if not transcript_path.exists():
                raise FileNotFoundError(f"קובץ לא נמצא: {transcript_path}")
            full_transcript = transcript_path.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error("[_generate_visual_metadata] Failed to read transcript: %s", e)
            QMessageBox.critical(self, "שגיאה", f"לא ניתן לקרוא את קובץ התמלול: {e}")
            if hasattr(self, "visual_meta_btn"):
                self.visual_meta_btn.setEnabled(True)
            if hasattr(self, "visual_meta_status"):
                self.visual_meta_status.setText("שגיאה")
            return
        
        # Run visual metadata generation in a thread
        self._visual_meta_worker = VisualMetadataWorker(
            self.chat_session,
            full_transcript,
            self.settings.image_count if hasattr(self.settings, 'image_count') else 10,
            metadata_snapshot=metadata_snapshot,
        )
        self._visual_meta_worker.finished.connect(self._on_visual_metadata_complete)
        self._visual_meta_worker.error.connect(self._on_visual_metadata_error)
        self._visual_meta_worker.start()
        
        self.logger.info("[_generate_visual_metadata] Worker started")

    def _on_visual_metadata_complete(self, visual_metadata: dict) -> None:
        """Handle successful visual metadata generation."""
        self.logger.info("[_on_visual_metadata_complete] Received %d images", 
                        len(visual_metadata.get("images", [])))
        self._stop_visual_meta_spinner()
        
        # Save to file
        output_dir = Path(self.output_dir_edit.text().strip()) if hasattr(self, "output_dir_edit") else None
        serialized_metadata = dict(visual_metadata)
        generation_source = serialized_metadata.pop("_generation_source", None)
        if output_dir:
            visual_meta_path = output_dir / "visual_metadata.json"
            try:
                import json
                visual_meta_path.parent.mkdir(parents=True, exist_ok=True)
                visual_meta_path.write_text(
                    json.dumps(serialized_metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                self.logger.info("[_on_visual_metadata_complete] Saved to %s", visual_meta_path)
            except Exception as e:
                self.logger.error("[_on_visual_metadata_complete] Failed to save: %s", e)

        self._cache_visual_metadata(serialized_metadata)
        
        # Update status
        num_images = len(visual_metadata.get("images", []))
        has_video = bool(visual_metadata.get("video", {}).get("prompt"))
        status_text = f"✅ {num_images} תמונות"
        if has_video:
            status_text += " + וידאו"
        if generation_source == "local_fallback":
            status_text += " · נוצר מקומית"
            self.logger.info("[_on_visual_metadata_complete] Local fallback provided the prompts.")
        
        if hasattr(self, "visual_meta_status"):
            self.visual_meta_status.setText(status_text)
        if hasattr(self, "visual_meta_btn"):
            self.visual_meta_btn.setEnabled(True)
        
        # Show preview dialog
        self._show_visual_metadata_preview(visual_metadata)

    def _on_visual_metadata_error(self, error_msg: str) -> None:
        """Handle visual metadata generation error."""
        self.logger.error("[_on_visual_metadata_error] %s", error_msg)
        self._stop_visual_meta_spinner()
        
        if hasattr(self, "visual_meta_status"):
            self.visual_meta_status.setText("❌ שגיאה")
        if hasattr(self, "visual_meta_btn"):
            self.visual_meta_btn.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "שגיאה ביצירת מטא-דאטה ויזואלית",
            f"לא ניתן ליצור מטא-דאטה ויזואלית:\n{error_msg}"
        )

    def _show_visual_metadata_preview(self, visual_metadata: dict) -> None:
        """Show a preview dialog for the generated visual metadata."""
        images = visual_metadata.get("images", [])
        video = visual_metadata.get("video", {})
        background = visual_metadata.get("background", "")
        notes = visual_metadata.get("general_notes", {})
        
        preview_text = f"🎨 מטא-דאטה ויזואלית\n{'='*50}\n\n"
        preview_text += f"📖 רקע:\n{background[:200]}{'...' if len(background) > 200 else ''}\n\n"
        preview_text += f"📸 תמונות ({len(images)}):\n"
        for img in images[:5]:  # Show first 5
            preview_text += f"  {img.get('index', '?')}. {img.get('title', 'ללא כותרת')}\n"
            preview_text += f"     סגנון: {img.get('style', 'N/A')[:50]}\n"
        if len(images) > 5:
            preview_text += f"  ... ועוד {len(images) - 5} תמונות\n"
        
        if video.get("prompt"):
            preview_text += f"\n🎬 וידאו:\n"
            preview_text += f"  כותרת: {video.get('title', 'ללא כותרת')}\n"
            preview_text += f"  אורך: {video.get('duration', 0)} שניות\n"
            preview_text += f"  סגנון: {video.get('style', 'N/A')[:50]}\n"
        
        if notes.get("aesthetics"):
            preview_text += f"\n🎭 אסתטיקה:\n{notes.get('aesthetics', '')[:100]}...\n"
        
        QMessageBox.information(
            self,
            "מטא-דאטה ויזואלית נוצרה בהצלחה",
            preview_text
        )

    def _cache_visual_metadata(self, visual_metadata: dict, destination: Optional[Path] = None) -> Optional[Path]:
        """Persist the latest visual metadata next to the metadata temp file."""
        if not visual_metadata:
            return None
        target = destination or (self.metadata_temp_path.parent / "visual_metadata.json")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(visual_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            self._latest_visual_metadata = visual_metadata
            self._latest_visual_metadata_path = target
            self.logger.debug("[Visual Metadata] Cached to %s", target)
            return target
        except Exception as exc:
            self.logger.warning("[Visual Metadata] Failed to cache metadata: %s", exc)
            return None

    def _ensure_visual_metadata_ready(self, output_dir: Path) -> None:
        """
        Ensure that visual_metadata.json sits next to the metadata temp file before running the pipeline.
        """
        metadata_dir = self.metadata_temp_path.parent
        try:
            metadata_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.warning("[Visual Metadata] Cannot create metadata directory: %s", exc)
            return

        cache_path = metadata_dir / "visual_metadata.json"
        if self._latest_visual_metadata:
            self._cache_visual_metadata(self._latest_visual_metadata, cache_path)
            return
        if cache_path.exists():
            self._latest_visual_metadata_path = cache_path
            return

        output_visual = output_dir / "visual_metadata.json"
        if output_visual.exists():
            try:
                shutil.copy2(output_visual, cache_path)
                self._latest_visual_metadata_path = cache_path
                self.logger.info("[Visual Metadata] Copied from %s to %s", output_visual, cache_path)
            except Exception as exc:
                self.logger.warning("[Visual Metadata] Failed to copy file from output dir: %s", exc)

    def _check_google_ai_status(self) -> Tuple[bool, str]:
        """Ping the Google Imagen API to verify connectivity before running the pipeline."""
        api_key = getattr(self.settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return False, "GEMINI_API_KEY לא הוגדר."
        try:
            import requests

            response = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key, "pageSize": 1},
                timeout=5,
            )
            if response.status_code == 200:
                latency_ms = response.elapsed.total_seconds() * 1000
                return True, f"latency {latency_ms:.0f}ms"
            return False, f"שגיאת API {response.status_code}: {response.text[:120]}"
        except Exception as exc:
            return False, str(exc)

    def _update_gemini_status_banner(self) -> None:
        """Update the UI banner that shows Gemini/Imagen availability."""
        label = getattr(self, "visual_meta_status", None)
        if not label:
            return
        gemini_key = getattr(self.settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            label.setText("⚠️ GEMINI_API_KEY לא הוגדר – יווצרו תמונות זמניות.")
            return
        if self._gemini_probe_scheduled:
            return
        self._gemini_probe_scheduled = True
        label.setText("בודק חיבור ל-Google Imagen...")
        QTimer.singleShot(1200, self._run_gemini_latency_probe)

    def _run_gemini_latency_probe(self) -> None:
        """Run a synchronous connectivity check and update the banner."""
        label = getattr(self, "visual_meta_status", None)
        if not label:
            return
        status, message = self._check_google_ai_status()
        if status:
            label.setText(f"Google Imagen זמין ({message})")
        else:
            label.setText(f"⚠️ Google Imagen: {message}")
            self._log(f"⚠️ Google Imagen: {message}")
        self._gemini_probe_scheduled = False

    def _ensure_visual_generator_ready(self) -> bool:
        """Ensure Google AI visuals have a valid configuration before running."""
        visual_gen = getattr(self.settings, "visual_generator", "manim") or "manim"
        requires_gemini = visual_gen in {"imagen", "imagen_manim", "veo", "hybrid"}
        if not requires_gemini:
            return True
        gemini_key = getattr(self.settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            return True
        warning = (
            "GEMINI_API_KEY לא הוגדר, ולכן יווצרו תמונות פלייסהולדר.\n"
            "האם להמשיך בכל זאת?"
        )
        choice = QMessageBox.question(
            self,
            "חסר מפתח Gemini",
            warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            self._log("❌ Pipeline נעצר: GEMINI_API_KEY לא מוגדר.")
            return False
        self._log("⚠️ ממשיך ללא GEMINI_API_KEY – יווצרו תמונות זמניות.")
        if hasattr(self, "visual_meta_status") and self.visual_meta_status:
            self.visual_meta_status.setText("⚠️ GEMINI_API_KEY חסר – יווצרו תמונות זמניות.")
        return True

    def _run_quality_check(self) -> None:
        """
        Run quality verification checks.
        
        Opens the QualityReportDialog which performs:
        - Pre-flight checks (API keys, voice configuration, Hebrew support, quota)
        - Post-processing checks (audio/video validation) if an output directory exists
        
        Results are displayed in a visual dialog with pass/fail indicators.
        """
        self.logger.info("[_run_quality_check] Opening quality check dialog")
        
        # Determine output directory for post-processing checks
        output_dir = None
        if self.pending_run_dir and self.pending_run_dir.exists():
            output_dir = self.pending_run_dir
        elif hasattr(self, 'last_run_dir') and self.last_run_dir and self.last_run_dir.exists():
            output_dir = self.last_run_dir
        else:
            # Try to get from history
            history_entries = self.history.all()
            if history_entries:
                latest = history_entries[0]
                run_dir_str = latest.get("run_dir", "")
                if run_dir_str:
                    run_dir = Path(run_dir_str)
                    if run_dir.exists():
                        output_dir = run_dir
        
        self.logger.info("[_run_quality_check] Output directory: %s", output_dir)
        
        dialog = QualityReportDialog(
            parent=self,
            settings=self.settings,
            output_dir=output_dir,
        )
        dialog.exec()
        
        self.logger.info("[_run_quality_check] Quality check dialog closed")

    def _append_log(self, text: str) -> None:
        console = getattr(self, "log_console", None)
        if console:
            console.appendPlainText(text)
        self.log_buffer.append(text)
        self._maybe_update_pipeline_status(text)
        if len(self.log_buffer) > 2000:
            self.log_buffer = self.log_buffer[-2000:]

    def _log(self, text: str) -> None:
        """Helper alias for _append_log."""
        self._append_log(text)

    # --- Pipeline status feedback ------------------------------------
    def _reset_pipeline_status(self) -> None:
        self.pipeline_stage_index = 0
        self.pipeline_start_time = None
        if self.pipeline_status_timer:
            self.pipeline_status_timer.stop()
        if not (self.run_stage_label and self.run_progress_bar and self.run_timer_label):
            self._hide_header_status()
            return
        self.run_stage_label.setText("אין ריצה פעילה")
        self.run_progress_bar.setValue(0)
        self.run_timer_label.setText("Pipeline טרם הופעל.")
        self._set_header_idle_state()
        if self.run_status_card:
            self.run_status_card.setVisible(False)

    def _reveal_run_status_card(self, scroll_into_view: bool = False) -> None:
        """Ensure the run status card is visible and optionally scrolled into view."""
        if not self.run_status_card:
            return
        self.run_status_card.setVisible(True)
        if scroll_into_view:
            scroll_area = getattr(self, "summary_scroll", None)
            if isinstance(scroll_area, QScrollArea):
                def _ensure_visible() -> None:
                    scroll_area.ensureWidgetVisible(self.run_status_card, 0, 32)

                QTimer.singleShot(0, _ensure_visible)

    def _start_pipeline_status(self) -> None:
        if not self.run_status_card:
            return

        # Calculate dynamic weights based on content
        transcript_length = 0
        dialogue_entries = 0
        image_count = 10  # Default

        # Try to get accurate content information
        if hasattr(self, 'current_metadata') and self.current_metadata:
            # Count dialogue entries if available
            dialogue_data = self.current_metadata.get('dialogue', [])
            dialogue_entries = len(dialogue_data) if isinstance(dialogue_data, list) else 0

            # Get transcript length from actual transcript file if available
            transcript_text = ""
            if hasattr(self, 'transcript_path') and self.transcript_path and self.transcript_path.exists():
                try:
                    transcript_text = self.transcript_path.read_text(encoding='utf-8')
                    transcript_length = len(transcript_text)
                except Exception:
                    # Fallback to summary length
                    summary = self.current_metadata.get('summary', '')
                    transcript_length = len(summary) * 3
            else:
                # Fallback to summary length
                summary = self.current_metadata.get('summary', '')
                transcript_length = len(summary) * 3

            # Get image count from visual settings
            image_count = getattr(self, 'image_count_spin', None)
            if image_count:
                image_count = image_count.value()
            else:
                image_count = 10  # Default fallback

        # Store content statistics for performance tracking
        self._estimated_transcript_length = transcript_length
        self._estimated_dialogue_entries = dialogue_entries
        self._estimated_image_count = image_count

        # Initialize stage timestamps tracking
        self.pipeline_stage_timestamps = {}

        # Import here to avoid circular imports
        from .constants import calculate_dynamic_weights, load_performance_history

        # Update pipeline stages with dynamic weights
        self.pipeline_stages = calculate_dynamic_weights(
            transcript_length=transcript_length,
            image_count=image_count,
            dialogue_entries=dialogue_entries
        )

        # Load historical performance averages for smoother ETA
        try:
            self._performance_averages = load_performance_history()
        except Exception:
            self._performance_averages = {}

        self.logger.info(f"[ETA] Dynamic weights calculated: transcript={transcript_length}, dialogue={dialogue_entries}, images={image_count}")

        self.pipeline_stage_index = 0
        self.pipeline_start_time = time.perf_counter()
        self._current_stage_start = self.pipeline_start_time
        self._reveal_run_status_card(scroll_into_view=True)
        self._refresh_pipeline_status(label="מאתחל Pipeline", percent=0)
        if self.pipeline_status_timer:
            self.pipeline_status_timer.start()

        # Auto-advance from initialization stage after a short delay
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self._auto_advance_from_init)

    def _auto_advance_from_init(self) -> None:
        """Auto-advance from stages marked with auto_advance flag."""
        if self.pipeline_stages and self.pipeline_stage_index < len(self.pipeline_stages):
            current_stage = self.pipeline_stages[self.pipeline_stage_index]
            if current_stage.get("auto_advance", False):
                # Move to the next stage
                self.pipeline_stage_index += 1
                self._refresh_pipeline_status()
                self.logger.debug(f"[_auto_advance_from_init] Auto-advanced from '{current_stage['label']}' to next stage")

    def _maybe_update_pipeline_status(self, text: str) -> None:
        if not self.run_status_card:
            return
        lowered = text.lower()
        for idx, stage in enumerate(self.pipeline_stages):
            if stage["keyword"].lower() in lowered:
                if idx < self.pipeline_stage_index:
                    break
                # Record timestamp for performance tracking
                if hasattr(self, 'pipeline_start_time') and self.pipeline_start_time:
                    elapsed = time.perf_counter() - self.pipeline_start_time
                    self.pipeline_stage_timestamps[stage["keyword"]] = elapsed

                self.pipeline_stage_index = idx
                self._current_stage_start = time.perf_counter()
                if not self.pipeline_start_time:
                    self.pipeline_start_time = time.perf_counter()
                self._reveal_run_status_card()
                self._refresh_pipeline_status()
                break

    def _on_pipeline_status_tick(self) -> None:
        """Periodic refresh so ETA updates even during quiet stages."""
        if not self.run_status_card or not self.pipeline_start_time:
            return
        if self.worker and self.worker.isRunning():
            self._refresh_pipeline_status()
        elif self.pipeline_stage_index and self.pipeline_stage_index < len(self.pipeline_stages):
            # Keep updating elapsed time while finishing UI updates
            self._refresh_pipeline_status()

    def _on_worker_heartbeat(self, seconds_since_output: float) -> None:
        """
        Keep UI alive during quiet stages by updating ETA/labels on heartbeat.
        
        The pipeline can go silent for ~30s during metadata/visual generation,
        so we surface a lightweight status hint instead of leaving the user in
        the dark.
        """
        if not self.run_status_card:
            return
        # Refresh ETA/progress even without new log lines
        self._refresh_pipeline_status()
        if seconds_since_output >= 5:
            heartbeat_note = f"⏳ אין פלט {int(seconds_since_output)} שניות – התהליך עדיין רץ"
            timer_text = self.run_timer_label.text() if self.run_timer_label else ""
            combined = heartbeat_note if not timer_text else f"{timer_text} | {heartbeat_note}"
            if self.run_timer_label:
                self.run_timer_label.setText(combined)
            current_percent = self.run_progress_bar.value() if self.run_progress_bar else 0
            current_label = self.run_stage_label.text() if self.run_stage_label else "Pipeline רץ"
            self._update_header_status(current_label, current_percent, combined, running=True)

    def _on_worker_stall(self, seconds_since_output: float) -> None:
        """Show a visible warning if the worker reports a stall."""
        warning = f"⚠️ אין פלט כבר {int(seconds_since_output)} שניות – ייתכן שהריצה נתקעה"
        self._append_log(warning)
        if self.run_timer_label:
            self.run_timer_label.setText(warning)
        current_percent = self.run_progress_bar.value() if self.run_progress_bar else 0
        current_label = "⚠️ Pipeline ללא פלט"
        self._update_header_status(current_label, current_percent, warning, running=True)

    def _on_worker_sleep_recovery(self) -> None:
        """Notify the user if we resumed after a long pause (e.g., system sleep)."""
        message = "🔄 חזר לפעולה אחרי השהייה – ממשיך מאותה נקודה"
        self._append_log(message)
        if self.run_timer_label:
            self.run_timer_label.setText(message)
        current_percent = self.run_progress_bar.value() if self.run_progress_bar else 0
        current_label = self.run_stage_label.text() if self.run_stage_label else "Pipeline רץ"
        self._update_header_status(current_label, current_percent, message, running=True)

    def _estimate_stage_seconds(self, stage: dict) -> float:
        """Estimate a single stage duration using history and content size."""
        averages = getattr(self, "_performance_averages", {}) or {}
        stage_type = stage.get("type")

        if stage_type == "tts":
            per_entry = averages.get("tts_avg_per_entry")
            if per_entry:
                entries = max(1, getattr(self, "_estimated_dialogue_entries", 0))
                return per_entry * entries
        elif stage_type == "visuals":
            per_image = averages.get("visual_avg_per_image")
            if per_image:
                count = max(1, getattr(self, "_estimated_image_count", 0))
                return per_image * count
        elif stage_type == "video":
            video_time = averages.get("video_avg_time")
            if video_time:
                return video_time

        # Fallback: translate weight to seconds with a conservative multiplier
        return stage.get("weight", 1) * 2.0

    def _stage_duration_estimates(self) -> list[float]:
        """Return estimated seconds per stage (history-aware when available)."""
        return [self._estimate_stage_seconds(stage) for stage in self.pipeline_stages]

    def _refresh_pipeline_status(self, label: Optional[str] = None, percent: Optional[int] = None) -> None:
        """
        Update the pipeline status display with current progress.
        
        Shows the current stage with icon, progress percentage, elapsed time,
        and estimated time remaining (ETA) using stage-based weights for accuracy.
        
        Args:
            label: Optional override for the stage label
            percent: Optional override for the progress percentage
        """
        if not (self.run_stage_label and self.run_progress_bar and self.run_timer_label):
            return
        
        stage = self.pipeline_stages[min(self.pipeline_stage_index, len(self.pipeline_stages) - 1)]
        duration_estimates = self._stage_duration_estimates()
        estimated_total = sum(duration_estimates)
        
        # Calculate progress value using ETA-aware stage duration estimates
        progress_value: int
        if percent is not None:
            progress_value = percent
        elif estimated_total > 0 and self.pipeline_stage_index < len(duration_estimates):
            completed_time = sum(duration_estimates[:self.pipeline_stage_index])
            current_estimate = duration_estimates[self.pipeline_stage_index]
            stage_elapsed = 0.0
            if self._current_stage_start:
                stage_elapsed = max(0.0, time.perf_counter() - self._current_stage_start)
            stage_progress = 0.0
            if current_estimate > 0:
                stage_progress = min(0.95, stage_elapsed / current_estimate)
            progress_value = int(
                ((completed_time + stage_progress * current_estimate) / estimated_total) * 100
            )
        else:
            total_weight = sum(stage.get("weight", 1) for stage in self.pipeline_stages)
            completed_weight = sum(
                stage.get("weight", 1)
                for stage in self.pipeline_stages[:self.pipeline_stage_index]
            )
            progress_value = int((completed_weight / total_weight) * 100) if total_weight > 0 else 0
        
        # Include icon in stage label for visual feedback
        icon = stage.get("icon", "▶️")
        stage_label = label or f"{icon} {stage['label']}"
        self.run_stage_label.setText(stage_label)
        
        bounded_progress = min(100, max(0, progress_value))
        self.run_progress_bar.setValue(bounded_progress)
        
        # Calculate elapsed time and weighted ETA
        timer_text = ""
        if self.pipeline_start_time:
            elapsed = time.perf_counter() - self.pipeline_start_time
            
            # Format elapsed time
            if elapsed > 60:
                elapsed_min = elapsed / 60
                timer_parts = [f"חולפות {elapsed_min:.1f} דקות"]
            else:
                timer_parts = [f"חולפות {elapsed:.0f} שניות"]
            
            # Calculate estimated time remaining using duration estimates
            if bounded_progress > 0 and bounded_progress < 100:
                if estimated_total > 0:
                    remaining = max(0.0, estimated_total - elapsed)
                else:
                    estimated_total = (elapsed / bounded_progress) * 100
                    remaining = max(0, estimated_total - elapsed)

                if remaining > 60:
                    remaining_min = remaining / 60
                    timer_parts.append(f"נותרו ~{remaining_min:.1f} דקות")
                elif remaining > 5:
                    timer_parts.append(f"נותרו ~{remaining:.0f} שניות")
                else:
                    timer_parts.append("כמעט סיימנו...")
            
            timer_text = " | ".join(timer_parts)
            self.run_timer_label.setText(timer_text)
        
        self._update_header_status(stage_label, bounded_progress, timer_text, running=True)

    def _finalize_pipeline_status(self, success: bool) -> None:
        """
        Finalize the pipeline status display after completion.
        
        Shows success or failure state with appropriate icon and
        total elapsed time.
        
        Args:
            success: Whether the pipeline completed successfully
        """
        if not self.run_status_card:
            return
        
        # Use appropriate icon for completion state
        if success:
            label = "✅ Pipeline הושלם בהצלחה!"
        else:
            label = "❌ Pipeline נכשל"
        
        self.pipeline_stage_index = len(self.pipeline_stages) - 1
        
        if self.pipeline_start_time and self.run_timer_label:
            elapsed = time.perf_counter() - self.pipeline_start_time
            if elapsed > 60:
                elapsed_min = elapsed / 60
                self.run_timer_label.setText(f"זמן כולל: {elapsed_min:.1f} דקות ({elapsed:.1f} שניות)")
            else:
                self.run_timer_label.setText(f"זמן כולל: {elapsed:.1f} שניות")
        
        self.pipeline_start_time = None
        percent = 100 if success else self.run_progress_bar.value()
        self._refresh_pipeline_status(label=label, percent=percent)
        timer_text = self.run_timer_label.text() if self.run_timer_label else ""
        self._update_header_status(label, percent, timer_text, running=False)
        if self.pipeline_status_timer:
            self.pipeline_status_timer.stop()
        if self.run_status_card:
            self.run_status_card.setVisible(True)

    def _hide_pipeline_status(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if self.pipeline_status_timer:
            self.pipeline_status_timer.stop()
        if self.run_status_card:
            self.run_status_card.setVisible(False)
        self._current_stage_start = None
        self._hide_header_status()

    def _update_header_status(self, label: str, percent: int, timer_text: str, running: bool) -> None:
        if not (self.header_status_frame and self.header_stage_label and self.header_progress_bar):
            return
        self.header_stage_label.setText(label)
        if self.header_timer_label is not None:
            self.header_timer_label.setText(timer_text)
        self.header_progress_bar.setValue(min(100, max(0, percent)))
        self.header_status_frame.setVisible(True)
        if self.header_status_hide_timer:
            if running:
                self.header_status_hide_timer.stop()
            else:
                self.header_status_hide_timer.start(3500)

    def _hide_header_status(self) -> None:
        if self.header_status_hide_timer:
            self.header_status_hide_timer.stop()
        self._set_header_idle_state()

    def _set_header_idle_state(self) -> None:
        """Show the header banner in an idle state instead of hiding it."""
        if not (self.header_stage_label and self.header_progress_bar):
            return
        self.header_stage_label.setText("Pipeline idle")
        if self.header_timer_label:
            self.header_timer_label.setText("Waiting for next run")
        self.header_progress_bar.setValue(0)
        if self.header_status_frame:
            self.header_status_frame.setVisible(False)

    def _start_run_log(self) -> None:
        self.log_buffer = []

    def _persist_run_context_to_history(self) -> None:
        """
        Persist current run context (transcript, materials, URLs, chat log) to history.
        
        Called after successful pipeline run to save all user context for future loads.
        """
        if not self.pending_run_dir:
            self.logger.debug("[_persist_run_context_to_history] No pending_run_dir, skipping")
            return
            
        self.logger.info("[_persist_run_context_to_history] Saving context for: %s", self.pending_run_dir)
        
        materials = [
            self.materials_list.item(i).text()
            for i in range(self.materials_list.count())
        ]
        urls = [line.strip() for line in self.urls_edit.toPlainText().splitlines() if line.strip()]
        chat_log = [self.chat_history.item(i).text() for i in range(self.chat_history.count())]
        transcript_path = self.transcript_edit.text().strip()
        
        self.logger.debug("[_persist_run_context_to_history] transcript_path=%s, materials=%d, urls=%d, chat_log=%d",
                         transcript_path, len(materials), len(urls), len(chat_log))
        
        patch = {
            "transcript_path": transcript_path,
            "materials": materials,
            "urls": urls,
            "chat_log": chat_log,
        }
        
        try:
            HistoryManager(self.settings.output_base_dir).update(self.pending_run_dir, patch)
            self.logger.info("[_persist_run_context_to_history] Context saved successfully")
        except Exception as e:
            self.logger.error("[_persist_run_context_to_history] Failed to save context: %s", e)

    def _save_chat_to_history(self) -> None:
        """
        Save current chat history to the active project's history entry.
        
        This ensures chat history persists even without running the pipeline.
        Called when:
        - User sends a chat message
        - Project is switched
        - Application closes
        """
        if not self.active_history_entry:
            self.logger.debug("[_save_chat_to_history] No active history entry, skipping")
            return
            
        run_dir = self.active_history_entry.get("run_dir")
        if not run_dir:
            self.logger.debug("[_save_chat_to_history] No run_dir in active entry, skipping")
            return
            
        if not hasattr(self, "chat_history") or self.chat_history.count() == 0:
            self.logger.debug("[_save_chat_to_history] No chat history to save")
            return
            
        chat_log = [self.chat_history.item(i).text() for i in range(self.chat_history.count())]
        
        self.logger.info("[_save_chat_to_history] Saving %d messages to history for: %s", 
                        len(chat_log), Path(run_dir).name)
        
        try:
            # Also save transcript path if available
            patch = {"chat_log": chat_log}
            if hasattr(self, "transcript_edit"):
                transcript_path = self.transcript_edit.text().strip()
                if transcript_path and Path(transcript_path).exists():
                    patch["transcript_path"] = transcript_path
                    
            HistoryManager(self.settings.output_base_dir).update(run_dir, patch)
            self.logger.debug("[_save_chat_to_history] Chat history saved successfully")
        except Exception as e:
            self.logger.error("[_save_chat_to_history] Failed to save chat: %s", e)

    def _open_outputs(self) -> None:
        path = Path(self.output_dir_edit.text().strip() or self.settings.output_base_dir)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_cost_center(self) -> None:
        """Open the Cost Center dialog for budget tracking and analytics."""
        self.cost_totals = self._compute_cost_totals()
        dialog = CostCenterDialog(
            settings=self.settings,
            history=self.history,
            cost_totals=self.cost_totals,
            section_label_factory=self._section_label,
            card_widget_factory=self._card_widget,
            helper_label_factory=self._helper_label,
            parent=self,
        )
        dialog.exec()

    def _open_chat_settings(self) -> None:
        dialog = ChatAppearanceDialog(self.settings, self.font_library_dir, self._chat_font_options, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            values = dialog.selected_values()
            self.settings.save_ui_preferences(values)
            self._apply_chat_preferences()
            if self.chat_history:
                self.chat_history.repaint()

    def _open_visual_settings(self) -> None:
        """
        Open the visual settings dialog for configuring visual generator options.
        
        Handles:
            - Visual generator selection (Manim, Imagen, VEO, Hybrid)
            - Image count settings
            - AI helper request for metadata enrichment
        """
        start_time = time.time()
        self.logger.info("[_open_visual_settings] Opening visual settings dialog")
        
        # Track if AI helper was requested via signal
        self._pending_ai_helper = False
        
        def on_ai_helper_signal():
            """Handle AI helper request signal from dialog."""
            self.logger.info("[_open_visual_settings] Received ai_helper_requested signal")
            self._pending_ai_helper = True
        
        try:
            # Create dialog with callback for AI helper
            dialog = VisualSettingsDialog(
                self.settings, 
                self,
                ai_helper_callback=lambda: setattr(self, '_pending_ai_helper', True)
            )
            
            # Connect signal as backup mechanism
            dialog.ai_helper_requested.connect(on_ai_helper_signal)
            
            self.logger.debug("[_open_visual_settings] Dialog created, executing...")
            result = dialog.exec()
            
            self.logger.info("[_open_visual_settings] Dialog returned with result: %s", result)
            
            # Check if AI helper was requested (multiple methods for reliability)
            trigger_ai_flag = dialog.should_trigger_ai_helper()
            trigger_ai = trigger_ai_flag or self._pending_ai_helper
            
            self.logger.info("[_open_visual_settings] Dialog closed: result=%s, trigger_ai_flag=%s, pending_ai_helper=%s, trigger_ai=%s",
                            result, trigger_ai_flag, self._pending_ai_helper, trigger_ai)
            self._append_log(f"[Visual Settings] Dialog result: {result}, trigger_ai: {trigger_ai}")
            
            # Always try to save settings if dialog was accepted (result == 1 for Accepted)
            if result == QDialog.DialogCode.Accepted or result == 1:
                self.logger.info("[_open_visual_settings] Dialog accepted, saving settings...")
                values = dialog.get_saved_values()
                # Log image_count before saving
                image_count = values.get("image_count", 5)
                visual_gen = values.get("visual_generator", "manim")
                
                self.logger.info("[_open_visual_settings] Saving settings: image_count=%s, visual_generator=%s",
                               image_count, visual_gen)
                self._log(f"Visual settings: image_count={image_count}, visual_generator={visual_gen}")
                
                if not getattr(dialog, "_auto_saved", False):
                    self.logger.debug("[_open_visual_settings] Dialog auto-save not triggered, saving now")
                    self.settings.save_ui_preferences(values)
                
                # Verify image_count was saved
                saved_count = getattr(self.settings, 'image_count', None)
                self.logger.debug("[_open_visual_settings] Verified saved image_count: %s", saved_count)
                self._log(f"✅ הגדרות ויזואליות נשמרו: {image_count} תמונות, {visual_gen}")
                
                # Update status bar with new visual generator
                gen_names = {"manim": "Manim", "imagen": "Imagen", "imagen_manim": "Imagen+Manim", "veo": "VEO", "hybrid": "Hybrid"}
                self._log(f"מנוע ויזואלי: {gen_names.get(visual_gen, visual_gen)}")
            else:
                self.logger.info("[_open_visual_settings] Dialog cancelled")
            
            # Trigger AI helper if requested (regardless of cancel - we already confirmed in the sub-dialog)
            if trigger_ai:
                self.logger.info("[_open_visual_settings] AI helper requested, scheduling trigger...")
                self._log("🎨 מעביר לצ'אט להעשרת מטא-דאטה...")
                self._append_log("[Visual Settings] Triggering AI helper...")
                
                # Ensure window is active and raised
                self.raise_()
                self.activateWindow()
                QApplication.processEvents()
                
                # Use QTimer to delay so dialog fully closes and UI is ready
                QTimer.singleShot(500, self._trigger_ai_image_enrichment)
                self.logger.debug("[_open_visual_settings] QTimer.singleShot scheduled for AI helper (500ms delay)")
                    
        except Exception as e:
            self.logger.error("[_open_visual_settings] Error: %s\n%s", e, traceback.format_exc())
            self._append_log(f"[Visual Settings] Error: {e}")
            
        finally:
            elapsed = time.time() - start_time
            self.logger.debug("[_open_visual_settings] Completed in %.3fs", elapsed)

    # --- History & analytics ----------------------------------------
    def _refresh_history(self) -> None:
        self.history = HistoryManager(self.settings.output_base_dir)
        self.active_history_entry = None
        self._load_history_list()
        self._refresh_project_tree()
        self._refresh_timeline()
        self.cost_totals = self._compute_cost_totals()
        self._update_project_stats()
        self._update_output_gallery()

    def _load_history_list(self) -> None:
        self.projects_list.clear()
        self.history_index = {}
        valid_entries = []
        invalid_count = 0

        def parse_timestamp(raw: str | None) -> float:
            """Convert various timestamp formats to epoch seconds for stable sorting."""
            if not raw:
                return 0.0
            if isinstance(raw, (int, float)):
                return float(raw)
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
            except Exception:
                try:
                    return datetime.strptime(str(raw), "%Y-%m-%d").timestamp()
                except Exception:
                    return 0.0

        def format_datetime(entry: Dict) -> str:
            raw_ts = (
                entry.get("timestamp")
                or entry.get("generated_at")
                or entry.get("date")
            )
            if raw_ts:
                try:
                    dt = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            return entry.get("date", "—")

        # Load from history and validate paths
        for entry in self.history.all():
            entry = validate_history_entry_paths(entry)
            entry.setdefault("timestamp", entry.get("generated_at") or entry.get("date"))
            path_valid = entry.get("path_valid", True)

            if not path_valid:
                invalid_count += 1
                continue

            valid_entries.append(entry)
            run_dir = entry.get("run_dir")
            if run_dir:
                self.history_index[str(run_dir)] = entry

        # Log cleanup if any invalid entries were removed
        if invalid_count > 0:
            self._append_log(f"נמחקו {invalid_count} רשומות עם תיקיות חסרות מההיסטוריה")

        # Discover additional projects not in history.json
        discovered_entries = self._scan_filesystem_for_projects()
        if discovered_entries:
            valid_entries.extend(discovered_entries)

        # Sort by timestamp (newest first)
        valid_entries.sort(
            key=lambda e: parse_timestamp(
                e.get("timestamp") or e.get("generated_at") or e.get("date")
            ),
            reverse=True,
        )

        # Render items with date+time and topic
        for entry in valid_entries:
            failed = entry.get("failed", False)
            has_audio = bool(entry.get("final_audio"))
            status_icon = "❌ " if failed else "✅ " if has_audio else "📝 "
            date_label = format_datetime(entry)
            topic = entry.get("topic", "")
            extra = " • זוהה" if entry.get("discovered") else ""
            label = f"{status_icon}{date_label} - {topic}{extra}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.projects_list.addItem(item)
    
    def _scan_filesystem_for_projects(self) -> List[Dict]:
        """Scan output directory for projects that might not be in history."""
        output_dir = self.settings.output_base_dir
        discovered_entries: List[Dict] = []
        if not output_dir.exists():
            return discovered_entries

        for item in output_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith(".") or item.name.startswith("_"):
                continue
            if str(item) in self.history_index:
                continue

            metadata_file = item / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                entry = self._build_history_entry(item, metadata)
                entry["discovered"] = True
                self.history.record(entry)
                discovered_entries.append(entry)
                self.history_index[str(item)] = entry
            except (json.JSONDecodeError, OSError):
                continue

        return discovered_entries

    def _update_project_details(self) -> None:
        items = self.projects_list.selectedItems()
        if not items:
            self.active_history_entry = None
            self._update_story_preview()
            return
        entry = items[0].data(Qt.ItemDataRole.UserRole) or {}
        if entry:
            self.active_history_entry = entry
            self._update_output_gallery(entry)
            self._update_story_preview(entry)

    def _handle_project_double_click(self, _: QListWidgetItem) -> None:
        self._load_selected_history_entry(quiet=True)

    def _load_selected_history_entry(self, quiet: bool = False) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        self._apply_history_entry(entry, silent=True)
        if not quiet:
            topic = entry.get("topic") or entry.get("run_dir", "project")
            QMessageBox.information(self, "נטען", f"הריצה '{topic}' נטענה לעריכה.")

    def _load_latest_history_entry(self) -> None:
        runs = self.history.all()
        if not runs:
            QMessageBox.information(self, "אין ריצות", "עדיין אין היסטוריה לטעון.")
            return
        
        # Find the first valid entry
        valid_entry = None
        for entry in runs:
            entry = validate_history_entry_paths(entry)
            if entry.get("path_valid", True):
                valid_entry = entry
                break
        
        if not valid_entry:
            QMessageBox.warning(
                self, 
                "אין ריצות תקינות", 
                "כל הריצות בהיסטוריה מפנות לתיקיות שנמחקו או שונו.\nנסה לרענן את רשימת הפרויקטים."
            )
            return
        
        self.projects_list.clearSelection()
        if self.projects_list.count():
            self.projects_list.setCurrentRow(0)
        self._apply_history_entry(valid_entry, silent=True)
        topic = valid_entry.get("topic") or "פרויקט"
        QMessageBox.information(self, "נטען", f"הריצה האחרונה נטענה לעריכה.\nנושא: {topic}")

    def _refresh_project_tree(self) -> None:
        if not hasattr(self, "project_cards"):
            return
        self.project_card_entries = self.history.all()
        self._apply_project_card_filter()

    def _apply_project_card_filter(self) -> None:
        if not hasattr(self, "project_cards"):
            return
        pattern = (getattr(self, "card_filter", QLineEdit()).text() or "").lower().strip()
        self.project_cards.clear()
        for entry in self.project_card_entries:
            haystack_parts = [
                str(entry.get("topic") or ""),
                str(entry.get("date") or ""),
                str(entry.get("run_dir") or ""),
                " ".join(str(lab) for lab in (entry.get("labs") or [])),
            ]
            haystack = " ".join(haystack_parts).lower()
            if pattern and pattern not in haystack:
                continue
            widget = self._create_project_card(entry)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.project_cards.addItem(item)
            self.project_cards.setItemWidget(item, widget)
        if self.project_cards.count() == 0:
            placeholder = QListWidgetItem("לא נמצאו תוצרים להצגה.")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.project_cards.addItem(placeholder)
        self._update_card_buttons()

    def _create_project_card(self, entry: Dict) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        header = QHBoxLayout()
        
        # Check path validity first
        entry = validate_history_entry_paths(entry)
        path_valid = entry.get("path_valid", True)
        
        # Status icon based on state
        failed = entry.get("failed", False)
        discovered = entry.get("discovered", False)
        has_audio = bool(entry.get("final_audio"))
        
        if not path_valid:
            status_icon = "🚫"
            status_style = "color:#6b7280;"  # Gray for missing paths
        elif failed:
            status_icon = "❌"
            status_style = "color:#ef4444;"
        elif discovered:
            status_icon = "📁"
            status_style = "color:#f97316;"
        elif has_audio:
            status_icon = "✅"
            status_style = "color:#22c55e;"
        else:
            status_icon = "📝"
            status_style = "color:#94a3b8;"
        
        status_label = QLabel(status_icon)
        status_label.setStyleSheet(f"font-size:16px;{status_style}")
        header.addWidget(status_label)
        
        title = QLabel(entry.get("topic", "ללא נושא"))
        title.setStyleSheet("font-size:15px;font-weight:600;")
        header.addWidget(title)
        header.addStretch(1)
        date = QLabel(entry.get("date", "—"))
        date.setStyleSheet("color:#94a3b8;")
        header.addWidget(date)
        layout.addLayout(header)
        
        # Show failure message if failed or path invalid
        if not path_valid:
            failure_label = QLabel("⚠️ תיקייה חסרה או נמחקה")
            failure_label.setStyleSheet("color:#6b7280;font-size:11px;")
            layout.addWidget(failure_label)
        elif failed and entry.get("failure_message"):
            failure_label = QLabel(f"שגיאה: {entry.get('failure_message', '')[:50]}...")
            failure_label.setStyleSheet("color:#ef4444;font-size:11px;")
            layout.addWidget(failure_label)

        cost_info = entry.get("costs") or {}
        cost_line = f"${float(cost_info.get('total_cost_usd', 0.0)):.2f}"
        tts_chars = int(cost_info.get("tts_characters", 0))
        if tts_chars:
            cost_line += f" · {tts_chars:,} תווי TTS"
        layout.addWidget(self._helper_label(cost_line))

        badges = self._project_badges(entry)
        if badges:
            badges_row = QHBoxLayout()
            for badge in badges:
                pill = QLabel(badge)
                pill.setStyleSheet(
                    "background-color:#1d4ed8; color:#f8fafc; padding:4px 10px; border-radius:14px;"
                )
                badges_row.addWidget(pill)
            badges_row.addStretch(1)
            layout.addLayout(badges_row)

        actions_row = QHBoxLayout()

        def make_btn(text: str, handler, enabled: bool = True) -> QPushButton:
            btn = QPushButton(text)
            btn.setEnabled(enabled)
            btn.clicked.connect(handler)
            return btn

        run_dir = entry.get("run_dir")
        actions_row.addWidget(
            make_btn(
                "תיקייה",
                lambda _, path=run_dir: self._open_path(Path(path)) if path else None,
                bool(run_dir),
            )
        )
        audio_path = entry.get("final_audio")
        actions_row.addWidget(
            make_btn(
                "אודיו",
                lambda _, path=audio_path: self._open_path(Path(path)) if path else None,
                bool(audio_path),
            )
        )
        video_path = entry.get("final_video")
        actions_row.addWidget(
            make_btn(
                "וידאו",
                lambda _, path=video_path: self._open_path(Path(path)) if path else None,
                bool(video_path),
            )
        )
        story_path = entry.get("story")
        actions_row.addWidget(
            make_btn(
                "Story",
                lambda _, path=story_path: self._open_path(Path(path)) if path else None,
                bool(story_path),
            )
        )
        actions_row.addWidget(
            make_btn(
                "טען",
                lambda _, e=entry: self._apply_history_entry(e, silent=True),
            )
        )
        actions_row.addStretch(1)
        layout.addLayout(actions_row)
        return card

    def _filter_project_cards(self, _: str) -> None:
        self._apply_project_card_filter()

    def _selected_card_entry(self) -> Optional[Dict]:
        if not hasattr(self, "project_cards"):
            return None
        items = self.project_cards.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole) or {}

    def _update_card_buttons(self) -> None:
        entry = self._selected_card_entry()
        has_entry = bool(entry)
        if hasattr(self, "card_open_btn"):
            self.card_open_btn.setEnabled(has_entry)
        if hasattr(self, "card_delete_btn"):
            self.card_delete_btn.setEnabled(has_entry)

    def _open_selected_card_dir(self) -> None:
        entry = self._selected_card_entry()
        if not entry:
            QMessageBox.information(self, "בחירה", "בחרו ריצה מסייר התוצרים.")
            return
        path = entry.get("run_dir")
        if path:
            self._open_path(Path(path))

    def _delete_selected_card(self) -> None:
        entry = self._selected_card_entry()
        if not entry:
            QMessageBox.information(self, "בחירה", "בחרו ריצה למחיקה.")
            return
        run_dir = entry.get("run_dir")
        if not run_dir:
            QMessageBox.warning(self, "שגיאה", "לא נמצאה תיקייה לשורה שנבחרה.")
            return
        path = Path(run_dir)
        if not path.exists():
            QMessageBox.warning(self, "שגיאה", "התיקייה שנבחרה לא קיימת.")
            return
        reply = QMessageBox.question(
            self,
            "אישור מחיקה",
            f"האם למחוק לצמיתות את '{path.name}' וכל התוצרים שבו?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(path)
        except OSError as exc:
            QMessageBox.warning(self, "שגיאה", f"נכשל במחיקת הפרויקט:\n{exc}")
            return
        self.history.remove_run(path)
        self.active_history_entry = None
        self._refresh_history()
        QMessageBox.information(self, "נמחק", "הפרויקט הוסר בהצלחה.")

    def _build_history_entry(self, run_dir: Path, metadata: Dict) -> Dict:
        date_str = metadata.get("date", "unknown")
        timestamp = metadata.get("generated_at") or metadata.get("timestamp") or date_str
        
        # Find audio files (mp3)
        audio_pattern = f"lecture_{date_str}_summary.mp3"
        audio_file = run_dir / audio_pattern
        if not audio_file.exists():
            # Try to find any mp3 file
            mp3_files = list(run_dir.glob("*.mp3"))
            audio_file = mp3_files[0] if mp3_files else None
        
        # Find video files (mp4)
        video_pattern = f"lecture_{date_str}_summary.mp4"
        video_file = run_dir / video_pattern
        if not video_file.exists():
            # Try to find any mp4 file
            mp4_files = list(run_dir.glob("*.mp4"))
            video_file = mp4_files[0] if mp4_files else None
        
        entry = {
            "topic": metadata.get("topic"),
            "date": date_str,
            "timestamp": timestamp,
            "run_dir": str(run_dir),
            "labs": metadata.get("labs", []),
            "summary": metadata.get("summary", ""),
            "key_concepts": metadata.get("key_concepts", []),
            "reading_list": metadata.get("reading_list", []),
            "slide_deck": str(run_dir / "summary.pptx") if (run_dir / "summary.pptx").exists() else "",
            "story": "",
            "final_audio": str(audio_file) if audio_file and audio_file.exists() else "",
            "final_video": str(video_file) if video_file and video_file.exists() else "",
            "dialogue": str(run_dir / "dialogue.json") if (run_dir / "dialogue.json").exists() else "",
            "costs": {},
        }
        story_md = run_dir / "story.md"
        if story_md.exists():
            entry["story"] = str(story_md)
        elif (run_dir / "story.json").exists():
            entry["story"] = str(run_dir / "story.json")
        entry = self._hydrate_history_entry(run_dir, entry)
        self.history_index[str(run_dir)] = entry
        return entry

    def _hydrate_history_entry(self, run_dir: Path, entry: Dict) -> Dict:
        history_manager = getattr(self, "history", None)
        records = history_manager.all() if history_manager else HistoryManager(self.settings.output_base_dir).all()
        for record in records:
            if record.get("run_dir") == str(run_dir):
                for key in ("chat_log", "materials", "urls", "transcript_path"):
                    value = record.get(key)
                    if value:
                        entry[key] = value
                break
        return entry

    def _apply_history_entry(self, entry: Dict, silent: bool = False) -> None:
        """
        Apply a history entry to load a project with all its saved state.
        
        Loads:
        - Project directory and metadata
        - Transcript path
        - Materials and URLs
        - Chat history with the agent
        
        Args:
            entry: History entry dictionary
            silent: If True, suppress UI messages
        """
        start_time = time.time()
        topic = entry.get("topic", "unknown")
        self.logger.info("[_apply_history_entry] Applying entry for topic: %s", topic)
        
        run_dir = entry.get("run_dir")
        if run_dir:
            run_path = Path(run_dir)
            self.logger.debug("[_apply_history_entry] run_dir: %s, exists: %s", run_dir, run_path.exists())
            
            if run_path.exists():
                # Pass the original history entry to preserve transcript_path and other fields
                self._load_project_from_directory(run_path, silent=silent, history_entry=entry)
                self._update_output_gallery(entry)
            else:
                self.logger.error("[_apply_history_entry] Directory not found: %s", run_dir)
                if not silent:
                    QMessageBox.warning(
                        self, 
                        "תיקייה חסרה", 
                        f"התיקייה לא נמצאה:\n{run_dir}\n\nיתכן שהתיקייה הועברה או נמחקה."
                    )
                return
        else:
            self.logger.error("[_apply_history_entry] Entry has no run_dir field")
            if not silent:
                QMessageBox.warning(self, "שגיאה", "רשומת ההיסטוריה לא מכילה נתיב תיקייה.")
            return
            
        # Load materials
        materials = entry.get("materials") or []
        self.logger.debug("[_apply_history_entry] Loading %d materials", len(materials))
        if hasattr(self, "materials_list"):
            self.materials_list.clear()
            for path in materials:
                self.materials_list.addItem(path)
                
        # Load URLs
        urls = entry.get("urls") or []
        self.logger.debug("[_apply_history_entry] Loading %d URLs", len(urls))
        if hasattr(self, "urls_edit"):
            self.urls_edit.setPlainText("\n".join(urls))
        self._sync_materials_to_session()
        
        # Select the corresponding item in the projects list
        if topic and hasattr(self, "projects_list"):
            for i in range(self.projects_list.count()):
                item = self.projects_list.item(i)
                if item and topic in item.text():
                    self.projects_list.setCurrentRow(i)
                    break
        
        # Load chat_log (conversation with the agent) into chat_history
        # This happens after _load_project_from_directory to ensure it overrides any previous content
        # Note: dialogue.json contains the generated podcast dialogue, NOT the chat with the agent
        chat_log = entry.get("chat_log") or []
        self.logger.info("[_apply_history_entry] Loading chat_log with %d messages", len(chat_log))
        
        if chat_log and hasattr(self, "chat_history"):
            self.chat_history.clear()
            user_speakers = {"אני", "you", "user", "משתמש"}
            for message in chat_log:
                item = QListWidgetItem(message)
                # Extract speaker name to determine alignment
                if ": " in message:
                    speaker = message.split(": ", 1)[0].lower()
                    is_user = speaker in user_speakers or speaker == "אני"
                else:
                    is_user = False
                align = Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(align)
                self.chat_history.addItem(item)
            self.chat_history.scrollToBottom()
            self.logger.debug("[_apply_history_entry] Chat history restored with %d messages", 
                             self.chat_history.count())
        elif hasattr(self, "chat_history") and not chat_log:
            # Clear chat_history if no chat_log is available
            self.logger.debug("[_apply_history_entry] No chat_log found, clearing chat_history")
            self.chat_history.clear()
            
        self.active_history_entry = entry
        self._update_onboarding_tip()
        try:
            self._apply_chat_preferences()
        except Exception:
            pass
        
        elapsed = time.time() - start_time
        self.logger.info("[_apply_history_entry] Completed in %.3fs", elapsed)

    def _project_badges(self, entry: Dict) -> List[str]:
        badges: List[str] = []
        run_dir = entry.get("run_dir")
        if not run_dir:
            return badges
        path = Path(run_dir)
        if any(path.glob("*.mp3")) or (entry.get("final_audio") and Path(entry["final_audio"]).exists()):
            badges.append("🎧 אודיו")
        if any(path.glob("*.mp4")) or (entry.get("final_video") and Path(entry["final_video"]).exists()):
            badges.append("🎬 וידאו")
        if (path / "summary.pptx").exists() or entry.get("slide_deck"):
            badges.append("📊 PPTX")
        if (path / "story.md").exists() or (path / "story.json").exists() or entry.get("story"):
            badges.append("📖 Story")
        return badges

    def _browse_project_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "בחר תיקיית פרויקט", str(self.settings.output_base_dir))
        if not path:
            return
        run_dir = Path(path)
        
        # Try to find existing history entry for this project to load chat_log and other saved data
        history_entry = None
        history_manager = HistoryManager(self.settings.output_base_dir)
        for record in history_manager.all():
            if record.get("run_dir") == str(run_dir):
                history_entry = record
                break
        
        # Load the project - if history_entry exists, it will load chat_log and transcript_path
        if history_entry:
            self._apply_history_entry(history_entry, silent=False)
        else:
            self._load_project_from_directory(run_dir)
        
        # Save transcript_path to history if it was found and loaded
        # This ensures the transcript will be available in future loads
        if hasattr(self, "transcript_edit") and self.transcript_edit.text().strip():
            transcript_path = self.transcript_edit.text().strip()
            if transcript_path and Path(transcript_path).exists():
                try:
                    patch = {"transcript_path": transcript_path}
                    history_manager.update(run_dir, patch)
                except Exception:
                    # Silently fail if history update fails - transcript will still be loaded in UI
                    pass

    def _log_load_error(self, message: str) -> None:
        """Persist load errors to a root-level log for debugging."""
        try:
            log_path = Path("load_error.log")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def _load_project_from_directory(self, run_dir: Path, silent: bool = False, history_entry: Optional[Dict] = None) -> None:
        """
        Load a project from a directory.
        
        Attempts to find and load transcript from multiple sources:
        1. History entry transcript_path (highest priority)
        2. Processing log file references
        3. Files matching transcript naming patterns
        4. Largest txt file in directory (fallback)
        
        Args:
            run_dir: Path to the project directory
            silent: If True, suppress UI messages
            history_entry: Optional history entry with saved fields
        """
        start_time = time.time()
        load_error: Optional[str] = None
        self.logger.info("[_load_project_from_directory] Loading project from: %s", run_dir)
        self.logger.debug("[_load_project_from_directory] silent=%s, history_entry=%s", 
                         silent, "provided" if history_entry else "None")
        
        try:
            metadata_file = run_dir / "metadata.json"
            metadata = None
            
            # Try to load metadata.json if it exists
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    self.logger.debug("[_load_project_from_directory] Metadata loaded: topic=%s", 
                                     metadata.get("topic", "unknown"))
                except json.JSONDecodeError as exc:
                    load_error = f"Failed to parse metadata.json: {exc}"
                    self.logger.error("[_load_project_from_directory] %s", load_error)
                    raise
            
            # If metadata.json doesn't exist, try to create it from history entry
            if metadata is None:
                self.logger.warning("[_load_project_from_directory] metadata.json not found in %s, attempting to create from history", run_dir)
                
                if history_entry:
                    # Create metadata from history entry
                    metadata = {
                        "topic": history_entry.get("topic", run_dir.name),
                        "date": history_entry.get("date", datetime.now().strftime("%Y-%m-%d")),
                        "summary": history_entry.get("summary", ""),
                        "key_concepts": history_entry.get("key_concepts", []),
                        "labs": history_entry.get("labs", []),
                        "reading_list": history_entry.get("reading_list", []),
                    }
                    
                    # Try to save temporary metadata.json for future loads
                    try:
                        metadata_file.write_text(
                            json.dumps(metadata, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                        self.logger.info("[_load_project_from_directory] Created temporary metadata.json from history entry")
                    except Exception as e:
                        self.logger.warning("[_load_project_from_directory] Failed to save temporary metadata.json: %s", e)
                else:
                    # If no history entry, create basic metadata from directory name
                    dir_name = run_dir.name
                    # Try to extract topic from directory name (remove date prefix if exists)
                    if "_" in dir_name and dir_name[0].isdigit():
                        # Format: "2025-12-02_project-name" -> extract "project-name"
                        parts = dir_name.split("_", 1)
                        topic = parts[1] if len(parts) > 1 else dir_name
                        date_str = parts[0] if len(parts) > 0 else datetime.now().strftime("%Y-%m-%d")
                    else:
                        topic = dir_name
                        date_str = datetime.now().strftime("%Y-%m-%d")
                    
                    metadata = {
                        "topic": topic,
                        "date": date_str,
                        "summary": "",
                        "key_concepts": [],
                        "labs": [],
                        "reading_list": [],
                    }
                    
                    # Try to save temporary metadata.json
                    try:
                        metadata_file.write_text(
                            json.dumps(metadata, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                        self.logger.info("[_load_project_from_directory] Created basic metadata.json from directory name")
                    except Exception as e:
                        self.logger.warning("[_load_project_from_directory] Failed to save basic metadata.json: %s", e)
                
                if not silent:
                    QMessageBox.warning(
                        self, 
                        "metadata.json חסר", 
                        f"לא נמצא metadata.json בתיקייה.\nנוצר מטא-דאטה זמני מהנתונים הקיימים.\nנושא: {metadata.get('topic', 'לא צוין')}"
                    )
            
            # Merge history metadata without overwriting existing keys
            if metadata and history_entry:
                for key in ("summary", "key_concepts", "labs", "reading_list", "date", "topic"):
                    if not metadata.get(key) and history_entry.get(key):
                        metadata[key] = history_entry.get(key)
                        self.logger.debug("[_load_project_from_directory] Filled missing %s from history", key)
            
            entry = self._build_history_entry(run_dir, metadata)
            
            # If history_entry was provided, merge its fields (especially transcript_path) into entry
            if history_entry:
                for key in ("transcript_path", "materials", "urls", "chat_log"):
                    value = history_entry.get(key)
                    if value:
                        entry[key] = value
                        self.logger.debug("[_load_project_from_directory] Merged %s from history: %s", 
                                         key, value[:100] if isinstance(value, str) else f"({len(value)} items)")
            
            self.active_history_entry = entry
            self.current_metadata = metadata
            self.chat_session.import_metadata(metadata)
            self._update_metadata_preview()
            self._apply_chat_preferences()
            
            # Auto-fill custom_project_name field with project name
            if hasattr(self, "custom_project_name"):
                project_name = None
                
                # Try to extract name from directory (remove date prefix if exists)
                dir_name = run_dir.name
                if "_" in dir_name:
                    # Format: "2025-12-02_project-name" -> "project-name"
                    parts = dir_name.split("_", 1)
                    if len(parts) == 2 and parts[0][0].isdigit():
                        # Remove date prefix and convert dashes to spaces for readability
                        project_name = parts[1].replace("-", " ")
                    else:
                        # No date prefix, use directory name as-is
                        project_name = dir_name.replace("-", " ")
                else:
                    # No underscore, use directory name
                    project_name = dir_name.replace("-", " ")
                
                # If metadata has a topic, prefer it over directory name
                if metadata and metadata.get("topic"):
                    project_name = metadata.get("topic")
                
                if project_name:
                    self.custom_project_name.setText(project_name)
                    self.logger.debug("[_load_project_from_directory] Auto-filled custom_project_name: %s", project_name)
            
            # Load transcript using helper function
            transcript_found, transcript_source = self._find_and_load_transcript(run_dir, entry, silent)
            
            if transcript_found:
                self.logger.info("[_load_project_from_directory] Transcript loaded from %s", transcript_source)
                # Save transcript path to history for future loads
                if hasattr(self, "transcript_edit"):
                    loaded_path = self.transcript_edit.text().strip()
                    if loaded_path:
                        try:
                            HistoryManager(self.settings.output_base_dir).update(run_dir, {"transcript_path": loaded_path})
                            self.logger.debug("[_load_project_from_directory] Saved transcript_path to history")
                        except Exception as e:
                            self.logger.warning("[_load_project_from_directory] Failed to save transcript_path to history: %s", e)
            else:
                self.logger.warning("[_load_project_from_directory] No transcript found for project")
                if not silent:
                    QMessageBox.warning(self, "תמלול חסר", "לא נמצא קובץ תמלול המשויך לפרויקט זה.\nנא לבחור תמלול ידנית.")

            if not silent and not load_error:
                QMessageBox.information(self, "נטען", f"הפרויקט '{run_dir.name}' נטען לעריכה.")
                
            elapsed = time.time() - start_time
            self.logger.info("[_load_project_from_directory] Completed in %.3fs (transcript: %s)", 
                            elapsed, transcript_source if transcript_found else "not found")
        except Exception as exc:
            load_error = load_error or str(exc)
            self._log_load_error(f"{run_dir}: {load_error}")
            self.logger.error("[_load_project_from_directory] Failed to load project: %s", exc)
            if not silent:
                QMessageBox.critical(self, "כשל בטעינת פרויקט", f"לא ניתן לטעון את הפרויקט:\n{load_error}")
    
    def _find_and_load_transcript(self, run_dir: Path, entry: Dict, silent: bool = False) -> Tuple[bool, str]:
        """
        Find and load transcript from multiple sources.
        
        Search order:
        1. History entry transcript_path
        2. Processing log file references
        3. Files matching transcript patterns in run_dir
        4. Largest txt file (fallback)
        
        Args:
            run_dir: Project directory
            entry: History entry with potential transcript_path
            silent: If True, suppress UI messages
            
        Returns:
            Tuple of (found: bool, source: str describing where it was found)
        """
        self.logger.debug("[_find_and_load_transcript] Searching for transcript in: %s", run_dir)
        
        if not hasattr(self, "transcript_edit"):
            self.logger.error("[_find_and_load_transcript] transcript_edit widget not found")
            return False, "widget_missing"
        
        # 1. Check history entry (highest priority)
        transcript_path_str = entry.get("transcript_path")
        if transcript_path_str:
            transcript_path = Path(transcript_path_str)
            self.logger.debug("[_find_and_load_transcript] Checking history path: %s", transcript_path)
            if transcript_path.exists():
                self.transcript_edit.blockSignals(True)
                self.transcript_edit.setText(str(transcript_path))
                self.transcript_edit.blockSignals(False)
                if not silent:
                    self._log(f"תמלול נטען מהיסטוריה: {transcript_path.name}")
                return True, "history_entry"
            else:
                self.logger.warning("[_find_and_load_transcript] History path does not exist: %s", transcript_path)
        
        # 2. Check processing log for transcript references
        processing_log = run_dir / "processing_log.txt"
        if processing_log.exists():
            self.logger.debug("[_find_and_load_transcript] Parsing processing_log.txt")
            try:
                log_text = processing_log.read_text(encoding="utf-8")
                for line in log_text.splitlines():
                    if "transcript" in line.lower() or ".txt" in line:
                        parts = line.split()
                        for part in parts:
                            if ".txt" in part:
                                p = Path(part.strip("'\",[]"))
                                if p.exists():
                                    self.transcript_edit.blockSignals(True)
                                    self.transcript_edit.setText(str(p))
                                    self.transcript_edit.blockSignals(False)
                                    self.logger.info("[_find_and_load_transcript] Found in processing log: %s", p)
                                    return True, "processing_log"
            except OSError as e:
                self.logger.warning("[_find_and_load_transcript] Error reading processing log: %s", e)
        
        # 3. Look for files matching transcript patterns
        self.logger.debug("[_find_and_load_transcript] Searching for transcript-named files")
        for cand in run_dir.glob("*.txt"):
            if "transcript" in cand.name.lower() or "תמלול" in cand.name:
                self.transcript_edit.blockSignals(True)
                self.transcript_edit.setText(str(cand))
                self.transcript_edit.blockSignals(False)
                self.logger.info("[_find_and_load_transcript] Found by name pattern: %s", cand)
                return True, f"pattern_match:{cand.name}"
            
        # 4. Fallback: largest txt file (excluding logs)
        txt_files = list(run_dir.glob("*.txt"))
        if txt_files:
            txt_files = [f for f in txt_files if "log" not in f.name.lower()]
            if txt_files:
                largest = max(txt_files, key=lambda p: p.stat().st_size)
                self.transcript_edit.blockSignals(True)
                self.transcript_edit.setText(str(largest))
                self.transcript_edit.blockSignals(False)
                self.logger.info("[_find_and_load_transcript] Using largest txt file: %s (%d bytes)", 
                               largest, largest.stat().st_size)
                return True, f"largest_file:{largest.name}"
        
        self.logger.warning("[_find_and_load_transcript] No transcript found after all searches")
        return False, "not_found"

    def _clear_chat_history(self) -> None:
        if hasattr(self, "chat_history"):
            self.chat_history.clear()
        if self.chat_session:
            try:
                self.chat_session.clear_chat()
            except AttributeError:
                self.chat_session.reset()
        if self.chat_delegate and self.chat_history:
            self.chat_history.viewport().update()

    def _generate_transcript_from_chat(self) -> None:
        """
        Generate a transcript from the current chat history and load it as project transcript.
        Extracts AI responses and formats them as a transcript file.
        """
        if not hasattr(self, "chat_history") or self.chat_history.count() == 0:
            QMessageBox.information(self, "אין שיחה", "אין שיחה לייצא. התחל שיחה עם ה-AI קודם.")
            return
        
        # Extract text from chat history
        transcript_lines = []
        transcript_lines.append("# תמלול מיוצר מתוך שיחת AI\n")
        transcript_lines.append(f"# תאריך: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        transcript_lines.append("# ---\n\n")
        
        for i in range(self.chat_history.count()):
            item = self.chat_history.item(i)
            if item:
                text = item.text().strip()
                if text:
                    transcript_lines.append(text)
                    transcript_lines.append("\n\n")
        
        if not transcript_lines or len(transcript_lines) <= 3:
            QMessageBox.information(self, "שיחה ריקה", "השיחה לא מכילה תוכן לייצוא.")
            return
        
        # Create transcript text
        transcript_text = "".join(transcript_lines)
        
        # Ask user where to save
        default_name = f"transcript_from_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "שמור תמלול",
            str(self.settings.output_base_dir / default_name),
            "קבצי טקסט (*.txt);;כל הקבצים (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            Path(file_path).write_text(transcript_text, encoding="utf-8")
            
            # Ask if user wants to load as project transcript
            reply = QMessageBox.question(
                self,
                "תמלול נוצר בהצלחה",
                f"התמלול נשמר ב:\n{file_path}\n\nהאם לטעון כתמלול לפרויקט?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if hasattr(self, "transcript_edit"):
                    self.transcript_edit.setText(file_path)
                self._append_log(f"תמלול נטען: {file_path}")
                
        except OSError as exc:
            QMessageBox.warning(self, "שגיאה", f"לא ניתן לשמור את התמלול:\n{exc}")

    def _clear_loaded_entry(self) -> None:
        """
        Clear the currently loaded history entry without deleting any data.
        Resets the workspace to a clean state while preserving all history records.
        """
        try:
            # Clear selection in projects list
            if hasattr(self, "projects_list"):
                self.projects_list.clearSelection()
                self.projects_list.setCurrentItem(None)
        
            # Clear selection in project cards (explorer)
            if hasattr(self, "project_cards"):
                self.project_cards.clearSelection()
                self.project_cards.setCurrentItem(None)
            
            # Clear active history entry reference
            self.active_history_entry = None
            self.pending_run_dir = None
            
            # Reset metadata to empty state
            self._reset_metadata_session()
            
            # Clear materials
            if hasattr(self, "materials_list"):
                self.materials_list.clear()
            if hasattr(self, "urls_edit"):
                self.urls_edit.clear()
            
            # Clear transcript field
            if hasattr(self, "transcript_edit"):
                self.transcript_edit.blockSignals(True)
                self.transcript_edit.clear()
                self.transcript_edit.setText("")
                self.transcript_edit.blockSignals(False)
            
            # Clear output gallery
            if hasattr(self, "output_gallery"):
                self.output_gallery.clear()
            
            # Clear chat history display
            if hasattr(self, "chat_history") and self.chat_history:
                self.chat_history.clear()
            
            # Clear story preview
            if hasattr(self, "story_preview"):
                self.story_preview.clear()
            
            # Reset chat session
            if hasattr(self, "chat_session") and self.chat_session:
                self.chat_session.clear_chat(preserve_metadata=False)
            
            # Clear metadata preview
            if hasattr(self, "metadata_preview"):
                self.metadata_preview.clear()
            
            # Update UI
            self._update_metadata_preview()
            self._update_output_gallery()
            self._update_card_buttons()
            
            # Update the "אחרון" (last topic) label to show cleared state
            if hasattr(self, "last_topic_value"):
                self.last_topic_value.setText("—")
            
            # Update status
            self._log("✅ Workspace נוקה בהצלחה")
            if hasattr(self, "statusBar") and self.statusBar():
                self.statusBar().showMessage("✅ Workspace נוקה בהצלחה", 3000)
            
            # Show message box to confirm
            QMessageBox.information(self, "נוקה", "✅ Workspace נוקה בהצלחה!\n\nהיסטוריית הריצות נשמרה וניתן לטעון ריצות קודמות מהרשימה.")
            
        except Exception as e:
            self._log(f"❌ שגיאה בניקוי Workspace: {e}")
            if hasattr(self, "statusBar") and self.statusBar():
                self.statusBar().showMessage(f"❌ שגיאה: {e}", 5000)
            QMessageBox.warning(self, "שגיאה", f"אירעה שגיאה בעת הניקוי:\n{e}")

    def _delete_all_projects(self) -> None:
        """
        Delete ALL projects physically and from history, but preserve cost stats.
        """
        reply = QMessageBox.question(
            self,
            "מחיקת כל הפרויקטים",
            "⚠️ פעולה זו תמחק את כל הפרויקטים והקבצים הפיזיים לצמיתות!\n\n"
            "היסטוריית העלויות תישמר בנתונים המצטברים.\n"
            "האם את/ה בטוח/ה?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Double confirmation
        confirm = QMessageBox.warning(
            self,
            "אישור סופי",
            "זוהי אזהרה אחרונה.\nכל הקבצים בתיקיית הפלט יימחקו ללא יכולת שחזור.\n\nלהמשיך?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self._log("🗑️ מתחיל מחיקת כל הפרויקטים...")
            
            # 1. Clear workspace first to release file locks
            self._clear_loaded_entry()
            
            # 2. Delete physical directories of all known runs
            all_runs = self.history.all()
            deleted_count = 0
            for entry in all_runs:
                run_dir = entry.get("run_dir")
                if run_dir:
                    path = Path(run_dir)
                    if path.exists():
                        try:
                            shutil.rmtree(path)
                            deleted_count += 1
                        except OSError as e:
                            self._log(f"⚠️ נכשל במחיקת {path.name}: {e}")

            # 3. Clear history but aggregate stats (handled by history manager)
            self.history.clear_all_runs()
            
            # 4. Refresh UI
            self._refresh_history()
            
            QMessageBox.information(self, "בוצע", f"נמחקו {deleted_count} פרויקטים.\nההיסטוריה נוקתה.")
            self._log(f"✅ כל הפרויקטים נמחקו ({deleted_count} תיקיות).")

        except Exception as e:
            QMessageBox.critical(self, "שגיאה", f"אירעה שגיאה בעת המחיקה:\n{e}")
            self._log(f"❌ שגיאה קריטית במחיקה: {e}")

    def _apply_chat_preferences(self) -> None:
        """Apply chat appearance preferences to all relevant widgets."""
        config = self._chat_theme_config()
        font = self._resolve_chat_font()
        font_family = font.family()
        font_size = font.pointSize()

        # Keep settings in sync with the effective font so they persist across restarts
        self.settings.chat_font_family = font_family
        self.settings.chat_font_size = font_size
        self._persist_chat_preferences()
        
        # Apply font to chat history and delegate
        if hasattr(self, "chat_history") and self.chat_history:
            self.chat_history.setFont(font)
            # Also set font on delegate for immediate effect
            if self.chat_delegate:
                self.chat_delegate.setFont(font)
            # Force complete re-layout and repaint of all items
            for i in range(self.chat_history.count()):
                item = self.chat_history.item(i)
                if item:
                    # Reset size hint to force recalculation
                    item.setSizeHint(QSize(-1, -1))
            # Trigger full layout recalculation
            model = self.chat_history.model()
            if model:
                model.layoutChanged.emit()
            self.chat_history.reset()
            self.chat_history.update()
        
        # Apply font to chat input
        if getattr(self, "chat_input", None):
            self.chat_input.setFont(QFont(font_family, font_size))
        
        # Apply font to buttons
        btn_font = QFont(font_family, max(10, font_size - 1))
        if getattr(self, "chat_clear_btn", None):
            self.chat_clear_btn.setFont(btn_font)
        
        # Build chat card stylesheet with gradient background
        if hasattr(self, "chat_card") and self.chat_card:
            bg_gradient = config.get("background_gradient", "")
            panel_bg = config.get("panel_bg", "#0f172a")
            
            if bg_gradient:
                bg_style = f"background: {bg_gradient};"
            else:
                bg_style = f"background-color: {panel_bg};"
            
            # Apply comprehensive stylesheet
            stylesheet = f"""
                QFrame#ChatCard {{
                    {bg_style}
                    border: 1px solid #1e293b;
                    border-radius: 16px;
                }}
                QFrame#ChatCard QListWidget {{
                    background: transparent;
                    border: none;
                }}
                QFrame#ChatCard QLabel {{
                    background: transparent;
                }}
                QFrame#ChatCard QPushButton {{
                    background: rgba(30, 58, 138, 0.8);
                }}
            """
            self.chat_card.setStyleSheet(stylesheet)
            self.chat_card.update()

    def _chat_delegate_config(self) -> Dict[str, object]:
        config = self._chat_theme_config()
        return {
            "theme": config["theme"],
            "assistant_bubble": config["assistant_bubble"],
            "assistant_text": config["assistant_text"],
            "user_bubble": config["user_bubble"],
            "user_text": config["user_text"],
        }

    def _chat_theme_config(self) -> Dict[str, object]:
        theme = (self.settings.chat_theme or "dark").lower()
        brightness = self._normalized_chat_brightness()
        base_dark = QColor("#0b1122")
        base_light = QColor("#f8fafc")
        if theme == "light":
            panel_color = self._tint_color(base_light, brightness, lighten=False)
            # AI messages: soft gray-blue background
            assistant_bubble_color = self._tint_color(QColor("#e2e8f0"), brightness * 0.4, lighten=False)
            # User messages: distinct teal/cyan color
            user_bubble_color = self._tint_color(QColor("#0d9488"), brightness * 0.2, lighten=True)
            assistant_text = "#0f172a"
        else:
            panel_color = self._tint_color(base_dark, brightness, lighten=True)
            # AI messages: purple/violet color for clear distinction
            assistant_bubble_color = self._tint_color(QColor("#4c1d95"), brightness * 0.6, lighten=True)
            # User messages: teal/cyan color - clearly different from AI
            user_bubble_color = self._tint_color(QColor("#0f766e"), brightness * 0.3, lighten=True)
            assistant_text = "#f8fafc"
        
        def _apply_override(raw: str, fallback: QColor) -> QColor:
            """Validate and apply a hex override if provided."""
            if not raw:
                return fallback
            color = QColor(str(raw))
            return color if color.isValid() else fallback
        
        user_bubble_color = _apply_override(
            getattr(self.settings, "chat_user_bubble", "") or "", user_bubble_color
        )
        assistant_bubble_color = _apply_override(
            getattr(self.settings, "chat_assistant_bubble", "") or "", assistant_bubble_color
        )
        
        # Get background gradient from selected theme
        bg_theme_key = getattr(self.settings, "chat_bg_theme", "midnight") or "midnight"
        bg_theme = CHAT_THEMES.get(bg_theme_key, CHAT_THEMES.get("midnight", {}))
        background_gradient = bg_theme.get("gradient", "")
        
        return {
            "theme": theme,
            "font_family": self.settings.chat_font_family or "Assistant",
            "panel_bg": panel_color.name(),
            "assistant_bubble": assistant_bubble_color.name(),
            "user_bubble": user_bubble_color.name(),
            "assistant_text": assistant_text,
            "user_text": "#f8fafc",
            "brightness": brightness,
            "background_gradient": background_gradient,
        }

    def _normalized_chat_brightness(self) -> float:
        try:
            value = float(getattr(self.settings, "chat_banner_brightness", 0.85) or 0.85)
        except (TypeError, ValueError):
            value = 0.85
        return max(0.2, min(1.0, value))

    def _tint_color(self, color: QColor, factor: float, lighten: bool = True) -> QColor:
        factor = max(0.0, min(1.0, factor))
        if lighten:
            r = color.red() + (255 - color.red()) * factor
            g = color.green() + (255 - color.green()) * factor
            b = color.blue() + (255 - color.blue()) * factor
        else:
            r = color.red() * (1 - factor * 0.7)
            g = color.green() * (1 - factor * 0.7)
            b = color.blue() * (1 - factor * 0.7)
        return QColor(int(r), int(g), int(b))

    def _refresh_timeline(self) -> None:
        if not hasattr(self, "timeline_list"):
            return
        self.timeline_list.clear()
        entries = self.history.all()[:8]
        if not entries:
            self.timeline_list.addItem("אין ריצות מתועדות עדיין – הרץ Pipeline כדי לראות נתונים.")
            return
        for entry in entries:
            label = f"{entry.get('date', '???')} · {entry.get('topic', '')}"
            costs = entry.get("costs") or {}
            total_cost = float(costs.get("total_cost_usd", 0.0))
            if total_cost:
                label += f" · ${total_cost:.2f}"
            badges = []
            if entry.get("final_video"):
                badges.append("וידאו")
            if entry.get("slide_deck"):
                badges.append("PPTX")
            if entry.get("story"):
                badges.append("Story")
            if badges:
                label += " · " + "/".join(badges)
            item = QListWidgetItem(label)
            tooltip_parts = [
                f"נושא: {entry.get('topic', 'לא צוין')}",
                f"עלות משוערת: ${total_cost:.2f}",
                f"תווים לדיבור: {int(costs.get('tts_characters', 0)):,}",
            ]
            labs = entry.get("labs") or []
            if labs:
                # Handle list of dicts (new format) or list of strings (old format)
                lab_titles = []
                for lab in labs[:3]:
                    if isinstance(lab, dict):
                        lab_titles.append(lab.get("title", "Untitled Lab"))
                    else:
                        lab_titles.append(str(lab))
                tooltip_parts.append(f"Labs: {', '.join(lab_titles)}")
            item.setToolTip("\n".join(tooltip_parts))
            limit = max(self.settings.monthly_openai_cost_limit, 0.01)
            if total_cost >= 0.8 * limit:
                item.setForeground(QColor("#f87171"))
            elif total_cost:
                item.setForeground(QColor("#38bdf8"))
            self.timeline_list.addItem(item)

    def _update_project_stats(self) -> None:
        if not hasattr(self, "run_count_value"):
            return
        runs = self.history.all()
        if not runs:
            self.run_count_value.setText("0")
            self.total_cost_value.setText("$0.00")
            self.last_topic_value.setText("אין ריצות עדיין")
        else:
            self.run_count_value.setText(str(len(runs)))
            total_cost = sum(float((entry.get("costs") or {}).get("total_cost_usd", 0.0)) for entry in runs)
            self.total_cost_value.setText(f"${total_cost:.2f}")
            last_topic = runs[0].get("topic") or "—"
            self.last_topic_value.setText(last_topic)

    def _compute_cost_totals(self) -> Dict[str, float]:
        # Start with aggregated stats from deleted runs
        aggregated = self.history.get_aggregated_costs()
        totals = {
            "openai_cost_usd": aggregated.get("openai_cost_usd", 0.0),
            "tts_characters": aggregated.get("tts_characters", 0)
        }
        
        # Add current runs
        for entry in self.history.all():
            costs = entry.get("costs") or {}
            totals["openai_cost_usd"] += float(costs.get("total_cost_usd", 0.0))
            totals["tts_characters"] += int(costs.get("tts_characters", 0))
        return totals

    def _build_cost_series(self, metric: str) -> Tuple[List[int], List[float], List[str]]:
        entries = self.history.all()[:30]
        if not entries:
            return [], [], []
        x_vals: List[int] = []
        y_vals: List[float] = []
        labels: List[str] = []
        for idx, entry in enumerate(reversed(entries)):
            date_str = entry.get("date") or ""
            try:
                date_obj = datetime.fromisoformat(date_str)
            except ValueError:
                date_obj = datetime.utcnow()
            costs = entry.get("costs") or {}
            if metric == "tts":
                value = int(costs.get("tts_characters", 0)) / 1000
            else:
                value = float(costs.get("total_cost_usd", 0.0))
            x_vals.append(idx)
            y_vals.append(value)
            labels.append(date_obj.strftime("%m-%d"))
        return x_vals, y_vals, labels

    def _summarize_costs(self, entries: List[Dict]) -> Dict[str, float]:
        if not entries:
            return {"avg": 0.0, "max": 0.0, "tts_total": 0}
        costs = [float((entry.get("costs") or {}).get("total_cost_usd", 0.0)) for entry in entries]
        tts_total = sum(int((entry.get("costs") or {}).get("tts_characters", 0)) for entry in entries)
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        return {"avg": avg_cost, "max": max(costs) if costs else 0.0, "tts_total": tts_total}

    def _save_budget_limits(self, openai_limit: float, tts_limit: float) -> None:
        self.settings.monthly_openai_cost_limit = float(openai_limit)
        self.settings.monthly_tts_character_limit = int(tts_limit)
        self.cost_totals = self._compute_cost_totals()
        self._refresh_timeline()

    def _open_log_center(self) -> None:
        """Open the Log Center dialog for viewing and exporting logs."""
        dialog = LogCenterDialog(
            log_buffer=self.log_buffer,
            section_label_factory=self._section_label,
            parent=self,
        )
        dialog.exec()

    def _open_about_dialog(self) -> None:
        """Open the About dialog."""
        dialog = AboutDialog(parent=self)
        dialog.exec()

    def _reload_application(self) -> None:
        """Reload application components and check for updates."""
        import importlib
        from . import constants
        
        # Get old version
        old_version = constants.APP_VERSION
        
        # Reload constants module to get new values
        importlib.reload(constants)
        
        # Update version display
        new_version = constants.APP_VERSION
        
        # Update version label in header
        if hasattr(self, 'version_label'):
            self.version_label.setText(f"v{new_version}")
        
        # Refresh all data
        self._refresh_history()
        self._apply_chat_preferences()
        
        # Update window title with new version
        self.setWindowTitle(f"{constants.APP_DISPLAY_NAME} - יצירת פודקאסטים v{new_version}")
        
        # Notify user
        if old_version != new_version:
            QMessageBox.information(
                self, 
                "עדכון גרסה", 
                f"גרסה עודכנה!\n\nמ-{old_version} ל-{new_version}\n\nכל הרכיבים רועננו."
            )
        else:
            QMessageBox.information(
                self, 
                "רענון הושלם", 
                f"גרסה נוכחית: {new_version}\n\nכל הנתונים רועננו בהצלחה."
            )

    def _open_backup_dialog(self) -> None:
        """Open the Backup/Restore dialog."""
        dialog = BackupRestoreDialog(
            settings=self.settings,
            parent=self,
        )
        dialog.exec()
        # Refresh after restore
        self._refresh_history()

    def _export_log_to_file(self, text: str) -> None:
        if not text.strip():
            QMessageBox.information(self, "לוג ריק", "אין תוכן לשמור.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "שמור לוג", "run_log.txt", "Text Files (*.txt)")
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        QMessageBox.information(self, "נשמר", f"לוג נשמר אל {path}")

    def _save_failure_log(self) -> None:
        if not self.log_buffer:
            return
        target_dir = self.pending_run_dir or (self.settings.output_base_dir / "_failed_runs")
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = target_dir / f"failure_{timestamp}.log"
        try:
            log_path.write_text("\n".join(self.log_buffer), encoding="utf-8")
            QMessageBox.information(self, "לוג נשמר", f"הלוג נשמר אל {log_path}")
        except OSError as exc:
            QMessageBox.warning(self, "שגיאה", f"לא ניתן לשמור לוג:\n{exc}")

    # --- History actions --------------------------------------------
    def _selected_entry(self) -> Optional[Dict]:
        items = self.projects_list.selectedItems()
        if not items:
            QMessageBox.information(self, "בחירה", "בחר פרויקט מהרשימה")
            return None
        return items[0].data(Qt.ItemDataRole.UserRole) or {}

    def _open_selected_run_dir(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        path = entry.get("run_dir")
        if path:
            self._open_path(Path(path))

    def _open_selected_media(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        target = entry.get("final_video") or entry.get("final_audio")
        if target:
            self._open_path(Path(target))
        else:
            QMessageBox.information(self, "מידע", "לא נמצאו קבצי מדיה לריצה זו")

    def _open_selected_ppt(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        target = entry.get("slide_deck")
        if target:
            self._open_path(Path(target))
        else:
            QMessageBox.information(self, "מידע", "לא נוצרה מצגת לריצה זו")

    def _open_selected_story(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        path = entry.get("story")
        if path:
            self._open_path(Path(path))
        else:
            QMessageBox.information(self, "מידע", "לא נוצר קובץ Story לריצה זו.")

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "שגיאה", f"{path} לא קיים")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "שגיאה", f"לא ניתן לפתוח נתיב:\n{exc}")

    def _confirm_budget_allowance(self) -> bool:
        openai_limit = max(self.settings.monthly_openai_cost_limit, 0.01)
        tts_limit = max(float(self.settings.monthly_tts_character_limit), 1.0)
        over_openai = self.cost_totals["openai_cost_usd"] >= openai_limit
        over_tts = self.cost_totals["tts_characters"] >= tts_limit
        if not over_openai and not over_tts:
            return True
        message_parts = []
        if over_openai:
            message_parts.append("עלות OpenAI חרגה מהתקציב החודשי.")
        if over_tts:
            message_parts.append("סך התווים לדיבור חרג מהמגבלה.")
        message = "\n".join(message_parts) + "\n\nלהמשיך בכל זאת?"
        result = QMessageBox.question(self, "חריגה בתקציב", message)
        return result == QMessageBox.StandardButton.Yes

    def _calculate_cost_estimate(
        self,
        words: int,
        minutes: float,
        provider: str,
        include_audio: bool,
        include_video: bool,
        include_ppt: bool,
    ) -> Tuple[str, float]:
        if words <= 0 and minutes > 0:
            words = int(minutes * WORDS_PER_MINUTE)
        if words <= 0:
            raise ValueError("הזינו מספר מילים או דקות.")
        tokens = words * TOKENS_PER_WORD
        output_tokens = tokens * OUTPUT_TOKEN_RATIO
        if provider == "gemini":
            gpt_cost = (tokens / 1000) * GEMINI_INPUT_COST + (output_tokens / 1000) * GEMINI_OUTPUT_COST
            model_name = "Gemini Flash"
        else:
            gpt_cost = (tokens / 1000) * AZURE_GPT_INPUT_COST + (output_tokens / 1000) * AZURE_GPT_OUTPUT_COST
            model_name = "Azure GPT-4o"
        total = gpt_cost
        breakdown = [f"מודל {model_name}: ${gpt_cost:.2f}"]
        if include_audio:
            tts_chars = words * CHARS_PER_WORD
            tts_cost = (tts_chars / 1_000_000) * TTS_COST_PER_MILLION
            total += tts_cost
            breakdown.append(f"TTS (Neural): ${tts_cost:.2f}")
        if include_video:
            total += VIDEO_OVERHEAD_COST
            breakdown.append(f"וידאו / רינדור: ${VIDEO_OVERHEAD_COST:.2f}")
        if include_ppt:
            total += PPT_EXTRA_COST
            breakdown.append(f"PPTX/Story: ${PPT_EXTRA_COST:.2f}")
        breakdown.append(f"סה\"כ משוער: ${total:.2f}")
        return "\n".join(breakdown), total

    # --- Settings ----------------------------------------------------
    def _load_settings(self) -> Settings:
        try:
            return Settings.load()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "שגיאה", f"לא ניתן לקרוא .env:\n{exc}")
            raise


def main() -> None:  # pragma: no cover - manual run
    app = QApplication(sys.argv)
    window = PodcastGeneratorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
