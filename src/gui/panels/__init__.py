"""
M.B.S Studio - Panel Components
================================

Main panel building functions for the three-column layout.

Panels:
    - ProjectsPanel: Left sidebar with project list and explorer
    - WorkspacePanel: Center area with chat and materials
    - SummaryPanel: Right sidebar with controls and preview

Author: M.B.S Studio
Version: 1.0.0
"""

from .projects import build_projects_panel
from .workspace import build_workspace_panel
from .summary import build_summary_panel
from .control_panel import build_control_panel

__all__ = [
    "build_projects_panel",
    "build_workspace_panel",
    "build_summary_panel",
    "build_control_panel",
]

