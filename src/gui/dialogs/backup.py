"""
M.B.S Studio - Backup/Restore Dialog
=====================================

Dialog for creating and restoring application backups.

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils import Settings
from ..constants import APP_VERSION


class BackupRestoreDialog(QDialog):
    """
    Dialog for managing application backups.
    
    Features:
        - Create new backup (settings + history + outputs)
        - List existing backups
        - Restore from backup
        - Delete old backups
    """

    def __init__(
        self,
        settings: Settings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.backup_dir = Path(settings.output_base_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.setWindowTitle("גיבוי ושחזור")
        self.resize(500, 400)
        self._setup_ui()
        self._refresh_backup_list()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("💾 גיבוי ושחזור הגדרות")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "צרו גיבוי של ההגדרות והפרויקטים שלכם, או שחזרו מגיבוי קודם."
        )
        desc.setStyleSheet("color: #94a3b8;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Action buttons
        action_row = QHBoxLayout()
        
        self.create_btn = QPushButton("📦 צור גיבוי חדש")
        self.create_btn.clicked.connect(self._create_backup)
        action_row.addWidget(self.create_btn)
        
        self.import_btn = QPushButton("📂 ייבא גיבוי")
        self.import_btn.clicked.connect(self._import_backup)
        action_row.addWidget(self.import_btn)
        
        layout.addLayout(action_row)
        
        # Backups list
        layout.addWidget(QLabel("גיבויים קיימים:"))
        self.backup_list = QListWidget()
        self.backup_list.setSpacing(4)
        layout.addWidget(self.backup_list, 1)
        
        # List action buttons
        list_actions = QHBoxLayout()
        
        self.restore_btn = QPushButton("♻️ שחזר גיבוי נבחר")
        self.restore_btn.clicked.connect(self._restore_backup)
        list_actions.addWidget(self.restore_btn)
        
        self.delete_btn = QPushButton("🗑️ מחק גיבוי")
        self.delete_btn.clicked.connect(self._delete_backup)
        list_actions.addWidget(self.delete_btn)
        
        self.open_folder_btn = QPushButton("📁 פתח תיקייה")
        self.open_folder_btn.clicked.connect(self._open_backup_folder)
        list_actions.addWidget(self.open_folder_btn)
        
        layout.addLayout(list_actions)
        
        # Close button
        close_btn = QPushButton("סגור")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _refresh_backup_list(self) -> None:
        """Refresh the list of available backups."""
        self.backup_list.clear()
        
        if not self.backup_dir.exists():
            return
        
        backups = sorted(
            self.backup_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for backup_path in backups:
            # Extract info from filename
            name = backup_path.stem
            size_bytes = backup_path.stat().st_size
            mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
            
            # Show KB for small files, MB for larger
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            
            item = QListWidgetItem(
                f"📦 {name}\n   📅 {mtime.strftime('%Y-%m-%d %H:%M')} | 💾 {size_str}"
            )
            item.setData(Qt.ItemDataRole.UserRole, str(backup_path))
            self.backup_list.addItem(item)

    def _create_backup(self) -> None:
        """Create a new backup of settings and data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.zip"
        backup_path = self.backup_dir / backup_name
        files_backed_up = []
        
        try:
            # Get project root directory
            project_root = Path(__file__).resolve().parents[3]
            
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Backup .env file (important!)
                env_path = project_root / ".env"
                if env_path.exists():
                    zf.write(env_path, ".env")
                    files_backed_up.append(".env")
                
                # Backup UI preferences
                if self.settings.ui_preferences_path.exists():
                    zf.write(
                        self.settings.ui_preferences_path,
                        "ui_preferences.json",
                    )
                    files_backed_up.append("ui_preferences.json")
                
                # Backup history.json if exists
                history_path = Path(self.settings.output_base_dir) / "history.json"
                if history_path.exists():
                    zf.write(history_path, "history.json")
                    files_backed_up.append("history.json")
                
                # Backup _gui_metadata.json if exists
                gui_meta_path = Path(self.settings.output_base_dir) / "_gui_metadata.json"
                if gui_meta_path.exists():
                    zf.write(gui_meta_path, "_gui_metadata.json")
                    files_backed_up.append("_gui_metadata.json")
                
                # Backup config folder
                config_dir = project_root / "config"
                if config_dir.exists():
                    for config_file in config_dir.glob("*.json"):
                        arcname = f"config/{config_file.name}"
                        zf.write(config_file, arcname)
                        files_backed_up.append(arcname)
                
                # Create metadata
                metadata = {
                    "created": timestamp,
                    "version": APP_VERSION,
                    "output_dir": str(self.settings.output_base_dir),
                    "files": files_backed_up,
                }
                zf.writestr("backup_meta.json", json.dumps(metadata, indent=2))
            
            files_list = "\n".join(f"  • {f}" for f in files_backed_up)
            QMessageBox.information(
                self,
                "גיבוי נוצר",
                f"הגיבוי נשמר בהצלחה:\n{backup_path.name}\n\nקבצים שגובו:\n{files_list}",
            )
            self._refresh_backup_list()
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "שגיאה",
                f"יצירת הגיבוי נכשלה:\n{e}",
            )

    def _import_backup(self) -> None:
        """Import a backup file from external location."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "ייבוא גיבוי",
            "",
            "Backup Files (*.zip)",
        )
        if not path:
            return
        
        source = Path(path)
        dest = self.backup_dir / source.name
        
        # Handle duplicate names
        counter = 1
        while dest.exists():
            dest = self.backup_dir / f"{source.stem}_{counter}.zip"
            counter += 1
        
        try:
            shutil.copy2(source, dest)
            QMessageBox.information(
                self,
                "ייבוא הושלם",
                f"הגיבוי יובא בהצלחה:\n{dest.name}",
            )
            self._refresh_backup_list()
        except Exception as e:
            QMessageBox.warning(self, "שגיאה", f"ייבוא הגיבוי נכשל:\n{e}")

    def _restore_backup(self) -> None:
        """Restore from selected backup."""
        items = self.backup_list.selectedItems()
        if not items:
            QMessageBox.information(self, "שחזור", "בחרו גיבוי מהרשימה.")
            return
        
        backup_path = Path(items[0].data(Qt.ItemDataRole.UserRole))
        if not backup_path.exists():
            QMessageBox.warning(self, "שגיאה", "קובץ הגיבוי לא נמצא.")
            return
        
        reply = QMessageBox.question(
            self,
            "אישור שחזור",
            "האם אתם בטוחים שברצונכם לשחזר מגיבוי זה?\n"
            "ההגדרות הנוכחיות יוחלפו.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            project_root = Path(__file__).resolve().parents[3]
            restored_files = []
            
            with zipfile.ZipFile(backup_path, "r") as zf:
                # Restore .env file
                if ".env" in zf.namelist():
                    env_data = zf.read(".env")
                    env_path = project_root / ".env"
                    env_path.write_bytes(env_data)
                    restored_files.append(".env")
                
                # Restore UI preferences
                if "ui_preferences.json" in zf.namelist():
                    prefs_data = zf.read("ui_preferences.json")
                    self.settings.ui_preferences_path.parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    self.settings.ui_preferences_path.write_bytes(prefs_data)
                    restored_files.append("ui_preferences.json")
                
                # Restore history
                if "history.json" in zf.namelist():
                    history_data = zf.read("history.json")
                    history_path = Path(self.settings.output_base_dir) / "history.json"
                    history_path.write_bytes(history_data)
                    restored_files.append("history.json")
                
                # Restore _gui_metadata.json
                if "_gui_metadata.json" in zf.namelist():
                    gui_meta_data = zf.read("_gui_metadata.json")
                    gui_meta_path = Path(self.settings.output_base_dir) / "_gui_metadata.json"
                    gui_meta_path.write_bytes(gui_meta_data)
                    restored_files.append("_gui_metadata.json")
                
                # Restore config files
                config_dir = project_root / "config"
                config_dir.mkdir(parents=True, exist_ok=True)
                for name in zf.namelist():
                    if name.startswith("config/") and name.endswith(".json"):
                        config_data = zf.read(name)
                        config_file = project_root / name
                        config_file.write_bytes(config_data)
                        restored_files.append(name)
            
            files_list = "\n".join(f"  • {f}" for f in restored_files)
            QMessageBox.information(
                self,
                "שחזור הושלם",
                f"ההגדרות שוחזרו בהצלחה!\n\nקבצים ששוחזרו:\n{files_list}\n\n"
                "הפעילו מחדש את האפליקציה לטעינת השינויים.",
            )
            # Refresh list in case timestamps or naming changed externally
            self._refresh_backup_list()
            
        except Exception as e:
            QMessageBox.warning(self, "שגיאה", f"שחזור הגיבוי נכשל:\n{e}")

    def _delete_backup(self) -> None:
        """Delete selected backup."""
        items = self.backup_list.selectedItems()
        if not items:
            QMessageBox.information(self, "מחיקה", "בחרו גיבוי מהרשימה.")
            return
        
        backup_path = Path(items[0].data(Qt.ItemDataRole.UserRole))
        
        reply = QMessageBox.question(
            self,
            "אישור מחיקה",
            f"האם אתם בטוחים שברצונכם למחוק את הגיבוי?\n{backup_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            backup_path.unlink()
            self._refresh_backup_list()
        except Exception as e:
            QMessageBox.warning(self, "שגיאה", f"מחיקת הגיבוי נכשלה:\n{e}")

    def _open_backup_folder(self) -> None:
        """Open the backup folder in file explorer."""
        import os
        import subprocess
        
        if self.backup_dir.exists():
            if os.name == "nt":
                subprocess.run(["explorer", str(self.backup_dir)])
            else:
                subprocess.run(["xdg-open", str(self.backup_dir)])

