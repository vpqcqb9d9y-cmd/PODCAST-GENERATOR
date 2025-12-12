"""
System monitor controller for live system metrics.

Encapsulates psutil loading, metric polling, and UI updates for the system
status banner and compact header badge. Keeps the main window lean while
preserving existing behavior and messages.
"""

from __future__ import annotations

import importlib
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QFrame, QStatusBar, QWidget, QMessageBox


class SystemMonitorController(QObject):
    """
    Controller responsible for system metric collection and banner updates.

    This class wraps psutil loading, periodic metric polling, and UI updates
    for CPU, memory, battery, and network latency. It also provides lightweight
    connectivity checks used by network-dependent flows.
    """

    stats_updated = pyqtSignal(dict)
    """Signal emitted when metrics are refreshed with a payload of values."""

    def __init__(
        self,
        *,
        parent: Optional[QObject],
        logger: logging.Logger,
        status_bar: Optional[QStatusBar],
        system_status_banner: Optional[QFrame],
        cpu_label: Optional[QLabel],
        memory_label: Optional[QLabel],
        battery_label: Optional[QLabel],
        network_label: Optional[QLabel],
        system_badge_label: Optional[QLabel] = None,
    ) -> None:
        super().__init__(parent)
        self.logger = logger
        self.status_bar = status_bar
        self.system_status_banner = system_status_banner
        self.cpu_label = cpu_label
        self.memory_label = memory_label
        self.battery_label = battery_label
        self.network_label = network_label
        self.system_badge_label = system_badge_label

        self._system_metrics_timer: Optional[QTimer] = None
        self._psutil_mod = None
        self._psutil_retry_scheduled = False
        self._psutil_last_error: Optional[str] = None
        self._psutil_attempts: int = 0
        self._last_cpu_percent: float = 0.0
        self._system_badge_values: Dict[str, str] = {"cpu": "CPU --", "mem": "MEM --", "net": "NET --"}

    # Public API -----------------------------------------------------
    def init_system_status_bar(self) -> None:
        """Initialize the bottom system status banner with live metrics."""
        banner_ready = all(
            widget is not None
            for widget in (self.system_status_banner, self.cpu_label, self.memory_label, self.battery_label, self.network_label)
        )
        if not banner_ready:
            self.logger.warning("[System Status] Banner widgets not ready")
            return

        self.logger.info("[System Status] Initializing system status banner")
        self._psutil_attempts += 1

        psutil_mod = self._load_psutil_module()
        if not psutil_mod:
            self.logger.warning("[System Status] psutil not available - will retry")
            for label in (self.cpu_label, self.memory_label, self.battery_label, self.network_label):
                if label:
                    label.setText("psutil חסר")
                    label.setStyleSheet("font-weight:600; color:#94a3b8; padding:0 8px;")
            if self.system_status_banner:
                tooltip = "psutil לא הותקן או לא נטען. התקן עם: pip install psutil"
                if self._psutil_last_error:
                    tooltip += f"\nשגיאה: {self._psutil_last_error}"
                self.system_status_banner.setToolTip(tooltip)
            if self.status_bar:
                msg = "psutil חסר – התקן psutil בסביבה (pip install psutil)"
                if self._psutil_last_error:
                    msg += f" ({self._psutil_last_error})"
                self.status_bar.showMessage(msg, 8000)

            # Try twice only
            if self._psutil_attempts >= 2:
                self._psutil_retry_scheduled = False
                return

            if not self._psutil_retry_scheduled:
                self._psutil_retry_scheduled = True
                QTimer.singleShot(4000, self.init_system_status_bar)
            return
        self._psutil_mod = psutil_mod
        self._psutil_retry_scheduled = False

        self._system_metrics_timer = QTimer(self)
        self._system_metrics_timer.setInterval(2500)
        self._system_metrics_timer.timeout.connect(self.update_system_metrics)
        QTimer.singleShot(400, self.update_system_metrics)
        self._system_metrics_timer.start()
        self.logger.info("[System Status] System metrics timer started")

    def update_system_badge(
        self,
        *,
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

    def update_system_metrics(self) -> None:
        """Update system metrics (CPU, battery, network) in the status bar."""
        if not (self.cpu_label and self.memory_label and self.battery_label and self.network_label):
            self.logger.debug("[System Status] Labels not initialized yet")
            return

        psutil = self._psutil_mod or self._load_psutil_module()
        if not psutil:
            self.logger.debug("[System Status] psutil still missing during metrics update")
            for label in (self.cpu_label, self.memory_label, self.battery_label, self.network_label):
                if label:
                    label.setText("psutil חסר")
                    label.setStyleSheet("font-weight:600; color:#fbbf24; padding:0 8px;")
            return

        payload: Dict[str, object] = {}
        # CPU
        try:
            if not hasattr(self, "_last_cpu_percent") or self._last_cpu_percent is None:
                cpu_usage = psutil.cpu_percent(interval=0.1)
                self._last_cpu_percent = cpu_usage if cpu_usage is not None else 0.0
            else:
                cpu_usage = psutil.cpu_percent(interval=None)
                if cpu_usage is None:
                    cpu_usage = self._last_cpu_percent
                else:
                    self._last_cpu_percent = cpu_usage
            if cpu_usage < 0:
                cpu_usage = 0.0

            cpu_display = f"🧠 {cpu_usage:.0f}%"
            if self.cpu_label:
                self.cpu_label.setText(cpu_display)
                self.cpu_label.setStyleSheet(self._status_label_style(min(cpu_usage / 100.0, 1.0)))
            self.update_system_badge(cpu_text=f"CPU {cpu_usage:.0f}%")
            payload["cpu"] = cpu_usage
        except Exception as exc:
            self.logger.warning("[System Status] CPU metric error: %s", exc, exc_info=True)
            if self.cpu_label:
                self.cpu_label.setText("🧠 --")
                self.cpu_label.setStyleSheet(self._status_label_style(1.0))
            self.update_system_badge(cpu_text="CPU --")

        # Memory
        try:
            memory = psutil.virtual_memory()
            mem_usage = getattr(memory, "percent", None)
            if mem_usage is None:
                raise RuntimeError("virtual_memory.percent unavailable")
            if self.memory_label:
                self.memory_label.setText(f"💾 {mem_usage:.0f}%")
                self.memory_label.setStyleSheet(self._status_label_style(min(mem_usage / 100.0, 1.0)))
            self.update_system_badge(mem_text=f"MEM {mem_usage:.0f}%")
            payload["mem"] = mem_usage
        except Exception as exc:
            self.logger.warning("[System Status] Memory metric error: %s", exc)
            if self.memory_label:
                self.memory_label.setText("💾 --")
                self.memory_label.setStyleSheet(self._status_label_style(1.0))
            self.update_system_badge(mem_text="MEM --")

        # Battery
        try:
            battery = psutil.sensors_battery()
            if self.battery_label:
                if battery:
                    icon = "🔌" if battery.power_plugged else "🔋"
                    percent = battery.percent if battery.percent is not None else 100
                    self.battery_label.setText(f"{icon} {percent:.0f}%")
                    severity = 1 - min(percent / 100.0, 1.0)
                    self.battery_label.setStyleSheet(self._status_label_style(severity))
                    payload["battery"] = percent
                else:
                    self.battery_label.setText("🔌 AC")
                    self.battery_label.setStyleSheet("padding:0 8px; font-weight:600; color:#38bdf8;")
        except Exception as exc:
            self.logger.warning("[System Status] Battery metric error: %s", exc)
            if self.battery_label:
                self.battery_label.setText("🔋 --")
                self.battery_label.setStyleSheet(self._status_label_style(1.0))

        # Network
        try:
            online, latency_ms = self._probe_internet_latency()
            payload["network_online"] = online
            payload["network_latency_ms"] = latency_ms
            if self.network_label:
                if online:
                    self.network_label.setText(f"🌐 {latency_ms:.0f}ms")
                    severity = min(latency_ms / 250.0, 1.0)
                    self.network_label.setStyleSheet(self._status_label_style(severity))
                    self.update_system_badge(net_text=f"NET {latency_ms:.0f}ms")
                else:
                    self.network_label.setText("🌐 ללא רשת")
                    self.network_label.setStyleSheet(self._status_label_style(1.0))
                    self.update_system_badge(net_text="NET offline")
        except Exception as exc:
            self.logger.warning("[System Status] Network metric error: %s", exc)
            if self.network_label:
                self.network_label.setText("🌐 --")
                self.network_label.setStyleSheet(self._status_label_style(1.0))
            self.update_system_badge(net_text="NET --")

        if payload:
            self.stats_updated.emit(payload)

    def ensure_network_ready(self, action: str = "פעולה", dialog_parent: Optional[QWidget] = None) -> bool:
        """
        Lightweight connectivity guard for network-dependent flows.

        Shows the bottom banner in red and optional status message when offline.
        """
        online, _ = self._probe_internet_latency()
        if online:
            return True

        self.logger.warning("[Network] Blocked '%s' – offline", action)
        self.show_network_error_banner()
        if self.status_bar:
            self.status_bar.showMessage("אין חיבור אינטרנט – נסו שוב כשתחזרו לרשת", 6000)
        parent = dialog_parent or (self.parent() if isinstance(self.parent(), QWidget) else None)
        QMessageBox.warning(parent, "אין אינטרנט", f"הפעולה '{action}' דורשת חיבור אינטרנט.\nבדקו את הרשת ונסו שוב.")
        return False

    def show_network_error_banner(self) -> None:
        """Render an explicit offline state in the bottom banner."""
        if self.network_label:
            self.network_label.setText("🌐 No Internet Connection")
            self.network_label.setStyleSheet(self._status_label_style(1.0))
        self.update_system_badge(net_text="NET offline")

    def reset_status_indicators(self) -> None:
        """Return status labels/badge to a neutral state."""
        if self.network_label:
            self.network_label.setText("🌐 בודק...")
            self.network_label.setStyleSheet("font-weight:600; color:#94a3b8; padding:0 8px;")
        self.update_system_badge(net_text="NET --")
        if self.status_bar:
            self.status_bar.clearMessage()

    # Internal helpers ------------------------------------------------
    def _status_label_style(self, severity: float) -> str:
        """Return a color style string based on severity (0=good, 1=bad)."""
        if severity < 0.5:
            color = "#34d399"  # green
        elif severity < 0.8:
            color = "#fbbf24"  # yellow
        else:
            color = "#f87171"  # red
        return f"padding:0 8px; font-weight:600; color:{color};"

    def _load_psutil_module(self):
        """Attempt to import psutil, including common local/venv paths."""
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
        candidates = []
        for base in filter(
            None,
            [
                venv_env,
                project_root / ".venv",
                project_root / "venv",
                exe_path.parent.parent,  # typical <python>/Lib/site-packages
            ],
        ):
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

        try:
            import psutil  # type: ignore
            return psutil
        except Exception as exc:
            self._psutil_last_error = str(exc)
            self.logger.error("[System Status] psutil import final fail: %s", exc, exc_info=True)
            return None

    def _probe_internet_latency(self, timeout: float = 1.5) -> Tuple[bool, float]:
        """Probe internet connectivity and measure latency."""
        try:
            start = time.perf_counter()
            with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
                latency = (time.perf_counter() - start) * 1000
            return True, latency
        except (OSError, TimeoutError) as exc:
            self.logger.debug("[System Status] Network probe failed: %s", exc)
            return False, 0.0
        except Exception as exc:
            self.logger.warning("[System Status] Unexpected network probe error: %s", exc)
            return False, 0.0

