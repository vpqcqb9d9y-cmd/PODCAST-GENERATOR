"""
Voice Lab controller for recording, playback, and cloning flows.

Encapsulates the Voice Lab UI interactions, including recording via
RecordingWorker, preview playback, state transitions, and ElevenLabs cloning.
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import threading

from PyQt6.QtCore import QObject, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton, QWidget

from src.gui.workers import RecordingWorker


class VoiceLabController(QObject):
    """
    Controller for Voice Lab interactions (record, stop, preview, clone).

    Delegates all Voice Lab actions from the main window to keep `app.py`
    focused on orchestration. Uses the main window's widgets and services,
    without altering business logic.
    """

    quota_ready = pyqtSignal(str)
    quota_error = pyqtSignal(str)

    def __init__(
        self,
        *,
        window: QWidget,
        logger: logging.Logger,
        settings,
        voice_lab_service,
        voice_manager,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.logger = logger
        self.settings = settings
        self.voice_lab_service = voice_lab_service
        self.voice_manager = voice_manager

        # Playback resources
        self.voice_playback_player: Optional[QMediaPlayer] = getattr(window, "voice_playback_player", None)
        self.voice_audio_output: Optional[QAudioOutput] = getattr(window, "voice_audio_output", None)

        # Wire async quota updates to the UI thread
        self.quota_ready.connect(self._set_quota_label)
        self.quota_error.connect(self._set_quota_error)

    # Recording -------------------------------------------------------
    def on_record_clicked(self, btn: Optional[QPushButton] = None) -> None:
        """Handle record/stop toggle from the mic button."""
        w = self.window
        if btn is None:
            btn = getattr(w, "sender", lambda: None)()
        if not isinstance(btn, QPushButton):
            return
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np  # type: ignore
            from scipy.io import wavfile  # type: ignore
            _ = (sd, np, wavfile)
        except Exception:
            reply = QMessageBox.question(
                w,
                "נדרשת התקנה",
                "ספריות הקלטה חסרות. האם להתקין אותן כעת? (sounddevice, numpy, scipy)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "sounddevice", "numpy", "scipy"]
                    )
                    QMessageBox.information(
                        w, "התקנה הושלמה", "ספריות ההקלטה הותקנו בהצלחה."
                    )
                except Exception as exc_install:
                    QMessageBox.warning(
                        w,
                        "שגיאת התקנה",
                        f"נכשל בהתקנת ספריות ההקלטה:\n{exc_install}",
                    )
            btn.setChecked(False)
            return

        if btn.isChecked():
            if getattr(w, "_record_thread", None) and w._record_thread.isRunning():
                btn.setChecked(True)
                getattr(w, "voice_lab_status_label", None).setText("הקלטה כבר פעילה...") if hasattr(w, "voice_lab_status_label") else None
                return
            self._set_voice_lab_state("recording")
            clone_btn = getattr(w, "voice_lab_clone_btn", None)
            if clone_btn:
                clone_btn.setEnabled(False)
            w._record_thread = QThread(w)
            w._record_worker = RecordingWorker(duration=60, samplerate=44100)
            w._record_worker.moveToThread(w._record_thread)

            w._record_thread.started.connect(w._record_worker.run)
            w._record_worker.status.connect(getattr(w, "voice_lab_status_label", QLabel()).setText)
            w._record_worker.finished.connect(lambda path, frames: self._on_recording_finished(path, frames, btn))
            w._record_worker.error.connect(lambda msg: self._on_recording_error(msg, btn))
            w._record_worker.finished.connect(w._record_thread.quit)
            w._record_worker.error.connect(w._record_thread.quit)
            w._record_thread.finished.connect(w._record_worker.deleteLater)
            w._record_thread.finished.connect(w._record_thread.deleteLater)
            w._record_thread.finished.connect(self._clear_recording_refs)

            w._record_thread.start()
        else:
            if getattr(w, "_record_thread", None) and w._record_thread.isRunning() and getattr(w, "_record_worker", None):
                getattr(w, "voice_lab_status_label", None).setText("עוצר הקלטה...") if hasattr(w, "voice_lab_status_label") else None
                w._record_worker.request_stop()
            btn.setChecked(False)
            self._set_voice_lab_state("idle")

    def _on_recording_finished(self, path: Path, frames: int, btn: QPushButton) -> None:
        w = self.window
        btn.setChecked(False)
        if path and path.exists() and frames > 0:
            w.voice_lab_file_path = path
            if getattr(w, "voice_lab_file_label", None):
                w.voice_lab_file_label.setText(f"נשמר: {path.name}")
            if getattr(w, "voice_lab_status_label", None):
                w.voice_lab_status_label.setText("Recording saved: temp_recording.wav")
            clone_btn = getattr(w, "voice_lab_clone_btn", None)
            if clone_btn:
                clone_btn.setEnabled(True)
            self._set_voice_lab_state("review")
        else:
            if getattr(w, "voice_lab_status_label", None):
                w.voice_lab_status_label.setText("הקלטה הופסקה.")
            clone_btn = getattr(w, "voice_lab_clone_btn", None)
            if clone_btn:
                clone_btn.setEnabled(False)
            self._set_voice_lab_state("idle")
        self._clear_recording_refs()

    def _on_recording_error(self, message: str, btn: QPushButton) -> None:
        w = self.window
        btn.setChecked(False)
        if getattr(w, "voice_lab_status_label", None):
            w.voice_lab_status_label.setText(f"שגיאת הקלטה: {message}")
        clone_btn = getattr(w, "voice_lab_clone_btn", None)
        if clone_btn:
            clone_btn.setEnabled(False)
        self._clear_recording_refs()
        self._set_voice_lab_state("idle")

    def _clear_recording_refs(self) -> None:
        w = self.window
        if getattr(w, "_record_thread", None) and w._record_thread.isRunning():
            w._record_thread.quit()
            w._record_thread.wait(1500)
        w._record_thread = None
        w._record_worker = None

    def stop_voice_recording(self) -> None:
        """Stop recording safely from the UI (Stop button)."""
        w = self.window
        if getattr(w, "_record_worker", None):
            if getattr(w, "voice_lab_status_label", None):
                w.voice_lab_status_label.setText("עוצר הקלטה...")
            w._record_worker.request_stop()
        btn = getattr(w, "voice_lab_mic_btn", None)
        if btn and btn.isChecked():
            btn.setChecked(False)

    # File management -------------------------------------------------
    def reset_voice_lab_file(self) -> None:
        """Clear current voice sample and disable clone until a new file is selected."""
        w = self.window
        if getattr(w, "voice_lab_file_path", None) and w.voice_lab_file_path.exists():
            try:
                w.voice_lab_file_path.unlink()
            except Exception:
                pass
        w.voice_lab_file_path = None
        if getattr(w, "voice_lab_file_label", None):
            w.voice_lab_file_label.setText("לא נבחר קובץ")
        if getattr(w, "voice_lab_status_label", None):
            w.voice_lab_status_label.setText("בחר/י קובץ או הקלט מחדש.")
        clone_btn = getattr(w, "voice_lab_clone_btn", None)
        if clone_btn:
            clone_btn.setEnabled(False)
        self._set_voice_lab_state("idle")
        self.stop_voice_playback()

    def select_voice_sample(self) -> None:
        """Open file dialog to choose an audio sample."""
        w = self.window
        file_path, _ = QFileDialog.getOpenFileName(
            w,
            "בחר קובץ קול (עד 60 שניות)",
            str(self.settings.output_base_dir),
            "Audio Files (*.wav *.mp3)",
        )
        if not file_path:
            return
        w.voice_lab_file_path = Path(file_path)
        if getattr(w, "voice_lab_file_label", None):
            w.voice_lab_file_label.setText(f"נבחר: {w.voice_lab_file_path.name}")
        if getattr(w, "voice_lab_status_label", None):
            w.voice_lab_status_label.setText("מוכן לשיכפול קולות.")
        clone_btn = getattr(w, "voice_lab_clone_btn", None)
        if clone_btn:
            clone_btn.setEnabled(True)
        self._set_voice_lab_state("review")

    # Playback --------------------------------------------------------
    def play_voice_preview(self) -> None:
        """Open the recorded/selected file in the default media player."""
        w = self.window
        if not getattr(w, "voice_lab_file_path", None) or not w.voice_lab_file_path.exists():
            QMessageBox.information(w, "קובץ חסר", "אין קובץ להשמעה כרגע.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(w.voice_lab_file_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(w.voice_lab_file_path)])
            else:
                subprocess.Popen(["xdg-open", str(w.voice_lab_file_path)])
        except Exception as exc:
            QMessageBox.warning(w, "השמעה נכשלה", f"לא ניתן להשמיע את הקובץ:\n{exc}")

    def toggle_voice_preview(self) -> None:
        """Play/pause the recorded file inline using QMediaPlayer."""
        w = self.window
        if not getattr(w, "voice_lab_file_path", None) or not w.voice_lab_file_path.exists():
            QMessageBox.information(w, "קובץ חסר", "אין קובץ להשמעה כרגע.")
            return
        try:
            if self.voice_playback_player is None:
                self.voice_playback_player = QMediaPlayer()
                self.voice_audio_output = QAudioOutput()
                self.voice_playback_player.setAudioOutput(self.voice_audio_output)
                self.voice_playback_player.mediaStatusChanged.connect(
                    lambda _: self._update_voice_play_button_icon()
                )
                setattr(w, "voice_playback_player", self.voice_playback_player)
                setattr(w, "voice_audio_output", self.voice_audio_output)
            self.voice_playback_player.setSource(QUrl.fromLocalFile(str(w.voice_lab_file_path)))
            if self.voice_playback_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.voice_playback_player.pause()
            else:
                self.voice_playback_player.play()
            self._update_voice_play_button_icon()
        except Exception as exc:
            QMessageBox.warning(w, "השמעה נכשלה", f"לא ניתן להשמיע את הקובץ:\n{exc}")

    def stop_voice_playback(self) -> None:
        """Stop inline playback if active."""
        if self.voice_playback_player and self.voice_playback_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            try:
                self.voice_playback_player.stop()
            except Exception:
                pass
        self._update_voice_play_button_icon(reset=True)

    def _update_voice_play_button_icon(self, reset: bool = False) -> None:
        btn = getattr(self.window, "voice_lab_play_btn", None)
        if not btn:
            return
        if reset or not self.voice_playback_player or self.voice_playback_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            btn.setText("Play Preview")
        else:
            btn.setText("Pause")

    # State & visuals -------------------------------------------------
    def _set_voice_lab_state(self, state: str) -> None:
        """State machine: idle -> recording -> review."""
        w = self.window
        w.voice_lab_state = state
        timer = getattr(w, "voice_lab_timer", None)
        record_controls = getattr(w, "voice_lab_record_controls", None)
        review_controls = getattr(w, "voice_lab_review_controls", None)
        trash_btn = getattr(w, "voice_lab_trash_btn", None)
        mic_btn = getattr(w, "voice_lab_mic_btn", None)
        stop_btn = getattr(w, "voice_lab_stop_btn", None)
        timer_label = getattr(w, "voice_lab_timer_label", None)

        if state == "idle":
            if timer and timer.isActive():
                timer.stop()
            w.voice_lab_record_start = None
            self._stop_voice_visualizer()
            if timer_label:
                timer_label.setText("00:00")
                timer_label.setVisible(False)
            if record_controls:
                record_controls.setVisible(True)
            if review_controls:
                review_controls.setVisible(False)
            if trash_btn:
                trash_btn.setVisible(True)
            if mic_btn:
                mic_btn.setChecked(False)
                mic_btn.setVisible(True)
                mic_btn.setText("Record")
                mic_btn.setStyleSheet("background-color: #25D366;")
            if stop_btn:
                stop_btn.setEnabled(False)
            self.stop_voice_playback()
        elif state == "recording":
            w.voice_lab_record_start = time.time()
            if timer:
                timer.start(1000)
                timer_label.setVisible(True) if timer_label else None
            if record_controls:
                record_controls.setVisible(True)
            if review_controls:
                review_controls.setVisible(False)
            self._start_voice_visualizer()
            if trash_btn:
                trash_btn.setVisible(True)
            if mic_btn:
                mic_btn.setVisible(True)
                mic_btn.setChecked(True)
                mic_btn.setText("Recording...")
                mic_btn.setStyleSheet("background-color: #ef4444;")
            if stop_btn:
                stop_btn.setEnabled(True)
        elif state == "review":
            if timer and timer.isActive():
                timer.stop()
            if timer_label:
                timer_label.setVisible(False)
            if record_controls:
                record_controls.setVisible(False)
            if review_controls:
                review_controls.setVisible(True)
            self._stop_voice_visualizer()
            if trash_btn:
                trash_btn.setVisible(True)
            if mic_btn:
                mic_btn.setChecked(False)
                mic_btn.setVisible(False)
            if stop_btn:
                stop_btn.setEnabled(False)
        self._update_voice_play_button_icon(reset=True)

    def tick_voice_timer(self) -> None:
        w = self.window
        timer_label = getattr(w, "voice_lab_timer_label", None)
        if not getattr(w, "voice_lab_record_start", None):
            if timer_label:
                timer_label.setText("00:00")
            return
        elapsed = int(time.time() - w.voice_lab_record_start)
        mins, secs = divmod(elapsed, 60)
        if timer_label:
            timer_label.setText(f"{mins:02d}:{secs:02d}")

    def _start_voice_visualizer(self) -> None:
        timer = getattr(self.window, "voice_lab_visual_timer", None)
        if not timer:
            return
        self._tick_voice_visualizer()
        timer.start()

    def _stop_voice_visualizer(self) -> None:
        w = self.window
        timer = getattr(w, "voice_lab_visual_timer", None)
        if timer and timer.isActive():
            timer.stop()
        bars = getattr(w, "voice_lab_visual_bars", [])
        for bar in bars:
            bar.setFixedHeight(8)

    def _tick_voice_visualizer(self) -> None:
        w = self.window
        bars = getattr(w, "voice_lab_visual_bars", [])
        if not bars:
            return
        active = getattr(w, "voice_lab_state", "") == "recording"
        for bar in bars:
            height = random.randint(10, 40) if active else 8
            bar.setFixedHeight(height)

    # Quota & cloning -------------------------------------------------
    def refresh_voice_quota(self) -> None:
        """Start a background fetch to avoid blocking the UI thread."""
        self.refresh_voice_quota_async()

    def refresh_voice_quota_async(self) -> None:
        w = self.window
        if not getattr(w, "voice_lab_quota_label", None) or not self.voice_lab_service:
            return
        w.voice_lab_quota_label.setText("בודק מכסה...")

        def _worker() -> None:
            try:
                quota = self.voice_lab_service.get_subscription_quota()
                remaining = quota["character_limit"] - quota["character_count"]
                remaining = max(0, remaining)
                text = f"נותרו {remaining:,} / {quota['character_limit']:,} תווים החודש"
                self.quota_ready.emit(text)
            except Exception as exc:  # pragma: no cover - UI only
                self.quota_error.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_quota_label(self, text: str) -> None:
        label = getattr(self.window, "voice_lab_quota_label", None)
        if label:
            label.setText(text)

    def _set_quota_error(self, message: str) -> None:
        label = getattr(self.window, "voice_lab_quota_label", None)
        if label:
            label.setText(f"שגיאה בשליפת מכסה: {message}")

    def handle_clone_voice(self) -> None:
        w = self.window
        if not self.voice_lab_service or not getattr(self.settings, "elevenlabs_api_key", ""):
            QMessageBox.warning(
                w,
                "API Key חסר",
                "נדרש ELEVENLABS_API_KEY כדי לשכפל קול.",
            )
            return
        if not getattr(w, "voice_lab_file_path", None) or not w.voice_lab_file_path.exists():
            QMessageBox.warning(
                w,
                "קובץ חסר",
                "בחר/י קובץ WAV או MP3 (עד 60 שניות) לפני השיכפול.",
            )
            return

        clone_btn = getattr(w, "voice_lab_clone_btn", None)
        if clone_btn:
            clone_btn.setEnabled(False)
        try:
            voice_id = self.voice_lab_service.clone_instant_voice(
                w.voice_lab_file_path, voice_name="Custom Voice"
            )
            self.voice_lab_service.save_custom_voice_profile(voice_id)
            refresh_profiles = getattr(w, "_refresh_voice_profiles_combo", None)
            if callable(refresh_profiles):
                refresh_profiles(select_profile="Custom")
            if getattr(w, "voice_lab_status_label", None):
                w.voice_lab_status_label.setText(
                    f"✅ קול שוכפל ונשמר כפרופיל 'Custom' (ID: {voice_id[:10]}...)"
                )
            QMessageBox.information(
                w,
                "Voice Cloned",
                "הקול שוכפל בהצלחה ונשמר כפרופיל 'Custom' ב-voice_profiles.json.",
            )
        except Exception as exc:
            if getattr(w, "voice_lab_status_label", None):
                w.voice_lab_status_label.setText(f"❌ שגיאה: {exc}")
            QMessageBox.critical(w, "כישלון בשיכפול קול", str(exc))
        finally:
            if clone_btn:
                clone_btn.setEnabled(True)
            self.refresh_voice_quota()

