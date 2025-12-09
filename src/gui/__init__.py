"""
M.B.S Studio - Interactive Desktop GUI
=======================================

A comprehensive GUI application for the M.B.S Studio podcast generation pipeline.
Provides a three-panel interface for project management, AI-powered chat workspace,
and pipeline control with live progress tracking.

Modules:
    - app: Main application window (PodcastGeneratorWindow)
    - constants: Application-wide constants and configuration
    - workers: Background worker threads (Pipeline, Chat, Metadata)
    - widgets: Custom UI components (SmoothScrollArea, ChatBubbleDelegate)
    - dialogs/: Dialog windows (Onboarding, Appearance, Cost, Log)
    - panels/: Panel builders (Projects, Workspace, Summary)

Usage:
    >>> from src.gui import main
    >>> main()  # Launch the GUI application

Author: M.B.S Studio
Version: 2.0.0 (Refactored)
"""

from .app import main, PodcastGeneratorWindow  # noqa: F401
from .constants import (
    APP_DISPLAY_NAME,
    APP_ASSISTANT_NAME,
    PIPELINE_STAGES,
)  # noqa: F401

__all__ = [
    "main",
    "PodcastGeneratorWindow",
    "APP_DISPLAY_NAME",
    "APP_ASSISTANT_NAME",
    "PIPELINE_STAGES",
]

