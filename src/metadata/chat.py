from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Dict, List, Literal, Optional, Tuple

import google.generativeai as genai
from openai import AzureOpenAI

from ..utils import Settings, get_logger


AssistantRole = Literal["system", "user", "assistant"]

_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Performance thresholds
SLOW_AI_RESPONSE_THRESHOLD = 10.0  # seconds


@dataclass
class ChatMessage:
    role: AssistantRole
    content: str
    model: str


def _default_metadata() -> Dict:
    today = date.today().isoformat()
    return {
        "topic": "",
        "date": today,
        "summary": "",
        "key_concepts": [],
        "labs": [],
        "references": [],
        "reading_list": [],
        "call_to_action": "",
    }


def _default_visual_metadata() -> Dict:
    """Default structure for visual metadata."""
    return {
        "background": "",
        "images": [],
        "video": {
            "title": "",
            "duration": 0,
            "prompt": "",
            "style": "",
            "scene_structure": [],
            "mood": "",
            "color_palette": "",
            "music": "",
            "background_context": "",
        },
        "general_notes": {
            "aesthetics": "",
            "messages": "",
        },
    }


# Default visual metadata system prompt
DEFAULT_VISUAL_METADATA_PROMPT = """אתה מומחה ליצירת מטא-דאטה ויזואלית מקצועית לפרויקטים יצירתיים.

המשימה שלך: ליצור מטא-דאטה ויזואלית מפורטת עבור 10 תמונות + וידאו קצר המבוססים על התוכן שניתן לך.

הנחיות חשובות:
1. נתח את התוכן לעומק והבן את המסרים, הרגשות והאווירה
2. צור רצף נרטיבי של 10 תמונות המספרות סיפור ויזואלי
3. התאם את האסתטיקה לתוכן (מזרחית ישראלית, מודרנית, קלאסית וכו')
4. כתוב את ה-prompts באנגלית מקצועית לשימוש ב-AI (Midjourney, DALL-E, Imagen)
5. הוסף פרטים טכניים: סגנון צילום, תאורה, פלטת צבעים
6. צור מטא-דאטה לוידאו עם מבנה סצנות מפורט

החזר JSON במבנה הבא בלבד (ללא טקסט נוסף):
{
  "background": "רקע והקשר כללי על התוכן (בעברית)",
  "images": [
    {
      "index": 1,
      "title": "כותרת התמונה בעברית",
      "prompt": "Detailed English prompt for AI image generation...",
      "style": "Photography style, lighting, camera type",
      "mood": "מצב רוח בעברית (למשל: התמדה, תקווה, מרד)",
      "color_palette": "פלטת צבעים בעברית",
      "background_context": "הקשר סמלי ומשמעות בעברית"
    }
  ],
  "video": {
    "title": "כותרת הוידאו בעברית",
    "duration": 180,
    "prompt": "Detailed English prompt for video generation...",
    "style": "Video style description in English",
    "scene_structure": [
      {"start": "0:00", "end": "0:30", "description": "תיאור הסצנה בעברית"}
    ],
    "mood": "מצב רוח כללי בעברית",
    "color_palette": "פלטת צבעים לוידאו",
    "music": "הפניה למוזיקה או סגנון",
    "background_context": "הקשר ומשמעות הוידאו"
  },
  "general_notes": {
    "aesthetics": "הערות על האסתטיקה הכללית בעברית",
    "messages": "המסרים המרכזיים שהוויזואליה צריכה להעביר"
  }
}

חשוב: צור בדיוק 10 אובייקטי תמונות במערך images.
"""


class MetadataChatSession:
    """
    Conversational metadata designer (NotebookLM-style).
    
    Manages AI-powered chat sessions for metadata generation and enrichment.
    Supports both Google Gemini and Azure OpenAI backends.
    
    Features:
        - Multi-turn conversation with context
        - Automatic metadata extraction from AI responses
        - Material and URL attachment
        - Transcript bootstrapping
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize chat session with AI backends."""
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self.messages: List[ChatMessage] = []
        self.current_metadata: Dict = _default_metadata()
        self.current_visual_metadata: Dict = _default_visual_metadata()
        self.materials: List[Path] = []
        self.urls: List[str] = []
        self._gemini_model = None
        self._azure_client: Optional[AzureOpenAI] = None
        self._total_ai_time: float = 0.0
        self._request_count: int = 0
        
        self.logger.info("[MetadataChatSession.__init__] Initializing chat session")

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            model_name = settings.gemini_model or "gemini-1.5-flash"
            self._gemini_model = genai.GenerativeModel(model_name)
            self.logger.debug("[MetadataChatSession.__init__] Gemini configured: %s", model_name)
        else:
            self.logger.warning("GEMINI_API_KEY missing – falling back to Azure for metadata chat.")

        try:
            self._azure_client = AzureOpenAI(
                api_key=settings.openai_api_key,
                api_version=settings.openai_api_version,
                azure_endpoint=settings.openai_endpoint,
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            self.logger.warning("Failed to initialize AzureOpenAI client: %s", exc)
            self._azure_client = None

    # Public API -----------------------------------------------------
    def attach_materials(self, paths: List[Path]) -> None:
        self.materials = paths

    def attach_urls(self, urls: List[str]) -> None:
        self.urls = urls

    def reset(self) -> None:
        self.messages.clear()
        self.current_metadata = _default_metadata()
        self.current_visual_metadata = _default_visual_metadata()

    def clear_chat(self, preserve_metadata: bool = True) -> None:
        """Clear conversation history while optionally keeping current metadata."""
        self.messages.clear()
        if not preserve_metadata:
            self.current_metadata = _default_metadata()

    def import_metadata(self, metadata: Dict) -> None:
        """Replace current metadata with provided payload (used for CLI fallback)."""
        self.current_metadata = _default_metadata()
        if metadata:
            self._merge_metadata(metadata)

    def send(self, user_text: str, preferred_model: str = "gemini") -> Tuple[str, Dict]:
        """Send a chat message and receive assistant response + merged metadata."""
        if not user_text.strip():
            raise ValueError("Cannot send empty message.")

        self.messages.append(ChatMessage("user", user_text.strip(), "user"))

        model_choice = self._pick_model(preferred_model)
        prompt = self._compose_user_payload(user_text)
        assistant_text, metadata_patch = self._invoke_model(model_choice, prompt)

        if metadata_patch:
            self._merge_metadata(metadata_patch)
        self.messages.append(ChatMessage("assistant", assistant_text, model_choice))
        return assistant_text, self.current_metadata

    def bootstrap_from_transcript(self, transcript_text: str, force: bool = False) -> Dict[str, Optional[str]]:
        """Auto-build metadata from a transcript snippet when user hasn't provided any."""
        text = (transcript_text or "").strip()
        if not text:
            raise ValueError("Cannot seed metadata without transcript text.")
        if not force and not self._metadata_needs_seed():
            return {}

        snippet = text[:6000]
        prompt = (
            f"{self.settings.metadata_system_prompt}\n\n"
            "על בסיס התמלול הבא, בנה JSON מובנה עם שדות topic, summary, key_concepts, labs, "
            "references, reading_list ו-call_to_action. כלול גם מענה ידידותי בעברית בשדה assistant שמסביר "
            "כיצד כדאי להמשיך. אם חסר מידע, הצע שאלות המשך.\n\n"
            f"תמלול:\n{snippet}"
        )
        model_choice = self._pick_model("gemini")
        assistant_text, metadata_patch = self._invoke_model(model_choice, prompt)
        if metadata_patch:
            self._merge_metadata(metadata_patch)
        result: Dict[str, Optional[str]] = {"assistant": assistant_text or ""}
        if assistant_text:
            self.messages.append(ChatMessage("assistant", assistant_text, model_choice))
        bilingual_hint = None
        if self._detect_bilingual(text):
            bilingual_hint = (
                "שמתי לב שהתמלול משלב עברית ואנגלית. תרצה לבחור שפה ראשית לתוצרים ולקולות?"
            )
            self.messages.append(ChatMessage("assistant", bilingual_hint, model_choice))
        result["bilingual_hint"] = bilingual_hint
        return result

    def export_metadata(self) -> Dict:
        return dict(self.current_metadata)

    def export_visual_metadata(self) -> Dict:
        """Return visual metadata as a separate dict for storage in visual_metadata.json."""
        return dict(self.current_visual_metadata)

    def generate_visual_metadata(
        self,
        transcript_text: str,
        image_count: int = 10,
        preferred_model: str = "gemini",
    ) -> Dict:
        """
        Generate detailed visual metadata for image and video generation.
        
        Creates professional-grade visual metadata including:
        - Background context
        - 10 image prompts with style, mood, color palette
        - Video metadata with scene-by-scene breakdown
        - General aesthetic notes
        
        Args:
            transcript_text: Source content to analyze
            image_count: Number of images to generate metadata for (default 10)
            preferred_model: AI model to use ("gemini" or "azure")
            
        Returns:
            Dict with generated visual metadata
        """
        text = (transcript_text or "").strip()
        if not text:
            raise ValueError("Cannot generate visual metadata without transcript text.")
        
        self.logger.info("[MetadataChatSession] Generating visual metadata for %d images...", image_count)
        
        # Get existing metadata for context
        topic = self.current_metadata.get("topic", "")
        summary = self.current_metadata.get("summary", "")
        key_concepts = self.current_metadata.get("key_concepts", [])
        
        # Build the prompt
        system_prompt = self.settings.visual_metadata_system_prompt or DEFAULT_VISUAL_METADATA_PROMPT
        
        snippet = text[:8000]  # Use more text for visual analysis
        
        context_section = ""
        if topic or summary or key_concepts:
            context_section = f"""
מטא-דאטה קיים:
- נושא: {topic or 'לא ידוע'}
- תקציר: {summary or 'לא זמין'}
- מושגים מרכזיים: {', '.join(key_concepts) if key_concepts else 'לא זמינים'}
"""
        
        prompt = f"""{system_prompt}

{context_section}

תוכן המקור לניתוח:
{snippet}

הנחיות נוספות:
- צור בדיוק {image_count} תמונות
- התאם את האסתטיקה לתוכן
- כתוב prompts מפורטים ומקצועיים באנגלית
- הוסף הקשר ומשמעות סמלית לכל תמונה

החזר JSON תקין בלבד."""

        model_choice = self._pick_model(preferred_model)
        
        try:
            raw_response = self._invoke_visual_model(model_choice, prompt)
            visual_metadata = self._parse_visual_response(raw_response)
            
            if visual_metadata:
                self.current_visual_metadata = visual_metadata
                self.logger.info(
                    "[MetadataChatSession] Visual metadata generated: %d images, video: %s",
                    len(visual_metadata.get("images", [])),
                    bool(visual_metadata.get("video", {}).get("prompt"))
                )
            else:
                self.logger.warning("[MetadataChatSession] Visual metadata generation returned empty result")
                
            return self.current_visual_metadata
            
        except Exception as exc:
            self.logger.error("[MetadataChatSession] Visual metadata generation failed: %s", exc)
            raise RuntimeError(f"Visual metadata generation failed: {exc}") from exc

    def _invoke_visual_model(self, model_choice: str, prompt: str) -> str:
        """Invoke AI model for visual metadata generation with higher token limit."""
        if model_choice == "gemini" and self._gemini_model:
            try:
                response = self._gemini_model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.4,
                        "max_output_tokens": 4000,  # Higher limit for detailed metadata
                    }
                )
                # Check if response was blocked or has no valid parts
                if hasattr(response, "text") and response.text:
                    return response.text.strip()
                # Check for blocked response
                if hasattr(response, "prompt_feedback"):
                    block_reason = getattr(response.prompt_feedback, "block_reason", None)
                    if block_reason:
                        self.logger.warning("[MetadataChatSession] Gemini blocked: %s, falling back to Azure", block_reason)
                        if self._azure_client:
                            return self._invoke_visual_model("azure", prompt)
                        raise RuntimeError(f"Gemini blocked content (reason: {block_reason})")
                # Check candidates for finish_reason issues
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = getattr(candidate, "finish_reason", None)
                    if finish_reason and finish_reason != 1:  # 1 = STOP (normal)
                        self.logger.warning("[MetadataChatSession] Gemini finish_reason=%s, falling back to Azure", finish_reason)
                        if self._azure_client:
                            return self._invoke_visual_model("azure", prompt)
                        raise RuntimeError(f"Gemini did not complete (finish_reason: {finish_reason})")
                    # Try to extract text from parts
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        parts = candidate.content.parts
                        if parts and hasattr(parts[0], "text"):
                            return parts[0].text.strip()
                raise RuntimeError("Gemini returned empty response")
            except Exception as gemini_exc:
                # Fallback to Azure if available
                if self._azure_client and "azure" not in str(model_choice).lower():
                    self.logger.warning("[MetadataChatSession] Gemini failed: %s, trying Azure", gemini_exc)
                    return self._invoke_visual_model("azure", prompt)
                raise
        elif model_choice == "azure" and self._azure_client:
            messages = [
                {"role": "system", "content": "You are a professional visual metadata generator."},
                {"role": "user", "content": prompt},
            ]
            response = self._azure_client.chat.completions.create(
                model=self.settings.openai_deployment,
                messages=messages,
                temperature=0.4,
                max_tokens=4000,  # Higher limit for detailed metadata
            )
            return response.choices[0].message.content.strip()
        else:
            raise RuntimeError("Selected model is unavailable.")

    def _parse_visual_response(self, raw: str) -> Dict:
        """Parse visual metadata JSON from AI response."""
        try:
            # Try direct JSON parse first
            payload = json.loads(raw)
            return self._validate_visual_metadata(payload)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON fragment in text
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            fragment = raw[start : end + 1]
            try:
                payload = json.loads(fragment)
                return self._validate_visual_metadata(payload)
            except json.JSONDecodeError:
                pass
        
        self.logger.warning("[MetadataChatSession] Could not parse visual metadata JSON")
        return _default_visual_metadata()

    def _validate_visual_metadata(self, payload: Dict) -> Dict:
        """Validate and normalize visual metadata structure."""
        result = _default_visual_metadata()
        
        # Copy background
        if "background" in payload:
            result["background"] = str(payload["background"])
        
        # Validate and copy images
        images = payload.get("images", [])
        if isinstance(images, list):
            validated_images = []
            for i, img in enumerate(images):
                if isinstance(img, dict):
                    validated_images.append({
                        "index": img.get("index", i + 1),
                        "title": str(img.get("title", f"תמונה {i + 1}")),
                        "prompt": str(img.get("prompt", "")),
                        "style": str(img.get("style", "")),
                        "mood": str(img.get("mood", "")),
                        "color_palette": str(img.get("color_palette", "")),
                        "background_context": str(img.get("background_context", "")),
                    })
            result["images"] = validated_images
        
        # Validate and copy video
        video = payload.get("video", {})
        if isinstance(video, dict):
            result["video"] = {
                "title": str(video.get("title", "")),
                "duration": int(video.get("duration", 0)) if video.get("duration") else 0,
                "prompt": str(video.get("prompt", "")),
                "style": str(video.get("style", "")),
                "scene_structure": video.get("scene_structure", []) if isinstance(video.get("scene_structure"), list) else [],
                "mood": str(video.get("mood", "")),
                "color_palette": str(video.get("color_palette", "")),
                "music": str(video.get("music", "")),
                "background_context": str(video.get("background_context", "")),
            }
        
        # Validate and copy general notes
        notes = payload.get("general_notes", {})
        if isinstance(notes, dict):
            result["general_notes"] = {
                "aesthetics": str(notes.get("aesthetics", "")),
                "messages": str(notes.get("messages", "")),
            }
        
        return result

    def history(self) -> List[ChatMessage]:
        return list(self.messages)

    # Internal helpers ----------------------------------------------
    def _pick_model(self, preferred: str) -> str:
        if preferred == "azure" and self._azure_client:
            return "azure"
        if preferred == "gemini" and self._gemini_model:
            return "gemini"
        if self._gemini_model:
            return "gemini"
        if self._azure_client:
            return "azure"
        raise RuntimeError("No AI providers configured. Set GEMINI_API_KEY or Azure credentials.")

    def _compose_user_payload(self, user_text: str) -> str:
        materials_section = "\n".join(f"- {path.name}" for path in self.materials) or "לא הועלו קבצים"
        urls_section = "\n".join(f"- {url}" for url in self.urls) or "אין קישורים"
        metadata_snapshot = json.dumps(self.current_metadata, ensure_ascii=False, indent=2)
        return (
            f"{self.settings.metadata_system_prompt}\n\n"
            "הקשר נוסף:\n"
            f"* קבצים מצורפים:\n{materials_section}\n"
            f"* קישורים:\n{urls_section}\n"
            f"* מטא-דאטה קיים:\n{metadata_snapshot}\n\n"
            "הנחיות:\n"
            "- ענה כמו עוזר NotebookLM ידידותי, והצע תובנות/שאלות המשך.\n"
            "- החזר JSON תקין עם שני שדות: assistant (תשובתך באריכות) ו-metadata (עדכון לכל אחד מהשדות במידת הצורך).\n"
            "- השתמש בעברית ברורה; עבור מונחים באנגלית אפשר להשאיר באנגלית.\n\n"
            f"הודעת המשתמש:\n{user_text.strip()}"
        )

    def _invoke_model(self, model_choice: str, prompt: str) -> Tuple[str, Dict]:
        if model_choice == "gemini" and self._gemini_model:
            response = self._gemini_model.generate_content(prompt, generation_config={"temperature": 0.3})
            text = response.text.strip() if hasattr(response, "text") else str(response)
        elif model_choice == "azure" and self._azure_client:
            messages = self._build_azure_messages(prompt)
            response = self._azure_client.chat.completions.create(
                model=self.settings.openai_deployment,
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            )
            text = response.choices[0].message.content.strip()
        else:  # pragma: no cover - defensive
            raise RuntimeError("Selected model is unavailable.")

        assistant_text, metadata_patch = self._parse_response(text)
        return assistant_text, metadata_patch

    def _build_azure_messages(self, prompt: str) -> List[Dict[str, str]]:
        history = [{"role": "system", "content": self.settings.metadata_system_prompt}]
        for msg in self.messages[-6:]:
            if msg.role in {"user", "assistant"}:
                history.append({"role": msg.role, "content": msg.content})
        history.append({"role": "user", "content": prompt})
        return history

    def _parse_response(self, raw: str) -> Tuple[str, Dict]:
        text = raw
        metadata: Dict = {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # attempt to find JSON fragment inside text
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                fragment = raw[start : end + 1]
                try:
                    payload = json.loads(fragment)
                except json.JSONDecodeError:
                    payload = {}
            if not payload:
                return raw, {}
        assistant_text = payload.get("assistant") or payload.get("response") or raw
        metadata = payload.get("metadata") or {}
        return assistant_text, metadata

    def _merge_metadata(self, patch: Dict) -> None:
        for key, value in patch.items():
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                existing = self.current_metadata.setdefault(key, [])
                merged = existing + [item for item in value if item not in existing]
                self.current_metadata[key] = merged
            else:
                self.current_metadata[key] = value

    def _metadata_needs_seed(self) -> bool:
        required = ("topic", "summary", "key_concepts")
        return not any(self.current_metadata.get(field) for field in required)

    def _detect_bilingual(self, text: str) -> bool:
        return bool(_HEBREW_RE.search(text)) and bool(_LATIN_RE.search(text))


