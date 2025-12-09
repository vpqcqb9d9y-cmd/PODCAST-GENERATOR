"""
M.B.S Studio - Cost Center Dialog
===================================

Centralized cost management dialog with budget tracking,
clear tables, analytics charts, and cost calculator.

Author: M.B.S Studio
Version: 2.0.0 - Redesigned with tabbed interface
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph import PlotWidget

from src.utils import HistoryManager, Settings
from ..constants import (
    AZURE_GPT_INPUT_COST,
    AZURE_GPT_OUTPUT_COST,
    AZURE_TTS_COST_PER_THOUSAND,
    CHARS_PER_WORD,
    ELEVENLABS_COST_PER_THOUSAND,
    GEMINI_INPUT_COST,
    GEMINI_OUTPUT_COST,
    IMAGEN_COST_PER_IMAGE,
    OUTPUT_TOKEN_RATIO,
    PPT_EXTRA_COST,
    TOKENS_PER_WORD,
    TTS_COST_PER_MILLION,
    VEO_COST_PER_SECOND,
    VIDEO_OVERHEAD_COST,
    WORDS_PER_MINUTE,
)


# Table styling constants
TABLE_STYLE = """
QTableWidget {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    gridline-color: #1e293b;
    color: #e2e8f0;
    font-size: 13px;
}
QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #1e293b;
}
QTableWidget::item:selected {
    background-color: #1e3a8a;
}
QTableWidget::item:alternate {
    background-color: #0b1220;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #334155;
    font-weight: 600;
    font-size: 12px;
}
QHeaderView::section:first {
    border-top-left-radius: 8px;
}
QHeaderView::section:last {
    border-top-right-radius: 8px;
}
"""


class CostCenterDialog(QDialog):
    """
    Cost management and analytics dialog with tabbed interface.
    
    Provides:
        - Tab 1: Clear tables for budget and history
        - Tab 2: Charts and analytics
        - Cost calculator with Azure + ElevenLabs support
    """

    def __init__(
        self,
        settings: Settings,
        history: HistoryManager,
        cost_totals: Dict[str, float],
        section_label_factory: Callable[[str], QLabel],
        card_widget_factory: Callable[[], QWidget],
        helper_label_factory: Callable[[str], QLabel],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.history = history
        self.cost_totals = cost_totals
        self._section_label = section_label_factory
        self._card_widget = card_widget_factory
        self._helper_label = helper_label_factory
        
        self._setup_window()
        self._setup_ui()
        self._refresh_all()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("מרכז עלויות וניתוח")
        self.resize(900, 700)
        self.setMinimumHeight(500)
        self.setMinimumWidth(700)

    def _setup_ui(self) -> None:
        """Build the tabbed dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Title
        title = QLabel("מרכז עלויות וניתוח")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #22c55e;")
        main_layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                border-radius: 8px;
                background: #0f172a;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #0f172a;
                color: #22c55e;
                border-bottom: 2px solid #22c55e;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
            }
        """)
        
        # Tab 1: Tables
        self.tabs.addTab(self._build_tables_tab(), "טבלאות עלויות")
        
        # Tab 2: Charts
        self.tabs.addTab(self._build_charts_tab(), "גרפים וניתוח")
        
        main_layout.addWidget(self.tabs, 1)
        
        # Calculator section (always visible)
        main_layout.addWidget(self._build_calculator())

    def _build_tables_tab(self) -> QWidget:
        """Build the tables tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Budget Summary Table
        layout.addWidget(self._section_label("סיכום תקציב חודשי"))
        self.budget_table = self._create_budget_table()
        layout.addWidget(self.budget_table)
        
        # Budget limits controls
        limits_row = QHBoxLayout()
        limits_row.addWidget(QLabel("מגבלת AI:"))
        self.openai_spin = QDoubleSpinBox()
        self.openai_spin.setPrefix("$ ")
        self.openai_spin.setRange(10.0, 5000.0)
        self.openai_spin.setValue(self.settings.monthly_openai_cost_limit)
        limits_row.addWidget(self.openai_spin)
        
        limits_row.addWidget(QLabel("מגבלת TTS:"))
        self.tts_spin = QDoubleSpinBox()
        self.tts_spin.setRange(50000, 5000000)
        self.tts_spin.setDecimals(0)
        self.tts_spin.setSuffix(" תווים")
        self.tts_spin.setValue(float(self.settings.monthly_tts_character_limit))
        limits_row.addWidget(self.tts_spin)
        
        save_btn = QPushButton("שמור מגבלות")
        save_btn.clicked.connect(self._save_limits)
        limits_row.addWidget(save_btn)
        limits_row.addStretch(1)
        layout.addLayout(limits_row)
        
        # Recent Runs Table
        layout.addWidget(self._section_label("היסטוריית הרצות (30 אחרונות)"))
        self.history_table = self._create_history_table()
        layout.addWidget(self.history_table, 1)
        
        return tab

    def _create_budget_table(self) -> QTableWidget:
        """Create the budget summary table."""
        table = QTableWidget()
        table.setStyleSheet(TABLE_STYLE)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["שירות", "שימוש", "עלות", "תקציב", "סטטוס"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setMaximumHeight(180)
        return table

    def _create_history_table(self) -> QTableWidget:
        """Create the history table."""
        table = QTableWidget()
        table.setStyleSheet(TABLE_STYLE)
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "תאריך", "נושא", "עלות AI", "עלות TTS", "ספק TTS", "סה״כ"
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSortingEnabled(True)
        return table

    def _build_charts_tab(self) -> QWidget:
        """Build the charts tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Chart controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("מדד להצגה:"))
        
        self.metric_combo = QComboBox()
        self.metric_combo.addItem("עלות יומית ($)", "cost")
        self.metric_combo.addItem("תווים לדיבור (באלפים)", "tts")
        self.metric_combo.addItem("עלות TTS בלבד", "tts_cost")
        self.metric_combo.currentIndexChanged.connect(lambda _: self._refresh_chart())
        controls.addWidget(self.metric_combo)
        controls.addStretch(1)
        layout.addLayout(controls)
        
        # Chart
        self.chart = PlotWidget(background="#0f172a")
        self.chart.setMinimumHeight(250)
        self.chart.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.chart, 1)
        
        # Placeholder
        self.chart_placeholder = QLabel("אין עדיין נתוני Pipeline להצגה.")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_placeholder.setProperty("class", "helper")
        self.chart_placeholder.setStyleSheet("color: #64748b; font-size: 14px;")
        layout.addWidget(self.chart_placeholder)
        
        # Summary stats
        stats_row = QHBoxLayout()
        self.avg_label = QLabel("$0.00 ממוצע")
        self.max_label = QLabel("$0.00 שיא")
        self.tts_label = QLabel("0 תווי TTS")
        
        for lbl in (self.avg_label, self.max_label, self.tts_label):
            lbl.setStyleSheet(
                "font-size: 16px; font-weight: 600; color: #38bdf8; "
                "background: #1e293b; padding: 8px 16px; border-radius: 8px;"
            )
            stats_row.addWidget(lbl)
        stats_row.addStretch(1)
        layout.addLayout(stats_row)
        
        return tab

    def _build_calculator(self) -> QGroupBox:
        """Build the cost calculator widget with TTS provider selection."""
        calc_group = QGroupBox("מחשבון עלויות מהיר")
        calc_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #22c55e;
                border: 1px solid #1e293b;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        calc_layout = QGridLayout(calc_group)
        calc_layout.setSpacing(12)

        # Row 0: Words and Minutes
        calc_layout.addWidget(QLabel("מספר מילים:"), 0, 0)
        self.words_input = QSpinBox()
        self.words_input.setRange(0, 100000)
        self.words_input.setValue(8000)
        calc_layout.addWidget(self.words_input, 0, 1)

        calc_layout.addWidget(QLabel("משך בדקות:"), 0, 2)
        self.minutes_input = QDoubleSpinBox()
        self.minutes_input.setRange(0.0, 240.0)
        self.minutes_input.setDecimals(1)
        self.minutes_input.setValue(30.0)
        calc_layout.addWidget(self.minutes_input, 0, 3)

        # Row 1: AI Model and TTS Provider
        calc_layout.addWidget(QLabel("מודל AI:"), 1, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Azure GPT-4o", "azure")
        self.provider_combo.addItem("Gemini 2.5 Flash", "gemini")
        calc_layout.addWidget(self.provider_combo, 1, 1)

        calc_layout.addWidget(QLabel("ספק TTS:"), 1, 2)
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItem("Azure Neural ($0.016/1K)", "azure")
        self.tts_provider_combo.addItem("ElevenLabs ($0.30/1K)", "elevenlabs")
        calc_layout.addWidget(self.tts_provider_combo, 1, 3)

        # Row 2: Visual Generator
        calc_layout.addWidget(QLabel("ויזואליזציה:"), 2, 0)
        self.visual_gen_combo = QComboBox()
        self.visual_gen_combo.addItem("Manim (חינם)", "manim")
        self.visual_gen_combo.addItem("Imagen 4 ($0.04/תמונה)", "imagen")
        self.visual_gen_combo.addItem("VEO ($0.75/שנייה)", "veo")
        self.visual_gen_combo.addItem("היברידי (Manim + Google AI)", "hybrid")
        calc_layout.addWidget(self.visual_gen_combo, 2, 1)
        
        calc_layout.addWidget(QLabel("תמונות/שניות:"), 2, 2)
        self.visual_count_input = QSpinBox()
        self.visual_count_input.setRange(0, 100)
        self.visual_count_input.setValue(5)
        self.visual_count_input.setToolTip("מספר תמונות (Imagen) או שניות (VEO)")
        calc_layout.addWidget(self.visual_count_input, 2, 3)

        # Row 3: Output toggles
        toggle_row = QHBoxLayout()
        self.audio_cb = QCheckBox("כולל אודיו")
        self.audio_cb.setChecked(True)
        self.video_cb = QCheckBox("כולל וידאו")
        self.video_cb.setChecked(True)
        self.ppt_cb = QCheckBox("כולל PPTX")
        self.ppt_cb.setChecked(False)
        toggle_row.addWidget(self.audio_cb)
        toggle_row.addWidget(self.video_cb)
        toggle_row.addWidget(self.ppt_cb)
        toggle_row.addStretch(1)
        
        calc_button = QPushButton("חשב עלות משוערת")
        calc_button.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                font-weight: 600;
                padding: 10px 24px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
        """)
        calc_button.clicked.connect(self._run_calculator)
        toggle_row.addWidget(calc_button)
        calc_layout.addLayout(toggle_row, 3, 0, 1, 4)

        # Row 4: Result
        self.calc_result = QLabel("הזינו נתונים ולחצו על \"חשב עלות משוערת\".")
        self.calc_result.setWordWrap(True)
        self.calc_result.setStyleSheet(
            "color: #94a3b8; background: #1e293b; padding: 12px; "
            "border-radius: 8px; font-size: 13px;"
        )
        calc_layout.addWidget(self.calc_result, 4, 0, 1, 4)

        return calc_group

    def _refresh_all(self) -> None:
        """Refresh all components."""
        self._fill_budget_table()
        self._fill_history_table()
        self._refresh_chart()

    def _fill_budget_table(self) -> None:
        """Fill the budget summary table."""
        totals = self.cost_totals
        openai_limit = max(self.settings.monthly_openai_cost_limit, 0.01)
        tts_limit = max(float(self.settings.monthly_tts_character_limit), 1.0)
        elevenlabs_limit = max(
            float(getattr(self.settings, 'monthly_elevenlabs_character_limit', 100000)), 1.0
        )
        
        # Calculate percentages
        ai_pct = min(100, (totals.get("openai_cost_usd", 0) / openai_limit) * 100)
        azure_tts_chars = totals.get("tts_characters", 0)
        azure_tts_pct = min(100, (azure_tts_chars / tts_limit) * 100)
        elevenlabs_chars = totals.get("elevenlabs_characters", 0)
        elevenlabs_pct = min(100, (elevenlabs_chars / elevenlabs_limit) * 100)
        
        # Google AI visuals usage
        imagen_images = totals.get("imagen_images", 0)
        imagen_cost = totals.get("imagen_cost_usd", imagen_images * IMAGEN_COST_PER_IMAGE)
        veo_seconds = totals.get("veo_seconds", 0)
        veo_cost = totals.get("veo_cost_usd", veo_seconds * VEO_COST_PER_SECOND)
        google_ai_cost = imagen_cost + veo_cost
        google_ai_limit = max(float(getattr(self.settings, 'monthly_google_ai_limit', 50.0)), 0.01)
        google_ai_pct = min(100, (google_ai_cost / google_ai_limit) * 100)
        
        rows = [
            (
                "Azure OpenAI / Gemini",
                f'{totals.get("prompt_tokens", 0) + totals.get("completion_tokens", 0):,} tokens',
                f'${totals.get("openai_cost_usd", 0):.2f}',
                f'${openai_limit:.0f}',
                ai_pct,
            ),
            (
                "Azure Neural TTS",
                f'{azure_tts_chars:,} תווים',
                f'${totals.get("azure_tts_cost_usd", azure_tts_chars * 0.000016):.2f}',
                f'{int(tts_limit):,} תווים',
                azure_tts_pct,
            ),
            (
                "ElevenLabs TTS",
                f'{elevenlabs_chars:,} תווים',
                f'${totals.get("elevenlabs_tts_cost_usd", elevenlabs_chars * 0.0003):.2f}',
                f'{int(elevenlabs_limit):,} תווים',
                elevenlabs_pct,
            ),
            (
                "Google AI (Imagen + VEO)",
                f'{imagen_images} תמונות | {veo_seconds:.1f} שניות וידאו',
                f'${google_ai_cost:.2f}',
                f'${google_ai_limit:.0f}',
                google_ai_pct,
            ),
        ]
        
        self.budget_table.setRowCount(len(rows))
        for row_idx, (service, usage, cost, budget, pct) in enumerate(rows):
            self.budget_table.setItem(row_idx, 0, QTableWidgetItem(service))
            self.budget_table.setItem(row_idx, 1, QTableWidgetItem(usage))
            self.budget_table.setItem(row_idx, 2, QTableWidgetItem(cost))
            self.budget_table.setItem(row_idx, 3, QTableWidgetItem(budget))
            
            # Status with color coding
            status_item = QTableWidgetItem(f'{pct:.0f}%')
            if pct >= 90:
                status_item.setForeground(QColor("#ef4444"))  # Red
            elif pct >= 70:
                status_item.setForeground(QColor("#f97316"))  # Orange
            else:
                status_item.setForeground(QColor("#22c55e"))  # Green
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.budget_table.setItem(row_idx, 4, status_item)

    def _fill_history_table(self) -> None:
        """Fill the history table with recent runs."""
        entries = self.history.all()[:30]
        self.history_table.setRowCount(len(entries))
        
        for row_idx, entry in enumerate(entries):
            date_str = entry.get("date", "")
            topic = entry.get("topic", "לא ידוע")[:30]
            costs = entry.get("costs") or {}
            
            ai_cost = costs.get("openai_cost_usd", 0)
            azure_tts = costs.get("azure_tts_cost_usd", costs.get("tts_cost_usd", 0))
            elevenlabs_tts = costs.get("elevenlabs_tts_cost_usd", 0)
            tts_cost = azure_tts + elevenlabs_tts
            total = costs.get("total_cost_usd", ai_cost + tts_cost)
            
            # Determine TTS provider used
            tts_provider = "Azure"
            if elevenlabs_tts > 0:
                tts_provider = "ElevenLabs" if azure_tts == 0 else "Mixed"
            
            self.history_table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            self.history_table.setItem(row_idx, 1, QTableWidgetItem(topic))
            self.history_table.setItem(row_idx, 2, QTableWidgetItem(f'${ai_cost:.3f}'))
            self.history_table.setItem(row_idx, 3, QTableWidgetItem(f'${tts_cost:.3f}'))
            self.history_table.setItem(row_idx, 4, QTableWidgetItem(tts_provider))
            
            total_item = QTableWidgetItem(f'${total:.3f}')
            total_item.setForeground(QColor("#22c55e"))
            self.history_table.setItem(row_idx, 5, total_item)

    def _refresh_chart(self) -> None:
        """Refresh the analytics chart."""
        self.chart.clear()
        metric = self.metric_combo.currentData()
        x_vals, y_vals, labels = self._build_cost_series(metric)
        
        if not x_vals:
            self.chart_placeholder.setVisible(True)
            self.chart.setVisible(False)
            return
        
        self.chart_placeholder.setVisible(False)
        self.chart.setVisible(True)
        
        # Choose color based on metric
        colors = {
            "cost": ("#60a5fa", "#1d4ed855"),
            "tts": ("#a78bfa", "#7c3aed55"),
            "tts_cost": ("#f472b6", "#db277755"),
        }
        pen_color, fill_color = colors.get(metric, colors["cost"])
        
        pen = {"color": pen_color, "width": 2}
        curve = self.chart.plot(
            x_vals, y_vals,
            pen=pen,
            symbol="o",
            symbolBrush=pen_color,
            symbolPen=pen_color,
        )
        curve.setFillLevel(0)
        curve.setBrush(fill_color)
        
        axis = self.chart.getAxis("bottom")
        axis.setTicks([[(i, labels[i]) for i in range(len(labels))]])
        
        # Update summary
        entries = self.history.all()[:30]
        summary = self._summarize_costs(entries)
        self.avg_label.setText(f"${summary['avg']:.2f} ממוצע")
        self.max_label.setText(f"${summary['max']:.2f} שיא")
        self.tts_label.setText(f"{summary['tts_total']:,} תווי TTS")

    def _build_cost_series(
        self,
        metric: str,
    ) -> Tuple[List[int], List[float], List[str]]:
        """Build time series data for the chart."""
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
                # Total TTS characters in thousands
                azure = int(costs.get("tts_characters", 0))
                elevenlabs = int(costs.get("elevenlabs_characters", 0))
                value = (azure + elevenlabs) / 1000
            elif metric == "tts_cost":
                # TTS cost only
                azure_cost = float(costs.get("azure_tts_cost_usd", costs.get("tts_cost_usd", 0)))
                elevenlabs_cost = float(costs.get("elevenlabs_tts_cost_usd", 0))
                value = azure_cost + elevenlabs_cost
            else:
                value = float(costs.get("total_cost_usd", 0.0))
            
            x_vals.append(idx)
            y_vals.append(value)
            labels.append(date_obj.strftime("%m-%d"))
        
        return x_vals, y_vals, labels

    def _summarize_costs(self, entries: List[Dict]) -> Dict[str, float]:
        """Summarize cost statistics from entries."""
        if not entries:
            return {"avg": 0.0, "max": 0.0, "tts_total": 0}
        
        costs = [
            float((entry.get("costs") or {}).get("total_cost_usd", 0.0))
            for entry in entries
        ]
        tts_total = sum(
            int((entry.get("costs") or {}).get("tts_characters", 0)) +
            int((entry.get("costs") or {}).get("elevenlabs_characters", 0))
            for entry in entries
        )
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        
        return {
            "avg": avg_cost,
            "max": max(costs) if costs else 0.0,
            "tts_total": tts_total,
        }

    def _save_limits(self) -> None:
        """Save the updated budget limits."""
        self.settings.monthly_openai_cost_limit = float(self.openai_spin.value())
        self.settings.monthly_tts_character_limit = int(self.tts_spin.value())
        self._refresh_all()
        QMessageBox.information(self, "נשמר", "מגבלות התקציב עודכנו בהצלחה.")

    def _run_calculator(self) -> None:
        """Run the cost calculator and display results."""
        try:
            text, _ = self._calculate_cost_estimate(
                self.words_input.value(),
                self.minutes_input.value(),
                self.provider_combo.currentData(),
                self.tts_provider_combo.currentData(),
                self.visual_gen_combo.currentData(),
                self.visual_count_input.value(),
                self.audio_cb.isChecked(),
                self.video_cb.isChecked(),
                self.ppt_cb.isChecked(),
            )
        except ValueError as exc:
            QMessageBox.information(self, "נתונים חסרים", str(exc))
            return
        self.calc_result.setText(text)

    def _calculate_cost_estimate(
        self,
        words: int,
        minutes: float,
        ai_provider: str,
        tts_provider: str,
        visual_gen: str,
        visual_count: int,
        include_audio: bool,
        include_video: bool,
        include_ppt: bool,
    ) -> Tuple[str, float]:
        """
        Calculate estimated costs for a pipeline run.
        
        Args:
            words: Number of words in transcript
            minutes: Duration in minutes
            ai_provider: AI provider ('azure' or 'gemini')
            tts_provider: TTS provider ('azure' or 'elevenlabs')
            visual_gen: Visual generator ('manim', 'imagen', 'veo', 'hybrid')
            visual_count: Number of images or seconds of video
            include_audio: Include TTS cost
            include_video: Include video rendering cost
            include_ppt: Include PPTX generation cost
            
        Returns:
            Tuple of (breakdown_text, total_cost)
        """
        if words <= 0 and minutes > 0:
            words = int(minutes * WORDS_PER_MINUTE)
        if words <= 0:
            raise ValueError("הזינו מספר מילים או דקות.")
        
        tokens = words * TOKENS_PER_WORD
        output_tokens = tokens * OUTPUT_TOKEN_RATIO
        
        if ai_provider == "gemini":
            gpt_cost = (
                (tokens / 1000) * GEMINI_INPUT_COST +
                (output_tokens / 1000) * GEMINI_OUTPUT_COST
            )
            model_name = "Gemini Flash"
        else:
            gpt_cost = (
                (tokens / 1000) * AZURE_GPT_INPUT_COST +
                (output_tokens / 1000) * AZURE_GPT_OUTPUT_COST
            )
            model_name = "Azure GPT-4o"
        
        total = gpt_cost
        breakdown = [f"מודל {model_name}: ${gpt_cost:.3f}"]
        
        if include_audio:
            tts_chars = words * CHARS_PER_WORD
            if tts_provider == "elevenlabs":
                tts_cost = (tts_chars / 1000) * ELEVENLABS_COST_PER_THOUSAND
                tts_name = "ElevenLabs"
            else:
                tts_cost = (tts_chars / 1000) * AZURE_TTS_COST_PER_THOUSAND
                tts_name = "Azure Neural"
            total += tts_cost
            breakdown.append(f"TTS ({tts_name}): ${tts_cost:.3f} ({int(tts_chars):,} תווים)")
        
        # Google AI Visuals cost
        if visual_gen == "imagen" and visual_count > 0:
            imagen_cost = visual_count * IMAGEN_COST_PER_IMAGE
            total += imagen_cost
            breakdown.append(f"Imagen 4 ({visual_count} תמונות): ${imagen_cost:.2f}")
        elif visual_gen == "veo" and visual_count > 0:
            veo_cost = visual_count * VEO_COST_PER_SECOND
            total += veo_cost
            breakdown.append(f"VEO ({visual_count} שניות): ${veo_cost:.2f}")
        elif visual_gen == "hybrid" and visual_count > 0:
            # Assume half images, half video seconds for hybrid
            imagen_count = visual_count // 2
            veo_secs = visual_count - imagen_count
            hybrid_cost = (imagen_count * IMAGEN_COST_PER_IMAGE) + (veo_secs * VEO_COST_PER_SECOND)
            total += hybrid_cost
            breakdown.append(f"היברידי ({imagen_count} תמונות + {veo_secs} שניות): ${hybrid_cost:.2f}")
        
        if include_video:
            total += VIDEO_OVERHEAD_COST
            breakdown.append(f"וידאו / רינדור: ${VIDEO_OVERHEAD_COST:.2f}")
        
        if include_ppt:
            total += PPT_EXTRA_COST
            breakdown.append(f"PPTX/Story: ${PPT_EXTRA_COST:.2f}")
        
        breakdown.append("")
        breakdown.append(f"סה\"כ משוער: ${total:.3f}")
        
        # Add comparison if using ElevenLabs
        if include_audio and tts_provider == "elevenlabs":
            azure_tts = (words * CHARS_PER_WORD / 1000) * AZURE_TTS_COST_PER_THOUSAND
            diff = tts_cost - azure_tts
            breakdown.append(f"(הפרש מ-Azure TTS: +${diff:.3f})")
        
        # Add warning for expensive VEO
        if visual_gen == "veo" and visual_count > 0:
            breakdown.append("⚠️ VEO יקר מאוד! שקול להשתמש ב-Manim או Imagen")
        
        return "\n".join(breakdown), total
