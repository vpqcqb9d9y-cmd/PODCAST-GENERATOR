"""
M.B.S Studio - Background Workers
==================================

QThread-based worker classes for handling long-running operations
without blocking the main UI thread.

Workers:
    - PipelineWorker: Executes the podcast generation pipeline with heartbeat monitoring
    - ChatWorker: Handles AI chat interactions
    - MetadataSeedWorker: Seeds metadata from transcript content

Author: M.B.S Studio
Version: 2.0.0 (Enhanced logging)
"""

from __future__ import annotations

import json
import logging
import os
import select
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from src.metadata import MetadataChatSession
from src.utils.visual_metadata_builder import build_visual_metadata_locally

# Module logger
_logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
DEFAULT_HEARTBEAT_INTERVAL = 5.0  # Check every 5 seconds
DEFAULT_STALL_TIMEOUT = 300.0  # 5 minutes without output = stall
DEFAULT_MAX_SLEEP_RECOVERY_TIME = 60.0  # 1 minute grace period after sleep


class PipelineWorker(QThread):
    """
    Background worker for executing the podcast generation pipeline.
    
    Runs the pipeline as a subprocess and streams output to the GUI
    in real-time. Includes heartbeat monitoring to detect stalls
    caused by system sleep or other interruptions.
    
    Signals:
        output (str): Emitted for each line of pipeline output
        finished (int): Emitted when pipeline completes with exit code
        heartbeat (float): Emitted periodically with seconds since last output
        stall_detected (float): Emitted when output stalls beyond threshold
        progress_state (dict): Emitted with current progress state for persistence
    
    Example:
        >>> worker = PipelineWorker(["python", "-m", "scripts.generate_podcast", ...])
        >>> worker.output.connect(self._append_log)
        >>> worker.finished.connect(self._run_finished)
        >>> worker.stall_detected.connect(self._handle_stall)
        >>> worker.start()
    """
    
    output = pyqtSignal(str)
    """Signal emitted for each line of stdout/stderr from the pipeline."""
    
    finished = pyqtSignal(int)
    """Signal emitted when pipeline execution completes (exit code)."""
    
    heartbeat = pyqtSignal(float)
    """Signal emitted with seconds since last output (for UI progress indication)."""
    
    stall_detected = pyqtSignal(float)
    """Signal emitted when pipeline appears stalled (seconds without output)."""
    
    progress_state = pyqtSignal(object)
    """Signal emitted with progress state dict for persistence/recovery."""
    
    sleep_recovery = pyqtSignal()
    """Signal emitted when recovering from system sleep."""

    def __init__(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        stall_timeout: float = DEFAULT_STALL_TIMEOUT,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        progress_file: Optional[Path] = None,
    ) -> None:
        """
        Initialize the pipeline worker.
        
        Args:
            command: Command and arguments to execute
            cwd: Working directory for the subprocess (optional)
            stall_timeout: Seconds without output before stall detection (default: 300)
            heartbeat_interval: Seconds between heartbeat checks (default: 5)
            progress_file: Path to save progress state for recovery (optional)
        """
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.stall_timeout = stall_timeout
        self.heartbeat_interval = heartbeat_interval
        self.progress_file = progress_file
        
        self._process: Optional[subprocess.Popen[str]] = None
        self._last_output_time: float = 0.0
        self._start_time: float = 0.0
        self._last_heartbeat_check: float = 0.0
        self._current_stage: str = "initializing"
        self._lines_received: int = 0
        self._is_terminated: bool = False
        self._stall_notified: bool = False
        
        _logger.info("[PipelineWorker.__init__] Initialized with command: %s", 
                    " ".join(command[:3]) + "..." if len(command) > 3 else " ".join(command))
        _logger.debug("[PipelineWorker.__init__] cwd=%s, stall_timeout=%s, heartbeat=%s",
                     cwd, stall_timeout, heartbeat_interval)

    def run(self) -> None:
        """
        Execute the pipeline command in a subprocess with heartbeat monitoring.
        
        Streams stdout line by line to the output signal.
        Monitors for stalls and emits heartbeat signals periodically.
        Captures and emits any exceptions as error messages.
        """
        self._start_time = time.time()
        self._last_output_time = self._start_time
        self._last_heartbeat_check = self._start_time
        self._stall_notified = False
        
        _logger.info("[PipelineWorker.run] Starting pipeline execution")
        _logger.debug("[PipelineWorker.run] Full command: %s", " ".join(self.command))
        
        try:
            # Save initial progress state
            self._save_progress_state("starting")
            
            _logger.debug("[PipelineWorker.run] Spawning subprocess...")
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered for real-time output
            )
            _logger.info("[PipelineWorker.run] Subprocess started with PID: %s", self._process.pid)
            
            assert self._process.stdout is not None
            
            # Use non-blocking read with timeout for heartbeat monitoring
            while True:
                if self._is_terminated:
                    _logger.info("[PipelineWorker.run] Termination requested, exiting loop")
                    break
                    
                # Check if process has finished
                poll_result = self._process.poll()
                if poll_result is not None:
                    _logger.debug("[PipelineWorker.run] Process finished with code %s", poll_result)
                    # Process finished, read any remaining output
                    remaining = self._process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            self._handle_output_line(line)
                    break
                
                # Try to read a line with a short timeout
                line = self._read_line_with_timeout(self._process.stdout, timeout=1.0)
                
                if line is not None:
                    self._handle_output_line(line.rstrip())
                
                # Perform heartbeat check
                self._check_heartbeat()
            
            return_code = self._process.wait() if self._process else -1
            elapsed = time.time() - self._start_time
            _logger.info("[PipelineWorker.run] Pipeline completed: code=%d, elapsed=%.1fs, lines=%d",
                        return_code, elapsed, self._lines_received)
            
        except Exception as exc:
            _logger.error("[PipelineWorker.run] Pipeline failed with exception: %s\n%s", 
                         exc, traceback.format_exc())
            self.output.emit(f"[ERROR] {exc}")
            return_code = -1
            self._save_progress_state("error", error=str(exc))
        
        # Save final state
        self._save_progress_state("completed" if return_code == 0 else "failed")
        self.finished.emit(return_code)

    def _read_line_with_timeout(self, stream, timeout: float) -> Optional[str]:
        """
        Read a line from stream with timeout support.
        
        On Windows, uses a simple polling approach.
        On Unix, uses select for efficient waiting.
        
        Args:
            stream: File stream to read from
            timeout: Maximum seconds to wait
            
        Returns:
            Line string if available, None if timeout
        """
        if os.name == 'nt':
            # Windows: Simple polling with sleep
            start = time.time()
            while time.time() - start < timeout:
                # Check if there's data available (Windows doesn't support select on pipes)
                try:
                    line = stream.readline()
                    if line:
                        return line
                    # Small sleep to avoid busy-waiting
                    time.sleep(0.1)
                except Exception:
                    break
            return None
        else:
            # Unix: Use select for efficient waiting
            ready, _, _ = select.select([stream], [], [], timeout)
            if ready:
                return stream.readline()
            return None

    def _handle_output_line(self, line: str) -> None:
        """Process and emit an output line, updating state."""
        current_time = time.time()
        
        # Check for sleep recovery (large time gap)
        time_since_last = current_time - self._last_output_time
        if time_since_last > DEFAULT_MAX_SLEEP_RECOVERY_TIME and self._lines_received > 0:
            self.output.emit(f"[INFO] Recovered from pause ({time_since_last:.1f}s gap detected)")
            self.sleep_recovery.emit()
        
        self._last_output_time = current_time
        self._lines_received += 1
        self._stall_notified = False  # Reset stall notification
        
        # Detect pipeline stage from output
        self._detect_stage(line)
        
        # Emit the output line
        self.output.emit(line)
        
        # Periodically save progress
        if self._lines_received % 10 == 0:
            self._save_progress_state("running")

    def _check_heartbeat(self) -> None:
        """Check heartbeat and emit signals for monitoring."""
        current_time = time.time()
        
        # Only check at heartbeat intervals
        if current_time - self._last_heartbeat_check < self.heartbeat_interval:
            return
        
        self._last_heartbeat_check = current_time
        seconds_since_output = current_time - self._last_output_time
        
        # Emit heartbeat signal
        self.heartbeat.emit(seconds_since_output)
        
        # Check for stall
        if seconds_since_output > self.stall_timeout and not self._stall_notified:
            self._stall_notified = True
            self.stall_detected.emit(seconds_since_output)
            self.output.emit(
                f"[WARNING] No output for {seconds_since_output:.0f}s. "
                "Pipeline may be stalled or system was in sleep mode."
            )

    def _detect_stage(self, line: str) -> None:
        """Detect current pipeline stage from output line."""
        stage_keywords = {
            "Pipeline execution started": "initializing",
            "Starting dialogue generation": "dialogue",
            "Starting speech synthesis": "tts",
            "Starting audio stitching": "audio",
            "Starting video composition": "video",
            "Pipeline execution finished": "completed",
        }
        
        for keyword, stage in stage_keywords.items():
            if keyword in line:
                self._current_stage = stage
                break

    def _save_progress_state(self, status: str, error: str = "") -> None:
        """Save current progress state for recovery."""
        state = {
            "status": status,
            "stage": self._current_stage,
            "lines_received": self._lines_received,
            "elapsed_seconds": time.time() - self._start_time,
            "last_output_time": self._last_output_time,
            "timestamp": datetime.now().isoformat(),
            "command": self.command,
            "error": error,
        }
        
        # Emit progress state signal
        self.progress_state.emit(state)
        
        # Save to file if configured
        if self.progress_file:
            try:
                self.progress_file.parent.mkdir(parents=True, exist_ok=True)
                self.progress_file.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            except Exception:
                pass  # Don't fail on progress save errors

    def terminate_process(self) -> None:
        """
        Terminate the running subprocess if active.
        
        Useful for canceling long-running pipeline operations.
        """
        self._is_terminated = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._save_progress_state("terminated")

    def get_elapsed_time(self) -> float:
        """Get elapsed time since pipeline started."""
        if self._start_time > 0:
            return time.time() - self._start_time
        return 0.0

    def get_current_stage(self) -> str:
        """Get the current pipeline stage."""
        return self._current_stage

    @staticmethod
    def load_progress_state(progress_file: Path) -> Optional[Dict]:
        """
        Load saved progress state from file.
        
        Args:
            progress_file: Path to progress state file
            
        Returns:
            Progress state dict if file exists and is valid, None otherwise
        """
        if not progress_file.exists():
            return None
        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


class ChatWorker(QThread):
    """
    Background worker for AI chat interactions.
    
    Handles communication with the MetadataChatSession to send
    prompts and receive responses without blocking the UI.
    
    Signals:
        result (str, object): Emitted with response text and metadata dict
        error (str): Emitted when an error occurs during chat
    
    Example:
        >>> worker = ChatWorker(session, "summarize this lesson", "gemini")
        >>> worker.result.connect(self._handle_chat_result)
        >>> worker.error.connect(self._handle_chat_error)
        >>> worker.start()
    """
    
    result = pyqtSignal(str, object)
    """Signal emitted with (response_text, metadata_dict) on success."""
    
    error = pyqtSignal(str)
    """Signal emitted with error message on failure."""

    def __init__(
        self,
        session: MetadataChatSession,
        prompt: str,
        model_choice: str,
    ) -> None:
        """
        Initialize the chat worker.
        
        Args:
            session: Active metadata chat session
            prompt: User's prompt text
            model_choice: AI model to use ('gemini' or 'azure')
        """
        super().__init__()
        self.session = session
        self.prompt = prompt
        self.model_choice = model_choice
        self._start_time: float = 0.0
        
        _logger.info("[ChatWorker.__init__] Initialized with model=%s, prompt_length=%d",
                    model_choice, len(prompt))

    def run(self) -> None:
        """
        Send the prompt to the AI model and emit the response.
        
        On success, emits result signal with response and metadata.
        On failure, emits error signal with exception message.
        """
        self._start_time = time.time()
        _logger.info("[ChatWorker.run] Sending request to %s...", self.model_choice)
        
        try:
            response, metadata = self.session.send(
                self.prompt,
                preferred_model=self.model_choice,
            )
            elapsed = time.time() - self._start_time
            _logger.info("[ChatWorker.run] Received response in %.2fs (%d chars)",
                        elapsed, len(response) if response else 0)
            _logger.debug("[ChatWorker.run] Metadata keys: %s", 
                         list(metadata.keys()) if metadata else [])
            self.result.emit(response, metadata)
            
        except Exception as exc:
            elapsed = time.time() - self._start_time
            _logger.error("[ChatWorker.run] Request failed after %.2fs: %s\n%s",
                         elapsed, exc, traceback.format_exc())
            self.error.emit(str(exc))


class MetadataSeedWorker(QThread):
    """
    Background worker for seeding metadata from transcript.
    
    Analyzes transcript content to automatically generate initial
    metadata (topic, key concepts, summary, etc.) for a new project.
    
    Signals:
        result (object): Emitted with generated metadata dict on success
        error (str): Emitted when seeding fails
    
    Example:
        >>> worker = MetadataSeedWorker(session, transcript_text)
        >>> worker.result.connect(self._handle_seed_result)
        >>> worker.error.connect(self._handle_seed_error)
        >>> worker.start()
    """
    
    result = pyqtSignal(object)
    """Signal emitted with metadata dict on successful seeding."""
    
    error = pyqtSignal(str)
    """Signal emitted with error message on seeding failure."""

    def __init__(
        self,
        session: MetadataChatSession,
        transcript_text: str,
    ) -> None:
        """
        Initialize the metadata seed worker.
        
        Args:
            session: Active metadata chat session
            transcript_text: Raw transcript text to analyze
        """
        super().__init__()
        self.session = session
        self.transcript_text = transcript_text
        self._start_time: float = 0.0
        
        _logger.info("[MetadataSeedWorker.__init__] Initialized with transcript length=%d",
                    len(transcript_text))

    def run(self) -> None:
        """
        Analyze transcript and generate initial metadata.
        
        Uses the chat session's bootstrap_from_transcript method
        to extract key information from the transcript text.
        """
        self._start_time = time.time()
        _logger.info("[MetadataSeedWorker.run] Starting metadata seeding...")
        
        try:
            payload = self.session.bootstrap_from_transcript(self.transcript_text)
            elapsed = time.time() - self._start_time
            
            if payload:
                topic = payload.get("assistant", "")[:50] if isinstance(payload, dict) else ""
                _logger.info("[MetadataSeedWorker.run] Seeding completed in %.2fs: %s...",
                            elapsed, topic)
            else:
                _logger.warning("[MetadataSeedWorker.run] Seeding returned empty payload after %.2fs",
                               elapsed)
                
            self.result.emit(payload or {})
            
        except Exception as exc:
            elapsed = time.time() - self._start_time
            _logger.error("[MetadataSeedWorker.run] Seeding failed after %.2fs: %s\n%s",
                         elapsed, exc, traceback.format_exc())
            self.error.emit(str(exc))


class VisualMetadataWorker(QThread):
    """
    Background worker for generating detailed visual metadata.
    
    Uses the AI to create professional prompts for images and videos,
    including styles, moods, color palettes, and contextual meanings.
    
    Signals:
        finished (dict): Emitted with generated visual metadata dict on success
        error (str): Emitted when generation fails
    
    Example:
        >>> worker = VisualMetadataWorker(session, transcript_text, 10)
        >>> worker.finished.connect(self._on_visual_metadata_complete)
        >>> worker.error.connect(self._on_visual_metadata_error)
        >>> worker.start()
    """
    
    finished = pyqtSignal(object)
    """Signal emitted with visual metadata dict on successful generation."""
    
    error = pyqtSignal(str)
    """Signal emitted with error message on generation failure."""

    def __init__(
        self,
        session: MetadataChatSession,
        transcript_text: str,
        image_count: int = 10,
        metadata_snapshot: Optional[Dict[str, object]] = None,
        dialogue_snapshot: Optional[Dict[str, object]] = None,
    ) -> None:
        """
        Initialize the visual metadata worker.
        
        Args:
            session: Active metadata chat session with basic metadata
            transcript_text: Raw transcript text to analyze
            image_count: Number of images to generate metadata for
        """
        super().__init__()
        self.session = session
        self.transcript_text = transcript_text
        self.image_count = image_count
        self.metadata_snapshot = metadata_snapshot or {}
        self.dialogue_snapshot = dialogue_snapshot or {}
        self._start_time: float = 0.0
        
        _logger.info("[VisualMetadataWorker.__init__] Initialized with transcript length=%d, image_count=%d",
                    len(transcript_text), image_count)

    def run(self) -> None:
        """
        Generate detailed visual metadata using AI.
        
        Creates prompts for images and video with professional specifications
        including styles, moods, color palettes, and contextual meanings.
        """
        self._start_time = time.time()
        _logger.info("[VisualMetadataWorker.run] Starting visual metadata generation...")
        
        fallback_reason: Optional[str] = None
        visual_metadata: Dict[str, object] = {}
        try:
            visual_metadata = self.session.generate_visual_metadata(
                transcript_text=self.transcript_text,
                image_count=self.image_count,
                preferred_model="gemini",
            )
            elapsed = time.time() - self._start_time
            num_images = len(visual_metadata.get("images", []))
            has_video = bool(visual_metadata.get("video", {}).get("prompt"))
            _logger.info(
                "[VisualMetadataWorker.run] Generation completed in %.2fs: %d images, video=%s",
                elapsed,
                num_images,
                has_video,
            )
        except Exception as exc:
            elapsed = time.time() - self._start_time
            fallback_reason = f"AI generation failed after {elapsed:.2f}s: {exc}"
            _logger.error(
                "[VisualMetadataWorker.run] Generation failed after %.2fs: %s\n%s",
                elapsed,
                exc,
                traceback.format_exc(),
            )
            visual_metadata = {}

        if not visual_metadata.get("images"):
            if not fallback_reason:
                fallback_reason = "AI returned empty or invalid payload"
            _logger.warning(
                "[VisualMetadataWorker.run] Falling back to local visual metadata builder (%s)",
                fallback_reason,
            )
            try:
                visual_metadata = build_visual_metadata_locally(
                    metadata=self.metadata_snapshot or {},
                    dialogue_json=self.dialogue_snapshot or {},
                    transcript_text=self.transcript_text,
                    image_count=self.image_count,
                    include_video=True,
                )
                visual_metadata.setdefault("_generation_source", "local_fallback")
                elapsed = time.time() - self._start_time
                _logger.info(
                    "[VisualMetadataWorker.run] Local fallback produced %d images (%.2fs).",
                    len(visual_metadata.get("images", [])),
                    elapsed,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                _logger.error(
                    "[VisualMetadataWorker.run] Local fallback failed: %s\n%s",
                    exc,
                    traceback.format_exc(),
                )
                self.error.emit(str(exc))
                return

        self.finished.emit(visual_metadata)


class RecordingWorker(QObject):
    """
    Offloads 60s microphone recording to a worker thread so the UI stays responsive.
    Emits status updates and completion/error signals for the Voice Lab flow.
    """

    status = pyqtSignal(str)
    finished = pyqtSignal(Path, int)
    error = pyqtSignal(str)

    def __init__(self, duration: int = 60, samplerate: int = 44100, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.duration = duration
        self.samplerate = samplerate
        self._stop_requested = False

    def request_stop(self) -> None:
        """Signal the worker to stop recording gracefully."""
        self._stop_requested = True
        try:
            import sounddevice as sd  # type: ignore
            sd.stop()
        except Exception:
            pass

    def run(self) -> None:
        """Capture audio for the configured duration and emit status/signals."""
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np  # type: ignore
            from scipy.io import wavfile  # type: ignore
        except Exception as exc:
            self.error.emit(f"Missing recording dependencies: {exc}")
            return

        try:
            self.status.emit("מקליט... לחצו שוב להפסקה.")
            frames = int(self.duration * self.samplerate)
            data = sd.rec(frames, samplerate=self.samplerate, channels=1, dtype="float32")
            sd.wait()

            if self._stop_requested:
                self.status.emit("הקלטה הופסקה.")
                self.finished.emit(Path(), 0)
                return

            temp_path = Path("temp_recording.wav")
            wavfile.write(temp_path, self.samplerate, (data * 32767).astype(np.int16))
            self.status.emit("Recording saved: temp_recording.wav")
            self.finished.emit(temp_path, len(data))
        except Exception as exc:
            self.error.emit(str(exc))
