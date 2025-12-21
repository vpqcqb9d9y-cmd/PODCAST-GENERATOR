from __future__ import annotations

"""
Centralized pricing helper for AI, TTS, and visual generation.

Keep all rates and shared calculation helpers here so UI (CostCenterDialog)
and backend trackers (CostTracker) stay in sync.
"""

from dataclasses import dataclass
from typing import Literal, Tuple


TTSProvider = Literal["azure", "elevenlabs"]
AIProvider = Literal["azure", "gemini"]
VisualProvider = Literal["manim", "imagen", "veo", "hybrid"]


@dataclass(frozen=True)
class PricingRates:
    words_per_minute: int = 150
    tokens_per_word: float = 1.3
    output_token_ratio: float = 0.6
    chars_per_word: float = 4.5

    # Token pricing (per 1K tokens)
    azure_gpt_input_per_1k: float = 0.005
    azure_gpt_output_per_1k: float = 0.015
    gemini_input_per_1k: float = 0.00035
    gemini_output_per_1k: float = 0.00105

    # TTS pricing (per 1K characters)
    azure_tts_per_1k_chars: float = 0.016
    elevenlabs_tts_per_1k_chars: float = 0.30

    # Visual pricing
    imagen_per_image: float = 0.04
    veo_per_second: float = 0.75

    # Production overheads
    video_overhead: float = 0.25
    ppt_extra: float = 0.08


PRICING = PricingRates()


def gpt_cost(tokens: float, output_tokens: float, provider: AIProvider) -> float:
    """Return cost for given token counts and provider."""
    if provider == "gemini":
        return (tokens / 1000) * PRICING.gemini_input_per_1k + (output_tokens / 1000) * PRICING.gemini_output_per_1k
    return (tokens / 1000) * PRICING.azure_gpt_input_per_1k + (output_tokens / 1000) * PRICING.azure_gpt_output_per_1k


def tts_cost(chars: float, provider: TTSProvider) -> Tuple[float, float]:
    """
    Return (cost, rate_used) for TTS provider.
    Rate is per 1K characters.
    """
    if provider == "elevenlabs":
        rate = PRICING.elevenlabs_tts_per_1k_chars
    else:
        rate = PRICING.azure_tts_per_1k_chars
    cost = (chars / 1000) * rate
    return cost, rate


def visual_cost(visual_gen: VisualProvider, visual_count: int) -> float:
    """Return cost for visual generation selection."""
    if visual_gen == "imagen":
        return max(0, visual_count) * PRICING.imagen_per_image
    if visual_gen == "veo":
        return max(0, visual_count) * PRICING.veo_per_second
    if visual_gen == "hybrid":
        count = max(0, visual_count)
        imagen_count = count // 2
        veo_secs = count - imagen_count
        return (imagen_count * PRICING.imagen_per_image) + (veo_secs * PRICING.veo_per_second)
    return 0.0


def azure_vs_elevenlabs_diff(chars: float) -> float:
    """
    Difference in cost when choosing ElevenLabs over Azure for given characters.
    Positive => ElevenLabs more expensive.
    """
    eleven_cost, _ = tts_cost(chars, "elevenlabs")
    azure_cost, _ = tts_cost(chars, "azure")
    return eleven_cost - azure_cost

