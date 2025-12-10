"""
Quick environment probe for visual generation dependencies.

Checks imports for numpy, cv2 (opencv-python), and Google GenAI clients.
Use to rapidly detect broken/partial installations that may cause silent visual failures.
"""

from __future__ import annotations

import sys
import importlib


def check_import(module_name: str) -> tuple[bool, str]:
    """Attempt to import a module and return (ok, message)."""
    try:
        importlib.import_module(module_name)
        return True, f"OK: {module_name}"
    except Exception as exc:  # pragma: no cover - simple diagnostic helper
        return False, f"FAIL: {module_name} -> {exc.__class__.__name__}: {exc}"


def main() -> int:
    checks = [
        "numpy",
        "cv2",
        "google.generativeai",
        "google.genai",
    ]

    results = [check_import(mod) for mod in checks]
    for ok, message in results:
        print(message)

    failures = [msg for ok, msg in results if not ok]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

