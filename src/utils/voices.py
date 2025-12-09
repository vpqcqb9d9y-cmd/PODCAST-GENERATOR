from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from langdetect import LangDetectException, detect

from .logging import get_logger

HEBREW_PATTERN = re.compile(r"[\u0590-\u05FF]")


def detect_language(text: str) -> str:
    """Return ISO language code (he/en) using heuristics + langdetect."""
    if HEBREW_PATTERN.search(text):
        return "he"
    snippet = text.strip()
    if not snippet:
        return "he"
    try:
        lang = detect(snippet)
    except LangDetectException:
        return "he"
    return lang.split("-")[0]


@dataclass(slots=True)
class VoiceProfile:
    """
    Voice profile configuration for TTS synthesis.
    
    Supports both Azure and ElevenLabs voices with per-speaker,
    per-language configuration.
    """
    name: str
    voices: Dict[str, Dict[str, object]]  # speaker -> provider/language -> voice config
    description: str = ""
    provider: str = "azure"  # default TTS provider for this profile

    def get_voice(self, speaker: str, language: str) -> Optional[str]:
        """Get Azure voice name for a speaker and language."""
        speaker_map = self.voices.get(speaker) or {}
        
        # Check for new multi-provider format
        if "azure" in speaker_map:
            azure_voices = speaker_map.get("azure", {})
            if isinstance(azure_voices, dict):
                return azure_voices.get(language) or azure_voices.get("he") or azure_voices.get("en")
        
        # Legacy format: direct language -> voice mapping
        return speaker_map.get(language) or speaker_map.get("he") or speaker_map.get("en")
    
    def get_elevenlabs_voice(self, speaker: str, language: str) -> Optional[Dict[str, str]]:
        """
        Get ElevenLabs voice configuration for a speaker.
        
        Args:
            speaker: Speaker name (e.g., 'Roee', 'Noa')
            language: ISO language code (unused, ElevenLabs uses multilingual models)
            
        Returns:
            Dict with voice_id and model keys, or None if not configured
        """
        speaker_map = self.voices.get(speaker) or {}
        
        # Check for ElevenLabs configuration
        elevenlabs_config = speaker_map.get("elevenlabs")
        if elevenlabs_config and isinstance(elevenlabs_config, dict):
            if "voice_id" in elevenlabs_config:
                return elevenlabs_config
        
        return None


class VoiceProfileManager:
    def __init__(self, config_path: Path, default_profile: str = "classic") -> None:
        self.logger = get_logger(self.__class__.__name__)
        self.config_path = config_path
        self.default_profile_name = default_profile
        self.profiles: Dict[str, VoiceProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            self.logger.warning("Voice profile config %s not found. Using built-in defaults.", self.config_path)
            return
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.default_profile_name = data.get("default_profile", self.default_profile_name)
        for name, payload in data.get("profiles", {}).items():
            self.profiles[name] = VoiceProfile(
                name=name,
                description=payload.get("description", ""),
                voices=payload.get("voices", {}),
                provider=payload.get("provider", "azure"),
            )
        if self.default_profile_name not in self.profiles and self.profiles:
            self.default_profile_name = next(iter(self.profiles))

    @property
    def profile_names(self) -> list[str]:
        return list(self.profiles.keys())

    def get(self, profile_name: Optional[str] = None) -> VoiceProfile:
        key = profile_name or self.default_profile_name
        if key not in self.profiles:
            self.logger.warning("Voice profile '%s' not found. Using default.", key)
            key = self.default_profile_name
        return self.profiles.get(key) or VoiceProfile(name="fallback", voices={})

    def open_in_explorer(self) -> None:  # pragma: no cover
        import os
        import subprocess
        import sys

        path = str(self.config_path)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

