"""
M.B.S Studio - Projects Panel Builder
======================================

Builds the left sidebar panel containing project list,
statistics, timeline, and NotebookLM-style explorer.

Author: M.B.S Studio
Version: 2.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..app import PodcastGeneratorWindow


def build_projects_panel(
    parent: "PodcastGeneratorWindow",
    section_label: Callable[[str], QLabel],
    card_widget: Callable[[], QFrame],
    add_stat_chip: Callable[[QHBoxLayout, str], QLabel],
) -> QWidget:
    """
    Build the projects panel (left sidebar).
    Uses a vertical splitter to allow resizing sections.
    """
    panel = QWidget()
    panel.setMinimumWidth(280)
    panel.setMaximumWidth(420)
    
    main_layout = QVBoxLayout(panel)
    main_layout.setContentsMargins(6, 6, 6, 6)
    main_layout.setSpacing(4)
    
    # === TOP SECTION: Stats & Load Button ===
    top_widget = QWidget()
    top_layout = QVBoxLayout(top_widget)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(4)
    
    top_layout.addWidget(section_label("פרויקטים אחרונים"))
    
    # Statistics row - compact chips
    stats_row = QHBoxLayout()
    stats_row.setSpacing(4)
    stats_row.setContentsMargins(0, 0, 0, 0)
    parent.run_count_value = add_stat_chip(stats_row, "ריצות")
    parent.total_cost_value = add_stat_chip(stats_row, "עלות")
    parent.last_topic_value = add_stat_chip(stats_row, "אחרון")
    top_layout.addLayout(stats_row)
    
    # Load/Clear buttons row
    btn_load_row = QHBoxLayout()
    btn_load_row.setSpacing(4)
    
    latest_btn = QPushButton("⚡ טען אחרונה")
    latest_btn.setFixedHeight(28)
    latest_btn.clicked.connect(parent._load_latest_history_entry)
    btn_load_row.addWidget(latest_btn)
    
    clear_load_btn = QPushButton("🧹 נקה טעינה")
    clear_load_btn.setFixedHeight(28)
    clear_load_btn.setToolTip("נקה את הריצה הטעונה (לא מוחק נתונים)")
    clear_load_btn.clicked.connect(parent._clear_loaded_entry)
    btn_load_row.addWidget(clear_load_btn)
    
    # Delete All button
    delete_all_btn = QPushButton("🗑️ מחק הכל")
    delete_all_btn.setFixedHeight(28)
    delete_all_btn.setToolTip("מחק את כל הפרויקטים והקבצים (שומר עלויות)")
    delete_all_btn.setStyleSheet("color: #ef4444; font-weight: bold;")
    delete_all_btn.clicked.connect(parent._delete_all_projects)
    btn_load_row.addWidget(delete_all_btn)
    
    top_layout.addLayout(btn_load_row)
    
    main_layout.addWidget(top_widget)
    
    # === VERTICAL SPLITTER for resizable sections ===
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setChildrenCollapsible(True)
    splitter.setHandleWidth(4)
    
    # --- Projects List Section ---
    projects_widget = QWidget()
    projects_layout = QVBoxLayout(projects_widget)
    projects_layout.setContentsMargins(0, 0, 0, 0)
    projects_layout.setSpacing(2)
    
    parent.projects_list = QListWidget()
    parent.projects_list.setObjectName("Projects")
    parent.projects_list.itemSelectionChanged.connect(parent._update_project_details)
    parent.projects_list.itemDoubleClicked.connect(parent._handle_project_double_click)
    projects_layout.addWidget(parent.projects_list)
    
    # Compact action buttons - 2 rows
    btn_row1 = QHBoxLayout()
    btn_row1.setSpacing(2)
    btn_row1.setContentsMargins(0, 2, 0, 0)
    
    def small_btn(text: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(26)
        btn.setToolTip(tooltip)
        return btn
    
    open_btn = small_btn("📂", "פתח תיקייה")
    open_btn.clicked.connect(parent._open_selected_run_dir)
    btn_row1.addWidget(open_btn)
    
    play_btn = small_btn("▶️", "נגן")
    play_btn.setObjectName("PlayButton")
    play_btn.clicked.connect(parent._open_selected_media)
    btn_row1.addWidget(play_btn)
    
    ppt_btn = small_btn("📊", "מצגת")
    ppt_btn.clicked.connect(parent._open_selected_ppt)
    btn_row1.addWidget(ppt_btn)
    
    story_btn = small_btn("📖", "Story")
    story_btn.clicked.connect(parent._open_selected_story)
    btn_row1.addWidget(story_btn)
    
    load_btn = small_btn("📥", "טען Workspace")
    load_btn.clicked.connect(parent._load_selected_history_entry)
    btn_row1.addWidget(load_btn)
    
    refresh_btn = small_btn("🔄", "רענן")
    refresh_btn.clicked.connect(parent._refresh_history)
    btn_row1.addWidget(refresh_btn)
    
    projects_layout.addLayout(btn_row1)
    splitter.addWidget(projects_widget)
    
    # --- Timeline Section ---
    timeline_widget = QWidget()
    timeline_layout = QVBoxLayout(timeline_widget)
    timeline_layout.setContentsMargins(0, 0, 0, 0)
    timeline_layout.setSpacing(2)
    
    # Timeline label with ETA explanation
    timeline_label = section_label("ציר זמן")
    timeline_label.setToolTip(
        "📊 הסבר על הערכת זמן (ETA):\n\n"
        "ETA מחושב לפי משקל יחסי של כל שלב:\n"
        "• יצירת דיאלוג (15%)\n"
        "• סינתזת קולות TTS (30%) - השלב הארוך ביותר\n"
        "• הלחנת אודיו (10%)\n"
        "• יצירת ויזואליים AI (10%)\n"
        "• הרכבת וידאו (20%)\n"
        "• שלבים נוספים (15%)\n\n"
        "ה-ETA מתעדכן בזמן אמת לפי התקדמות בפועל."
    )
    timeline_layout.addWidget(timeline_label)
    
    parent.timeline_list = QListWidget()
    parent.timeline_list.setMinimumHeight(40)
    parent.timeline_list.setToolTip(
        "רשימת הריצות האחרונות של ה-Pipeline.\n"
        "לחץ על ריצה כדי לראות פרטים נוספים."
    )
    timeline_layout.addWidget(parent.timeline_list)
    
    splitter.addWidget(timeline_widget)
    
    # --- Explorer Section ---
    explorer_card = _build_explorer_card(parent, section_label, card_widget)
    splitter.addWidget(explorer_card)
    
    # Set initial sizes: projects 30%, timeline 20%, explorer 50%
    splitter.setSizes([150, 100, 250])
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)
    splitter.setStretchFactor(2, 2)
    
    main_layout.addWidget(splitter, 1)
    
    # Hidden project details (used internally)
    parent.project_details = QLabel()
    parent.project_details.setVisible(False)
    
    return panel


def _build_explorer_card(
    parent: "PodcastGeneratorWindow",
    section_label: Callable[[str], QLabel],
    card_widget: Callable[[], QFrame],
) -> QFrame:
    """Build the NotebookLM-style explorer card."""
    explorer_card = card_widget()
    explorer_card.setMinimumHeight(120)
    explorer_layout = QVBoxLayout(explorer_card)
    explorer_layout.setContentsMargins(6, 6, 6, 6)
    explorer_layout.setSpacing(4)
    
    explorer_layout.addWidget(section_label("📁 סייר תוצרים"))
    
    # Search filter
    parent.card_filter = QLineEdit()
    parent.card_filter.setPlaceholderText("🔍 חפש...")
    parent.card_filter.setFixedHeight(28)
    parent.card_filter.textChanged.connect(parent._filter_project_cards)
    explorer_layout.addWidget(parent.card_filter)
    
    # Project cards list - main component
    parent.project_cards = QListWidget()
    parent.project_cards.setMinimumHeight(60)
    parent.project_cards.setSpacing(3)
    parent.project_cards.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    parent.project_cards.itemSelectionChanged.connect(parent._update_card_buttons)
    explorer_layout.addWidget(parent.project_cards, 1)
    
    # Card action buttons - compact row
    card_buttons = QHBoxLayout()
    card_buttons.setSpacing(2)
    card_buttons.setContentsMargins(0, 2, 0, 0)
    
    def card_btn(text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(26)
        btn.setToolTip(tooltip)
        return btn
    
    parent.card_open_btn = card_btn("📂", "פתח תיקייה")
    parent.card_open_btn.clicked.connect(parent._open_selected_card_dir)
    
    parent.card_delete_btn = card_btn("🗑️", "מחק ריצה")
    parent.card_delete_btn.clicked.connect(parent._delete_selected_card)
    
    parent.card_import_btn = card_btn("📥", "ייבא תיקייה")
    parent.card_import_btn.clicked.connect(parent._browse_project_directory)
    
    card_buttons.addWidget(parent.card_open_btn)
    card_buttons.addWidget(parent.card_delete_btn)
    card_buttons.addWidget(parent.card_import_btn)
    card_buttons.addStretch(1)
    
    explorer_layout.addLayout(card_buttons)
    
    return explorer_card
