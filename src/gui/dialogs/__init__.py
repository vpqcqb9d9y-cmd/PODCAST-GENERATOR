"""
M.B.S Studio - Dialog Components
=================================

Modal dialog windows for the M.B.S Studio application.

Dialogs:
    - OnboardingWizard: Multi-step quick start wizard
    - ChatAppearanceDialog: Chat display customization
    - VisualSettingsDialog: Visual generation configuration
    - CostCenterDialog: Cost management and analytics
    - LogCenterDialog: Log viewer and export
    - AboutDialog: Application information
    - BackupRestoreDialog: Backup and restore settings
    - ElevenLabsVoiceSelectorDialog: ElevenLabs voice selection
    - QualityReportDialog: Quality verification results

Author: M.B.S Studio
Version: 3.1.3
"""

from .about import AboutDialog
from .appearance import ChatAppearanceDialog
from .backup import BackupRestoreDialog
from .cost_center import CostCenterDialog
from .log_center import LogCenterDialog
from .onboarding import OnboardingWizard
from .quality_report import QualityReportDialog
from .visual_settings import VisualSettingsDialog
from .voice_selector import ElevenLabsVoiceSelectorDialog

__all__ = [
    "AboutDialog",
    "BackupRestoreDialog",
    "ChatAppearanceDialog",
    "CostCenterDialog",
    "ElevenLabsVoiceSelectorDialog",
    "LogCenterDialog",
    "OnboardingWizard",
    "QualityReportDialog",
    "VisualSettingsDialog",
]

