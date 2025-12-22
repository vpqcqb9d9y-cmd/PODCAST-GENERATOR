from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment, effects

from ..utils import (
    CostTracker,
    RunPaths,
    Settings,
    VoiceProfileManager,
    detect_language,
    get_logger,
)


class SpeechSynthesizer:
    """Convert dialogue JSON to individual speaker audio segments."""

    VOICE_MAP = {
        "Roee": "he-IL-AvriNeural",
        "Noa": "he-IL-HilaNeural",
    }

    def __init__(
        self,
        settings: Settings,
        cost_tracker: Optional[CostTracker] = None,
        voice_profile: Optional[str] = None,
        voice_manager: Optional[VoiceProfileManager] = None,
    ) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self.cost_tracker = cost_tracker or CostTracker()
        self.voice_manager = voice_manager or VoiceProfileManager(
            settings.voice_profile_path, settings.default_voice_profile
        )
        self.voice_profile_name = voice_profile or settings.default_voice_profile
        self.voice_profile = self.voice_manager.get(self.voice_profile_name)
        self.speech_config = speechsdk.SpeechConfig(subscription=settings.speech_key, region=settings.speech_region)
        if settings.speech_endpoint:
            self.speech_config.endpoint_id = settings.speech_endpoint
        self.speech_config.speech_synthesis_language = "he-IL"
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
        )

    def synthesize(self, dialogue_path: Path, run_paths: RunPaths, force: bool = False) -> List[Dict[str, object]]:
        run_paths.log("Starting speech synthesis.")
        data = json.loads(dialogue_path.read_text(encoding="utf-8"))
        segments: List[Dict[str, object]] = []
        for idx, entry in enumerate(data["dialogue"], start=1):
            target = run_paths.audio_dir / f"{idx:04d}_{entry['speaker'].lower()}.wav"
            if target.exists() and not force:
                segments.append({"path": target, "duration": self._probe_duration(target)})
                continue
            self._synthesize_entry(entry, target)
            segments.append({"path": target, "duration": self._probe_duration(target)})
        run_paths.log("Speech synthesis completed.")
        return segments

    def _synthesize_entry(self, entry: Dict[str, str], target: Path) -> None:
        speaker = entry["speaker"]
        text = entry["text"]

        language = detect_language(text)
        voice = self.voice_profile.get_voice(speaker, language)
        if not voice:
            # Prefer user-selected Azure default voice when available
            fallback_voice = getattr(self.settings, "azure_default_voice", "") or self.VOICE_MAP.get(
                speaker, self.VOICE_MAP["Roee"]
            )
            voice = fallback_voice
        self.speech_config.speech_synthesis_voice_name = voice
        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(target))
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=audio_config)

        ssml = self._build_ssml(voice, text)
        result = synthesizer.speak_ssml_async(ssml).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            cancellation_details = result.cancellation_details
            raise RuntimeError(f"TTS failed for {speaker}: {cancellation_details.reason} {cancellation_details.error_details}")

        segment = AudioSegment.from_file(target)
        segment = effects.normalize(segment)
        silence = AudioSegment.silent(duration=500)
        (segment + silence).export(target, format="wav")
        self.cost_tracker.add_tts_characters(len(text))
        self.logger.debug("Rendered segment %s for %s", target.name, speaker)

    @staticmethod
    def _build_ssml(voice: str, text: str) -> str:
        return f"""
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="he-IL">
  <voice name="{voice}">
    <prosody rate="1.05" pitch="+2%">
      {text}
    </prosody>
  </voice>
</speak>
""".strip()

    @staticmethod
    def _probe_duration(path: Path) -> float:
        """Best-effort duration reader for a rendered segment."""
        try:
            return float(AudioSegment.from_file(path).duration_seconds)
        except Exception:
            return 0.0

