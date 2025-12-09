"""
Tests for GUI Workers module.

Tests cover PipelineWorker heartbeat, stall detection, and sleep recovery.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch, Mock

import pytest


class TestPipelineWorkerHeartbeat:
    """Tests for PipelineWorker heartbeat mechanism."""
    
    def test_worker_initialization(self):
        """Test worker initializes with correct default values."""
        from src.gui.workers import PipelineWorker, DEFAULT_STALL_TIMEOUT, DEFAULT_HEARTBEAT_INTERVAL
        
        command = ["python", "-c", "print('test')"]
        worker = PipelineWorker(command)
        
        assert worker.command == command
        assert worker.stall_timeout == DEFAULT_STALL_TIMEOUT
        assert worker.heartbeat_interval == DEFAULT_HEARTBEAT_INTERVAL
        assert worker._current_stage == "initializing"
    
    def test_worker_custom_timeout(self):
        """Test worker accepts custom timeout values."""
        from src.gui.workers import PipelineWorker
        
        command = ["python", "-c", "print('test')"]
        worker = PipelineWorker(
            command,
            stall_timeout=600.0,
            heartbeat_interval=10.0
        )
        
        assert worker.stall_timeout == 600.0
        assert worker.heartbeat_interval == 10.0
    
    def test_elapsed_time_tracking(self):
        """Test elapsed time is tracked correctly."""
        from src.gui.workers import PipelineWorker
        
        command = ["python", "-c", "print('test')"]
        worker = PipelineWorker(command)
        
        # Before running, elapsed time should be 0
        assert worker.get_elapsed_time() == 0.0
        
        # Simulate starting
        worker._start_time = time.time() - 10.0  # 10 seconds ago
        
        elapsed = worker.get_elapsed_time()
        assert 9.0 < elapsed < 11.0  # Allow some tolerance


class TestStageDetection:
    """Tests for pipeline stage detection."""
    
    def test_detect_dialogue_stage(self):
        """Test detection of dialogue generation stage."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        
        worker._detect_stage("Starting dialogue generation")
        assert worker.get_current_stage() == "dialogue"
    
    def test_detect_tts_stage(self):
        """Test detection of TTS stage."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        
        worker._detect_stage("Starting speech synthesis")
        assert worker.get_current_stage() == "tts"
    
    def test_detect_video_stage(self):
        """Test detection of video composition stage."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        
        worker._detect_stage("Starting video composition")
        assert worker.get_current_stage() == "video"
    
    def test_detect_completed_stage(self):
        """Test detection of completed stage."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        
        worker._detect_stage("Pipeline execution finished")
        assert worker.get_current_stage() == "completed"
    
    def test_unrelated_text_no_stage_change(self):
        """Test that unrelated text doesn't change stage."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        initial_stage = worker.get_current_stage()
        
        worker._detect_stage("Some random log message")
        assert worker.get_current_stage() == initial_stage


class TestProgressStatePersistence:
    """Tests for progress state saving and loading."""
    
    def test_save_progress_state(self):
        """Test saving progress state to file."""
        from src.gui.workers import PipelineWorker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_file = Path(tmpdir) / "progress.json"
            
            worker = PipelineWorker(
                ["python", "-c", "pass"],
                progress_file=progress_file
            )
            
            worker._start_time = time.time()
            worker._current_stage = "dialogue"
            worker._lines_received = 42
            
            worker._save_progress_state("running")
            
            # File should exist
            assert progress_file.exists()
            
            # Content should be valid JSON with expected fields
            content = json.loads(progress_file.read_text())
            assert content["status"] == "running"
            assert content["stage"] == "dialogue"
            assert content["lines_received"] == 42
    
    def test_load_progress_state(self):
        """Test loading progress state from file."""
        from src.gui.workers import PipelineWorker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_file = Path(tmpdir) / "progress.json"
            
            # Create a test progress file
            test_state = {
                "status": "running",
                "stage": "tts",
                "lines_received": 100,
                "elapsed_seconds": 45.5,
            }
            progress_file.write_text(json.dumps(test_state))
            
            # Load and verify
            loaded = PipelineWorker.load_progress_state(progress_file)
            
            assert loaded is not None
            assert loaded["status"] == "running"
            assert loaded["stage"] == "tts"
            assert loaded["lines_received"] == 100
    
    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file returns None."""
        from src.gui.workers import PipelineWorker
        
        result = PipelineWorker.load_progress_state(Path("/nonexistent/path.json"))
        assert result is None
    
    def test_load_invalid_json(self):
        """Test loading invalid JSON returns None."""
        from src.gui.workers import PipelineWorker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_file = Path(tmpdir) / "progress.json"
            progress_file.write_text("not valid json {{{")
            
            result = PipelineWorker.load_progress_state(progress_file)
            assert result is None


class TestWorkerTermination:
    """Tests for worker termination."""
    
    def test_terminate_sets_flag(self):
        """Test that terminate_process sets the termination flag."""
        from src.gui.workers import PipelineWorker
        
        worker = PipelineWorker(["python", "-c", "pass"])
        
        assert not worker._is_terminated
        
        worker.terminate_process()
        
        assert worker._is_terminated


class TestChatWorker:
    """Tests for ChatWorker functionality."""
    
    def test_chat_worker_initialization(self):
        """Test ChatWorker initializes correctly."""
        from src.gui.workers import ChatWorker
        from src.metadata import MetadataChatSession
        
        mock_session = MagicMock(spec=MetadataChatSession)
        
        worker = ChatWorker(
            session=mock_session,
            prompt="Test prompt",
            model_choice="gemini"
        )
        
        assert worker.session == mock_session
        assert worker.prompt == "Test prompt"
        assert worker.model_choice == "gemini"


class TestMetadataSeedWorker:
    """Tests for MetadataSeedWorker functionality."""
    
    def test_seed_worker_initialization(self):
        """Test MetadataSeedWorker initializes correctly."""
        from src.gui.workers import MetadataSeedWorker
        from src.metadata import MetadataChatSession
        
        mock_session = MagicMock(spec=MetadataChatSession)
        
        worker = MetadataSeedWorker(
            session=mock_session,
            transcript_text="Test transcript content"
        )
        
        assert worker.session == mock_session
        assert worker.transcript_text == "Test transcript content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

