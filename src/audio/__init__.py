"""Audio synthesis and mastering helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .tts import SpeechSynthesizer
from .stitcher import PodcastStitcher

if TYPE_CHECKING:
    from ..utils import CostTracker, Settings, VoiceProfileManager


def create_tts_synthesizer(
    settings: "Settings",
    cost_tracker: Optional["CostTracker"] = None,
    voice_profile: Optional[str] = None,
    voice_manager: Optional["VoiceProfileManager"] = None,
    provider: Optional[str] = None,
):
    """
    Factory function to create the appropriate TTS synthesizer.
    
    Args:
        settings: Application settings
        cost_tracker: Optional cost tracker for monitoring usage
        voice_profile: Name of the voice profile to use
        voice_manager: Voice profile manager instance
        provider: TTS provider override ('azure' or 'elevenlabs').
                  If None, uses settings.default_tts_provider.
    
    Returns:
        SpeechSynthesizer or ElevenLabsSpeechSynthesizer instance
    
    Raises:
        ValueError: If the specified provider is not supported
    """
    # Determine which provider to use
    tts_provider = provider or settings.default_tts_provider
    
    if tts_provider == "elevenlabs":
        from .elevenlabs_tts import ElevenLabsSpeechSynthesizer
        return ElevenLabsSpeechSynthesizer(
            settings=settings,
            cost_tracker=cost_tracker,
            voice_profile=voice_profile,
            voice_manager=voice_manager,
        )
    elif tts_provider == "azure":
        return SpeechSynthesizer(
            settings=settings,
            cost_tracker=cost_tracker,
            voice_profile=voice_profile,
            voice_manager=voice_manager,
        )
    else:
        raise ValueError(
            f"Unsupported TTS provider: {tts_provider}. "
            "Supported providers: 'azure', 'elevenlabs'"
        )


__all__ = [
    "SpeechSynthesizer",
    "PodcastStitcher",
    "create_tts_synthesizer",
]

