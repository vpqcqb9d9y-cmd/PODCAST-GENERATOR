"""
M.B.S Studio - Cost Tracking
=============================

Tracks usage and costs for AI services including OpenAI,
Azure TTS, and ElevenLabs TTS.

Author: M.B.S Studio
Version: 1.1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CostTracker:
    """
    Track costs for OpenAI tokens and TTS characters.
    
    Supports both Azure Neural TTS and ElevenLabs TTS with
    separate tracking and cost calculation.
    """

    # Cost rates (USD per 1K units)
    openai_prompt_cost_per_1k: float = 0.0025  # GPT-4o mini
    openai_completion_cost_per_1k: float = 0.01
    azure_tts_cost_per_1k_chars: float = 0.016  # Azure Neural TTS
    elevenlabs_cost_per_1k_chars: float = 0.30  # ElevenLabs standard

    # Usage counters
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tts_characters: int = 0  # Azure TTS characters (for backward compatibility)
    elevenlabs_characters: int = 0  # ElevenLabs TTS characters
    visual_cost_usd: float = 0.0  # Imagen/VEO visual generation cost accumulator
    
    # Provider tracking
    tts_provider: str = "azure"  # Current TTS provider being used

    def add_openai_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Add OpenAI token usage."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def add_tts_characters(self, chars: int) -> None:
        """Add Azure TTS character usage (backward compatible)."""
        self.tts_characters += chars

    def add_elevenlabs_characters(self, chars: int) -> None:
        """Add ElevenLabs TTS character usage."""
        self.elevenlabs_characters += chars

    def add_visual_cost(self, amount: float) -> None:
        """Accumulate visual generation cost (e.g., Imagen/VEO)."""
        try:
            self.visual_cost_usd += float(amount)
        except (TypeError, ValueError):
            # Ignore invalid values to avoid crashing cost tracking
            return

    @property
    def openai_cost(self) -> float:
        """Calculate total OpenAI cost."""
        prompt_cost = (self.prompt_tokens / 1000) * self.openai_prompt_cost_per_1k
        completion_cost = (self.completion_tokens / 1000) * self.openai_completion_cost_per_1k
        return round(prompt_cost + completion_cost, 4)

    @property
    def azure_tts_cost(self) -> float:
        """Calculate Azure TTS cost."""
        return round((self.tts_characters / 1000) * self.azure_tts_cost_per_1k_chars, 4)

    @property
    def elevenlabs_tts_cost(self) -> float:
        """Calculate ElevenLabs TTS cost."""
        return round((self.elevenlabs_characters / 1000) * self.elevenlabs_cost_per_1k_chars, 4)

    @property
    def tts_cost(self) -> float:
        """Calculate total TTS cost (both providers)."""
        return round(self.azure_tts_cost + self.elevenlabs_tts_cost, 4)

    @property
    def total_tts_characters(self) -> int:
        """Total TTS characters from all providers."""
        return self.tts_characters + self.elevenlabs_characters

    def as_dict(self) -> Dict[str, float]:
        """
        Export all tracked costs as a dictionary.
        
        Returns:
            Dict with all cost metrics for serialization
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "tts_characters": self.tts_characters,  # Azure TTS
            "elevenlabs_characters": self.elevenlabs_characters,
            "total_tts_characters": self.total_tts_characters,
            "openai_cost_usd": self.openai_cost,
            "azure_tts_cost_usd": self.azure_tts_cost,
            "elevenlabs_tts_cost_usd": self.elevenlabs_tts_cost,
            "tts_cost_usd": self.tts_cost,
            "visual_cost_usd": round(self.visual_cost_usd, 4),
            "total_cost_usd": round(self.openai_cost + self.tts_cost + self.visual_cost_usd, 4),
        }
