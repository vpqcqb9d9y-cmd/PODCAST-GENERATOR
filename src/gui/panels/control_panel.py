from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def build_control_panel(
    parent,
    section_label: Callable[[str], QLabel],
    helper_label: Callable[[str], QLabel],
    inline_row: Callable[[str, QWidget, QPushButton], QHBoxLayout],
) -> QWidget:
    """
    Control Panel grouped into three sections:
    1) Inputs (Transcript + Project Name + Output Dir)
    2) Settings (Provider, Voice Profile, Visuals, Preview mode)
    3) Metadata editor
    4) Actions (Run Pipeline)
    """
    panel = QWidget()
    # Allow the app-level scroll wrapper to drive resizing while preventing bleed
    panel.setMinimumWidth(300)
    panel.setMaximumWidth(360)
    panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    outer_layout = QVBoxLayout(panel)
    outer_layout.setContentsMargins(0, 0, 0, 0)
    outer_layout.setSpacing(12)

    content = QWidget()
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    # --- Inputs ---
    inputs_box = QGroupBox("📂 שלב 1: מקורות (Inputs)")
    inputs_layout = QVBoxLayout(inputs_box)

    parent.transcript_edit = QLineEdit()
    parent.transcript_edit.setPlaceholderText("בחר קובץ .txt או .srt")
    transcript_btn = QPushButton("בחר תמלול")
    transcript_btn.setToolTip("פתח בחירת קובץ תמלול (TXT/SRT).")
    transcript_btn.clicked.connect(
        lambda: parent._pick_file(
            parent.transcript_edit,
            "Text Files (*.txt *.srt *.vtt *.md)",
        )
    )
    inputs_layout.addLayout(inline_row("תמלול", parent.transcript_edit, transcript_btn))
    inputs_layout.addWidget(helper_label("קובץ הטקסט/תמלול שממנו יבנה הפודקאסט."))

    parent.output_dir_edit = QLineEdit(str(parent.settings.output_base_dir))
    parent.output_dir_edit.setToolTip("תיקיית פלט ראשית. ריק = outputs/.")
    output_btn = QPushButton("בחר תיקייה")
    output_btn.setToolTip("בחר תיקייה בה יישמרו כל התוצרים.")
    output_btn.clicked.connect(lambda: parent._pick_directory(parent.output_dir_edit))
    inputs_layout.addLayout(inline_row("תיקיית פלט", parent.output_dir_edit, output_btn))

    parent.custom_project_name = QLineEdit()
    parent.custom_project_name.setObjectName("custom_project_name")
    parent.custom_project_name.setPlaceholderText("(אופציונלי) שם פרויקט")
    parent.custom_project_name.setToolTip("שם תיקיית הפרויקט. ריק = שם אוטומטי מתאריך+נושא.")
    inputs_layout.addWidget(section_label("שם פרויקט"))
    inputs_layout.addWidget(parent.custom_project_name)
    parent.run_dir_preview = QLabel("")
    parent.run_dir_preview.setObjectName("run_dir_preview")
    parent.run_dir_preview.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.run_dir_preview.setStyleSheet("color:#94a3b8;")
    inputs_layout.addWidget(parent.run_dir_preview)

    layout.addWidget(inputs_box)

    # --- Settings ---
    settings_box = QGroupBox("⚙️ שלב 2: הגדרות (Settings)")
    settings_layout = QVBoxLayout(settings_box)

    parent.tts_provider_combo = QComboBox()
    parent.tts_provider_combo.setObjectName("tts_provider_combo")
    parent.tts_provider_combo.addItem("Azure Neural TTS", "azure")
    parent.tts_provider_combo.addItem("ElevenLabs (טבעי יותר)", "elevenlabs")
    parent.tts_provider_combo.currentIndexChanged.connect(parent._handle_tts_provider_change)
    parent.tts_provider_combo.setToolTip("בחר ספק TTS: Azure (חסכוני) או ElevenLabs (איכותי).")
    parent.elevenlabs_voices_btn = QPushButton("בחר קולות")
    parent.elevenlabs_voices_btn.setObjectName("elevenlabs_voices_btn")
    parent.elevenlabs_voices_btn.setToolTip("פתח בורר קולות ElevenLabs לבחירת קולות מותאמים.")
    parent.elevenlabs_voices_btn.clicked.connect(parent._open_elevenlabs_voice_selector)
    settings_layout.addLayout(inline_row("ספק דיבור", parent.tts_provider_combo, parent.elevenlabs_voices_btn))

    parent.azure_voice_combo = QComboBox()
    parent.azure_voice_combo.setObjectName("azure_voice_combo")
    parent.azure_voice_combo.addItem("he-IL-AvriNeural (Roee)", "he-IL-AvriNeural")
    parent.azure_voice_combo.addItem("he-IL-HilaNeural (Noa)", "he-IL-HilaNeural")
    azure_row = inline_row("קול Azure", parent.azure_voice_combo, QPushButton(" "))
    azure_row.itemAt(2).widget().setVisible(False)
    settings_layout.addLayout(azure_row)

    parent.voice_combo = QComboBox()
    parent.voice_combo.setObjectName("voice_combo")
    for name in (parent.voice_manager.profile_names or [parent.voice_manager.default_voice_profile]):
        parent.voice_combo.addItem(name)
    parent.voice_combo.currentIndexChanged.connect(parent._handle_voice_profile_change)
    parent.voice_combo.setToolTip("בחר פרופיל קולות (Azure/ElevenLabs) למנחים.")
    settings_layout.addLayout(inline_row("פרופיל קולות", parent.voice_combo, QPushButton(" ")))
    settings_layout.itemAt(settings_layout.count() - 1).layout().itemAt(2).widget().setVisible(False)

    # Output mode combo drives the checkboxes
    parent.output_mode_combo = QComboBox()
    parent.output_mode_combo.setObjectName("output_mode_combo")
    parent.output_mode_combo.addItem("Audio Only (MP3)", "audio")
    parent.output_mode_combo.addItem("Video + Audio", "video_audio")
    parent.output_mode_combo.addItem("Presentation Only", "presentation")
    parent.output_mode_combo.addItem("Full Suite (All)", "all")
    settings_layout.addLayout(inline_row("מצב פלט", parent.output_mode_combo, QPushButton(" ")))
    settings_layout.itemAt(settings_layout.count() - 1).layout().itemAt(2).widget().setVisible(False)

    # Spacer to prevent Output Mode dropdown overlap with checkboxes below
    settings_layout.addSpacing(8)

    parent.include_visuals_cb = QCheckBox("כלול וידאו/ויזואליזציות")
    parent.include_visuals_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.include_visuals_cb.setChecked(True)
    parent.include_visuals_cb.setToolTip("יצירת וידאו/תמונות (עלות נוספת לפי מנוע נבחר).")
    parent.export_ppt_cb = QCheckBox("יצירת מצגת")
    parent.export_ppt_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.export_ppt_cb.setChecked(False)
    parent.export_ppt_cb.setToolTip("ייצוא מצגת PPTX מסיכומי ההרצאה.")
    settings_layout.addWidget(parent.include_visuals_cb)
    settings_layout.addWidget(parent.export_ppt_cb)

    parent.preview_mode_cb = QCheckBox("מצב טיוטה (30 שניות ראשונות)")
    parent.preview_mode_cb.setObjectName("preview_mode_cb")
    parent.preview_mode_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.preview_mode_cb.setChecked(getattr(parent.settings, "preview_mode", False))
    parent.preview_mode_cb.setToolTip("חוסך קרדיטים: מפעיל רק 5 פניות ראשונות לדיאלוג/קול.")
    settings_layout.addWidget(parent.preview_mode_cb)

    parent.skip_cache_cb = QCheckBox("דלג על מטמון דיאלוג")
    parent.skip_cache_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.force_cb = QCheckBox("דרוס קבצים קיימים (Force)")
    parent.force_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    parent.dry_run_cb = QCheckBox("הרצה יבשה (ללא הפקה)")
    parent.dry_run_cb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    settings_layout.addWidget(parent.skip_cache_cb)
    settings_layout.addWidget(parent.force_cb)
    settings_layout.addWidget(parent.dry_run_cb)

    layout.addWidget(settings_box)

    # --- Metadata editor ---
    meta_box = QGroupBox("🧾 מטא-דאטה")
    meta_layout = QVBoxLayout(meta_box)
    meta_layout.addWidget(section_label("מטא-דאטה שנבנה בזמן אמת"))
    meta_layout.addWidget(
        helper_label("התוכן מתעדכן בזמן צ'אט והרצות Pipeline. ניתן לערוך ידנית.")
    )

    parent.metadata_preview = QPlainTextEdit()
    parent.metadata_preview.setObjectName("MetadataPreview")
    parent.metadata_preview.setPlaceholderText('{\n  "topic": "...",\n  "date": "2025-11-25"\n}')
    parent.metadata_preview.textChanged.connect(parent._handle_metadata_editor_change)
    meta_layout.addWidget(parent.metadata_preview)

    meta_actions = QHBoxLayout()
    parent.meta_save_btn = QPushButton("שמור שינויים")
    parent.meta_save_btn.setEnabled(False)
    parent.meta_save_btn.clicked.connect(parent._save_metadata_from_editor)

    parent.meta_revert_btn = QPushButton("שחזר")
    parent.meta_revert_btn.setEnabled(False)
    parent.meta_revert_btn.clicked.connect(parent._revert_metadata_editor)

    network_btn = QPushButton("מפת רשת")
    network_btn.clicked.connect(parent._export_network_map)

    export_btn = QPushButton("ייצוא JSON...")
    export_btn.clicked.connect(parent._export_metadata_to_file)

    meta_actions.addWidget(parent.meta_save_btn)
    meta_actions.addWidget(parent.meta_revert_btn)
    meta_actions.addWidget(network_btn)
    meta_actions.addWidget(export_btn)
    meta_layout.addLayout(meta_actions)

    # Visual metadata row
    visual_row = QHBoxLayout()
    parent.visual_meta_btn = QPushButton("🎨 צור מטא-דאטה ויזואלית")
    parent.visual_meta_btn.setToolTip(
        "ייצור prompts מפורטים ל-10 תמונות + וידאו (Imagen/VEO)."
    )
    parent.visual_meta_btn.clicked.connect(parent._generate_visual_metadata)
    parent.visual_meta_status = QLabel("")
    parent.visual_meta_status.setProperty("class", "helper")
    visual_row.addWidget(parent.visual_meta_btn)
    visual_row.addWidget(parent.visual_meta_status, 1)
    meta_layout.addLayout(visual_row)

    layout.addWidget(meta_box)

    # --- Run status (ETA/progress) ---
    status_box = QGroupBox("🚦 סטטוס ו-ETA")
    status_layout = QVBoxLayout(status_box)

    parent.run_stage_label = QLabel("אין ריצה פעילה")
    parent.run_stage_label.setStyleSheet("font-size:16px;font-weight:600;")
    status_layout.addWidget(parent.run_stage_label)

    parent.run_progress_bar = QProgressBar()
    parent.run_progress_bar.setRange(0, 100)
    parent.run_progress_bar.setValue(0)
    status_layout.addWidget(parent.run_progress_bar)

    parent.run_timer_label = QLabel("כשתתחיל הרצה נראה כאן את ההתקדמות וה-ETA.")
    parent.run_timer_label.setProperty("class", "helper")
    status_layout.addWidget(parent.run_timer_label)

    parent.run_status_card = status_box
    parent.run_status_card.setVisible(False)

    layout.addWidget(status_box)

    # --- Actions ---
    actions_box = QGroupBox("🚀 שלב 3: ביצוע (Actions)")
    actions_layout = QVBoxLayout(actions_box)
    parent.run_button = QPushButton("הפעל Pipeline")
    parent.run_button.setObjectName("run_pipeline_btn")
    parent.run_button.setToolTip("הרץ את הפייפליין עם ההגדרות הנוכחיות.")
    parent.run_button.clicked.connect(parent._run_pipeline)
    actions_layout.addWidget(parent.run_button)

    open_btn = QPushButton("פתח תיקיית פלט")
    open_btn.setObjectName("open_output_btn")
    open_btn.setToolTip("פתח את תיקיית הפלט העדכנית.")
    open_btn.clicked.connect(parent._open_outputs)
    actions_layout.addWidget(open_btn)
    layout.addWidget(actions_box)

    layout.addStretch(1)
    outer_layout.addWidget(content)
    return panel
