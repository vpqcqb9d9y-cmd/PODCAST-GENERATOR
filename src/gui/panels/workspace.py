"""
M.B.S Studio - Workspace Panel Builder
=======================================

Builds the center workspace panel containing the AI chat,
materials attachments, and template buttons.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..widgets import ChatBubbleDelegate

if TYPE_CHECKING:
    from ..app import PodcastGeneratorWindow


def build_workspace_panel(
    parent: "PodcastGeneratorWindow",
    section_label: Callable[[str], QLabel],
    card_widget: Callable[[], QFrame],
) -> QWidget:
    """
    Build the workspace panel (center area).
    
    Contains:
        - Hero prompt and quick action buttons
        - Template chips for common prompts
        - Live AI chat with bubble rendering
        - Materials/URLs attachment area
        - Chat input with model selection
    
    Args:
        parent: Main window reference
        section_label: Factory for section labels
        card_widget: Factory for card widgets
        
    Returns:
        QWidget containing the workspace panel
    """
    panel = QWidget()
    panel.setMinimumWidth(360)
    layout = QVBoxLayout(panel)
    parent.template_buttons = []
    
    # Header row with hero prompt
    layout.addLayout(_build_header_row(parent))
    
    # Onboarding label
    parent.onboarding_label = QLabel()
    parent.onboarding_label.setWordWrap(True)
    parent.onboarding_label.setStyleSheet("color:#475569;")
    layout.addWidget(parent.onboarding_label)
    
    # Template chips
    layout.addLayout(_build_template_chips(parent))
    
    # Chat + attachments in splitter so users can resize live chat height
    chat_card = _build_chat_card(parent, section_label, card_widget)
    parent.chat_card = chat_card
    
    attachments_card = _build_attachments_card(parent, card_widget)
    
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setChildrenCollapsible(False)
    splitter.addWidget(chat_card)
    splitter.addWidget(attachments_card)
    # Bias toward chat but start more compact so it doesn't dominate the view
    splitter.setStretchFactor(0, 6)
    splitter.setStretchFactor(1, 2)
    splitter.setSizes([440, 280])
    layout.addWidget(splitter, 8)
    
    # Chat input row
    layout.addLayout(_build_chat_input_row(parent))
    
    # Enter key option
    layout.addLayout(_build_enter_option_row(parent))
    
    return panel


def _build_header_row(parent: "PodcastGeneratorWindow") -> QHBoxLayout:
    """
    Build the header row with hero prompt and action buttons.
    
    Args:
        parent: Main window reference
        
    Returns:
        QHBoxLayout with header components
    """
    header_row = QHBoxLayout()
    
    hero = QLabel("תאר את ההרצאה ותן לבינה לעשות את השאר")
    hero.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
    header_row.addWidget(hero)
    header_row.addStretch(1)
    
    # Wizard button
    wizard_btn = QPushButton("אשף התחלה מהירה")
    wizard_btn.setToolTip(
        "פתח תאור קצר של שלבי העבודה והטיפים החשובים לפני ההרצה הראשונה."
    )
    wizard_btn.clicked.connect(parent._open_onboarding_wizard)
    header_row.addWidget(wizard_btn)
    
    # Quick run button
    parent.quick_run_btn = QPushButton("הפעל Pipeline")
    parent.quick_run_btn.setObjectName("PrimaryButton")
    parent.quick_run_btn.setToolTip("הרצה מהירה של ה-Pipeline מתוך הסקשן המרכזי.")
    parent.quick_run_btn.clicked.connect(parent._run_pipeline)
    header_row.addWidget(parent.quick_run_btn)
    
    return header_row


def _build_template_chips(parent: "PodcastGeneratorWindow") -> QGridLayout:
    """
    Build the template prompt chips grid.
    
    Args:
        parent: Main window reference
        
    Returns:
        QGridLayout with template buttons
    """
    chips_layout = QGridLayout()
    chips_layout.setHorizontalSpacing(8)
    chips_layout.setVerticalSpacing(8)
    
    templates = (
        "סכם שיעור זה",
        "בנה מטא-דאטה",
        "שאל על תובנות",
        "תכנן מצגת",
    )
    
    for idx, text in enumerate(templates):
        chip = QPushButton(text)
        chip.setObjectName("Chip")
        chip.setToolTip(f"שלח פרומפט מוכן מראש: {text}")
        chip.clicked.connect(lambda _, t=text: parent._send_template_prompt(t))
        parent.template_buttons.append(chip)
        row = idx // 2
        col = idx % 2
        chips_layout.addWidget(chip, row, col)
    
    return chips_layout


def _build_chat_card(
    parent: "PodcastGeneratorWindow",
    section_label: Callable[[str], QLabel],
    card_widget: Callable[[], QFrame],
) -> QFrame:
    """
    Build the chat card with message history.
    
    Args:
        parent: Main window reference
        section_label: Factory for section labels
        card_widget: Factory for card widgets
        
    Returns:
        QFrame containing the chat card
    """
    chat_card = card_widget()
    chat_card.setObjectName("ChatCard")
    chat_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    chat_layout = QVBoxLayout(chat_card)
    
    chat_layout.addWidget(section_label("שיחה חיה"))
    
    # Chat toolbar
    chat_toolbar = QHBoxLayout()
    
    parent.chat_clear_btn = QPushButton("נקה שיחה")
    parent.chat_clear_btn.setToolTip("אפס את היסטוריית השיחה הנוכחית.")
    parent.chat_clear_btn.clicked.connect(parent._clear_chat_history)
    chat_toolbar.addWidget(parent.chat_clear_btn)
    
    parent.chat_to_transcript_btn = QPushButton("📝 צור תמלול")
    parent.chat_to_transcript_btn.setToolTip("צור תמלול מתוך השיחה וטען לפרויקט")
    parent.chat_to_transcript_btn.clicked.connect(parent._generate_transcript_from_chat)
    chat_toolbar.addWidget(parent.chat_to_transcript_btn)
    
    chat_toolbar.addStretch(1)
    chat_layout.addLayout(chat_toolbar)
    
    # Chat history list
    parent.chat_history = QListWidget()
    parent.chat_history.setObjectName("ChatHistory")
    parent.chat_history.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    # Start compact but allow user to resize via splitter
    parent.chat_history.setMinimumHeight(220)
    parent.chat_history.setWordWrap(True)
    parent.chat_history.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    parent.chat_history.setVerticalScrollMode(
        QAbstractItemView.ScrollMode.ScrollPerPixel
    )
    parent.chat_history.setSpacing(8)
    parent.chat_history.setResizeMode(QListView.ResizeMode.Adjust)
    
    # Set up bubble delegate
    parent.chat_delegate = ChatBubbleDelegate(
        parent.chat_history,
        config_provider=parent._chat_delegate_config,
    )
    parent.chat_history.setItemDelegate(parent.chat_delegate)
    
    chat_layout.addWidget(parent.chat_history)
    
    return chat_card


def _build_attachments_card(
    parent: "PodcastGeneratorWindow",
    card_widget: Callable[[], QFrame],
) -> QFrame:
    """
    Build the materials/URLs attachments card.
    
    Args:
        parent: Main window reference
        card_widget: Factory for card widgets
        
    Returns:
        QFrame containing the attachments card
    """
    attachments_card = card_widget()
    parent.attachments_card = attachments_card
    attachments_card.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    attach_layout = QVBoxLayout(attachments_card)
    
    attach_layout.addWidget(QLabel("חומרים תומכים"))
    
    # Materials list
    parent.materials_list = QListWidget()
    parent.materials_list.setToolTip(
        "קבצים שתצרפו יסרקו אוטומטית כדי להעשיר את המטא-דאטה."
    )
    attach_layout.addWidget(parent.materials_list)
    
    # Material buttons
    mat_buttons = QHBoxLayout()
    
    add_mat = QPushButton("העלה קבצים")
    add_mat.setToolTip("בחרו PDF / DOCX / PPTX שנרצה לסכם במטא-דאטה.")
    add_mat.clicked.connect(parent._add_materials)
    
    del_mat = QPushButton("מחק")
    del_mat.setToolTip("הסירו קבצים שאינם רלוונטיים יותר.")
    del_mat.clicked.connect(parent._remove_materials)
    
    mat_buttons.addWidget(add_mat)
    mat_buttons.addWidget(del_mat)
    attach_layout.addLayout(mat_buttons)
    
    # URLs text edit
    parent.urls_edit = QTextEdit()
    parent.urls_edit.setPlaceholderText("הדבק קישורים, שורה לכל URL")
    parent.urls_edit.setToolTip(
        "e.g. https://learn.microsoft.com/... – שורה נפרדת לכל קישור."
    )
    parent.urls_edit.textChanged.connect(parent._sync_materials_to_session)
    attach_layout.addWidget(parent.urls_edit)
    
    # Start with appropriate height based on current content
    if hasattr(parent, "_update_materials_card_size"):
        parent._update_materials_card_size()
    
    return attachments_card


def _build_chat_input_row(parent: "PodcastGeneratorWindow") -> QHBoxLayout:
    """
    Build the chat input row with model selector.
    
    Args:
        parent: Main window reference
        
    Returns:
        QHBoxLayout with chat input components
    """
    input_row = QHBoxLayout()
    
    # Model selector
    parent.chat_model_combo = QComboBox()
    parent.chat_model_combo.addItem("Gemini", "gemini")
    parent.chat_model_combo.addItem("Azure GPT", "azure")
    input_row.addWidget(parent.chat_model_combo)
    
    # Chat input
    parent.chat_input = QPlainTextEdit()
    parent.chat_input.setPlaceholderText("שאל את הבינה: מה הסיפור של ההרצאה?")
    parent.chat_input.setFixedHeight(80)
    parent.chat_input.installEventFilter(parent)
    input_row.addWidget(parent.chat_input, 1)
    
    # Send button
    parent.chat_send_btn = QPushButton("שלח")
    parent.chat_send_btn.setObjectName("PrimaryButton")
    parent.chat_send_btn.clicked.connect(parent._send_chat_message)
    input_row.addWidget(parent.chat_send_btn)
    
    return input_row


def _build_enter_option_row(parent: "PodcastGeneratorWindow") -> QHBoxLayout:
    """
    Build the enter key option row.
    
    Args:
        parent: Main window reference
        
    Returns:
        QHBoxLayout with enter option checkbox
    """
    enter_row = QHBoxLayout()
    enter_row.addStretch(1)
    
    parent.send_on_enter_cb = QCheckBox(
        "שלח עם Enter (Shift+Enter = שורה חדשה)"
    )
    parent.send_on_enter_cb.setChecked(True)
    enter_row.addWidget(parent.send_on_enter_cb)
    
    return enter_row

