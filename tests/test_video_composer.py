"""
Tests for VideoComposer module.

Tests cover the critical audio attachment fix and video rendering functionality.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch, Mock

import pytest


class TestVideoComposerAudioFix:
    """Tests for the video composer audio attachment fix."""
    
    def test_render_final_video_duration_sync(self):
        """Test that video duration is synced to audio duration."""
        from src.visuals.video_composer import VideoComposer
        from src.utils import Settings
        
        # Create mock settings
        mock_settings = MagicMock(spec=Settings)
        
        with patch('src.visuals.video_composer.AudioFileClip') as mock_audio, \
             patch('src.visuals.video_composer.concatenate_videoclips') as mock_concat, \
             patch('src.visuals.video_composer.CompositeAudioClip') as mock_composite:
            
            # Setup mocks
            mock_audio_clip = MagicMock()
            mock_audio_clip.duration = 120.0  # 2 minutes audio
            mock_audio.return_value = mock_audio_clip
            
            mock_video_clip = MagicMock()
            mock_video_clip.duration = 100.0  # Different duration
            mock_concat.return_value = mock_video_clip
            
            # Mock with_duration to return a new clip with correct duration
            mock_adjusted_clip = MagicMock()
            mock_adjusted_clip.duration = 120.0
            mock_video_clip.with_duration.return_value = mock_adjusted_clip
            
            mock_composite_audio = MagicMock()
            mock_composite.return_value = mock_composite_audio
            
            mock_final_clip = MagicMock()
            mock_final_clip.audio = mock_composite_audio  # Audio should be attached
            mock_final_clip.duration = 120.0
            mock_adjusted_clip.with_audio.return_value = mock_final_clip
            
            composer = VideoComposer(settings=mock_settings)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_file = Path(tmpdir) / "audio.mp3"
                output_file = Path(tmpdir) / "output.mp4"
                
                # Create a fake audio file
                audio_file.touch()
                
                # Create mock clips
                mock_clip = MagicMock()
                clips = [mock_clip]
                
                # Call render_final_video - should call with_duration due to mismatch
                try:
                    composer.render_final_video(clips, audio_file, output_file)
                except Exception:
                    pass  # May fail due to file operations, but we're testing the logic
                
                # Verify with_duration was called to sync durations
                mock_video_clip.with_duration.assert_called_once_with(120.0)

    def test_audio_attachment_verification(self):
        """Test that audio attachment is verified before writing."""
        from src.visuals.video_composer import VideoComposer
        from src.utils import Settings
        
        mock_settings = MagicMock(spec=Settings)
        
        with patch('src.visuals.video_composer.AudioFileClip') as mock_audio, \
             patch('src.visuals.video_composer.concatenate_videoclips') as mock_concat, \
             patch('src.visuals.video_composer.CompositeAudioClip') as mock_composite:
            
            # Setup mocks where audio fails to attach
            mock_audio_clip = MagicMock()
            mock_audio_clip.duration = 60.0
            mock_audio.return_value = mock_audio_clip
            
            mock_video_clip = MagicMock()
            mock_video_clip.duration = 60.0
            mock_concat.return_value = mock_video_clip
            
            mock_composite_audio = MagicMock()
            mock_composite.return_value = mock_composite_audio
            
            # Simulate failed audio attachment
            mock_final_clip = MagicMock()
            mock_final_clip.audio = None  # Audio failed to attach!
            mock_video_clip.with_audio.return_value = mock_final_clip
            
            composer = VideoComposer(settings=mock_settings)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_file = Path(tmpdir) / "audio.mp3"
                output_file = Path(tmpdir) / "output.mp4"
                audio_file.touch()
                
                mock_clip = MagicMock()
                clips = [mock_clip]
                
                # Should raise RuntimeError when audio is None
                with pytest.raises(RuntimeError, match="Failed to attach audio"):
                    composer.render_final_video(clips, audio_file, output_file)


class TestVideoComposerTimeline:
    """Tests for video timeline creation."""
    
    def test_create_timeline_with_animations(self):
        """Test timeline creation when animation files exist."""
        from src.visuals.video_composer import VideoComposer
        from src.utils import Settings
        
        mock_settings = MagicMock(spec=Settings)
        
        with patch('src.visuals.video_composer.AudioFileClip') as mock_audio, \
             patch('src.visuals.video_composer.VideoFileClip') as mock_video:
            
            mock_audio_clip = MagicMock()
            mock_audio_clip.duration = 60.0
            mock_audio.return_value = mock_audio_clip
            
            mock_video_clip = MagicMock()
            mock_video_clip.duration = 30.0
            mock_video.return_value = mock_video_clip
            
            composer = VideoComposer(settings=mock_settings)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_file = Path(tmpdir) / "audio.mp3"
                animations_dir = Path(tmpdir) / "animations"
                animations_dir.mkdir()
                
                audio_file.touch()
                
                # Create fake animation files
                (animations_dir / "scene1.mp4").touch()
                (animations_dir / "scene2.mp4").touch()
                
                dialogue_json = {"dialogue": [{"speaker": "A", "text": "Hello"}]}
                metadata = {"topic": "Test"}
                
                clips = composer.create_timeline(
                    dialogue_json, metadata, audio_file, animations_dir
                )
                
                # Should have created clips from the animation files
                assert len(clips) >= 2

    def test_create_timeline_with_static_images(self, caplog):
        """Test timeline creation when only static AI images exist."""
        from src.visuals.video_composer import VideoComposer
        from src.utils import Settings
        
        mock_settings = MagicMock(spec=Settings)
        
        with patch('src.visuals.video_composer.AudioFileClip') as mock_audio, \
             patch('src.visuals.video_composer.ImageClip') as mock_image_clip:
            
            mock_audio_clip = MagicMock()
            mock_audio_clip.duration = 40.0
            mock_audio.return_value = mock_audio_clip
            
            mock_image_instance = MagicMock()
            mock_image_instance.with_duration.return_value = mock_image_instance
            mock_image_instance.with_start.return_value = mock_image_instance
            mock_image_clip.return_value = mock_image_instance
            
            composer = VideoComposer(settings=mock_settings)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_file = Path(tmpdir) / "audio.mp3"
                visuals_dir = Path(tmpdir) / "visuals"
                visuals_dir.mkdir()
                (visuals_dir / "concept_1.png").touch()
                audio_file.touch()
                
                caplog.set_level("INFO", logger="VideoComposer")
                run_paths = MagicMock()
                
                clips = composer.create_timeline(
                    {"dialogue": [{"speaker": "Roee", "text": "שלום"}]},
                    {"topic": "Test"},
                    audio_file,
                    visuals_dir,
                    run_paths,
                )
                
                assert mock_image_clip.called
                assert len(clips) == 1
                assert "Visual assets detected" in caplog.text
                run_paths.log.assert_called()


class TestSlideBuilder:
    """Tests for the slide-based video fallback."""
    
    def test_build_slide_clips_from_metadata(self):
        """Test slide generation from metadata when no animations exist."""
        from src.visuals.video_composer import VideoComposer
        from src.utils import Settings
        
        mock_settings = MagicMock(spec=Settings)
        composer = VideoComposer(settings=mock_settings)
        
        dialogue_json = {
            "dialogue": [
                {"speaker": "Roee", "text": "Hello, welcome!"},
                {"speaker": "Noa", "text": "Thanks for having me."},
            ]
        }
        
        metadata = {
            "topic": "Azure Basics",
            "date": "2025-11-26",
            "key_concepts": ["VNet", "Load Balancer", "VM"],
            "summary": "Introduction to Azure networking.",
        }
        
        total_duration = 60.0  # 1 minute
        
        clips = composer._build_slide_clips(dialogue_json, metadata, total_duration)
        
        # Should generate multiple slides
        assert len(clips) > 0
        
        # Total duration should approximately match
        total_clip_duration = sum(c.duration for c in clips)
        assert abs(total_clip_duration - total_duration) < 1.0  # Within 1 second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

