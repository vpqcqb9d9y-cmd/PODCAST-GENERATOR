from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ISRAELI_COLOR_PALETTES: Sequence[Dict[str, str]] = (
    {
        "name": "TelAvivNight",
        "colors": "deep navy, magenta gradients, neon cyan accents",
        "mood": "אורבני, חד, מקצועי",
    },
    {
        "name": "NegevSunset",
        "colors": "warm oranges, desert pink, soft purple dusk",
        "mood": "חם, מלא השראה",
    },
    {
        "name": "MediterraneanOffice",
        "colors": "azure blue, off-white concrete, soft teal lighting",
        "mood": "נינוח אבל ממוקד",
    },
)


@dataclass
class VisualMetadataBuilder:
    """Heuristic builder that converts story/metadata into visual metadata prompts."""

    metadata: Dict[str, Any]
    markdown_lines: List[str]

    def __post_init__(self) -> None:
        self.topic = self.metadata.get("topic") or self.metadata.get("summary") or "תוכן חינוכי"
        self.summary = (
            self.metadata.get("summary")
            or self.metadata.get("description")
            or next((line for line in self.markdown_lines if line and not line.startswith("#")), "")
        )
        self.key_concepts: List[str] = list(self.metadata.get("key_concepts") or [])
        self.labs: List[str] = list(self.metadata.get("labs") or [])
        self.quotes: List[str] = [
            line for line in self.markdown_lines if line.strip().startswith("- **")
        ]

    def build(self, image_count: int = 10, include_video: bool = True) -> Dict[str, Any]:
        images: List[Dict[str, Any]] = []
        index = 1

        images.append(self._hero_image(index))
        index += 1

        for concept in self.key_concepts:
            if len(images) >= image_count:
                break
            images.append(self._concept_image(index, concept))
            index += 1

        if self.labs and len(images) < image_count:
            images.append(self._labs_image(index))
            index += 1

        if self.quotes and len(images) < image_count:
            images.append(self._quote_image(index, self.quotes[0]))
            index += 1

        while len(images) < image_count:
            images.append(self._filler_image(index))
            index += 1

        aesthetics, style_guide = self._general_style_profile()

        result: Dict[str, Any] = {
            "background": self.summary or f"סיפור חזותי עבור {self.topic}",
            "general_notes": {
                "aesthetics": aesthetics,
                "style_guide": style_guide,
                "technical_specs": "1920x1080, יחס 16:9, 30fps, ניגודיות גבוהה לטקסט עברי.",
                "hebrew_support": "כל הכותרות והחיצים בעברית RTL, פונט כמו Assistant/Alef.",
                "guardrails": "התאם תמיד לנושא, אל תעתיק דוגמאות מערכתיות, הימנע מאזכורי מותגים (Azure/Cloud) אם לא הוזכרו במפורש.",
            },
            "images": images,
        }

        if include_video:
            result["video"] = self._video_block()

        return result

    # --------------------------------------------------------------------- helpers

    def _hero_image(self, index: int) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[0]
        style_profile = self._visual_style_for_topic()
        prompt = (
            f"Cinematic opening frame introducing '{self.topic}'. {style_profile['vibe']}. "
            f"Visuals reflect the story/lyrics: {self.summary[:140] if self.summary else 'תיאור קצר של הנושא'}. "
            f"Color mood: {palette['colors']}. High-quality 4K, Hebrew-friendly composition."
        )
        return self._image_payload(
            index=index,
            title="פתיח חזותי",
            prompt=prompt,
            style=style_profile["style"],
            mood=style_profile["mood"],
            palette=palette["colors"],
            context=f"פריים פתיחה שמכניס את הצופה לעולם {self.topic}",
        )

    def _concept_image(self, index: int, concept: str) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[index % len(ISRAELI_COLOR_PALETTES)]
        style_profile = self._visual_style_for_topic()
        prompt = (
            f"Visualize the idea '{concept}' as part of {self.topic}. {style_profile['vibe']}. "
            f"Use Hebrew labels where text appears. Avoid generic tech labs unless the topic demands it."
        )
        return self._image_payload(
            index=index,
            title=f"המחשת {concept}",
            prompt=prompt,
            style=style_profile["style"],
            mood=palette["mood"],
            palette=palette["colors"],
            context=f"הצגה חזותית של המושג {concept}",
        )

    def _labs_image(self, index: int) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[1]
        style_profile = self._visual_style_for_topic()
        prompt = (
            f"Hands-on moment that matches '{self.topic}': learner practicing the material. "
            f"{style_profile['vibe']}. Use props that fit the domain (music/art: instruments/stage; "
            f"technical: whiteboard/devices), warm lighting, authentic Hebrew context."
        )
        return self._image_payload(
            index=index,
            title="תרגול מעשי",
            prompt=prompt,
            style=style_profile["style"],
            mood=style_profile["mood"],
            palette=palette["colors"],
            context="המחשת תרגול או תהליך מרכזי שהוזכר בשיחה",
        )

    def _quote_image(self, index: int, quote: str) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[2]
        style_profile = self._visual_style_for_topic()
        prompt = (
            f"Quote spotlight from the dialogue: {quote[:180]}. {style_profile['vibe']}. "
            "Design for clear Hebrew typography with high contrast."
        )
        return self._image_payload(
            index=index,
            title="ציטוט מרכזי",
            prompt=prompt,
            style="podcast studio photography + typography overlay",
            mood="דיאלוגי ואותנטי",
            palette=palette["colors"],
            context=f"הצגת הציטוט: {quote}",
        )

    def _filler_image(self, index: int) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[index % len(ISRAELI_COLOR_PALETTES)]
        style_profile = self._visual_style_for_topic()
        prompt = (
            f"Complementary abstract visual for '{self.topic}'. {style_profile['vibe']}. "
            f"Hebrew-friendly composition, avoids brand names, focuses on mood '{palette['mood']}'."
        )
        return self._image_payload(
            index=index,
            title=f"אלמנט חזותי {index}",
            prompt=prompt,
            style=style_profile["style"],
            mood=style_profile["mood"],
            palette=palette["colors"],
            context="אלמנט משלים ללולאת הווידאו",
        )

    def _video_block(self) -> Dict[str, Any]:
        style_profile = self._visual_style_for_topic()
        scenes = [
            f"מבוא לנושא: {self.topic}",
            "רגע הדגמה או ביצוע מרכזי",
            "הדגשת רגש/רעיון מוביל",
            "סיום עם מסר מרכזי או קריאה לפעולה",
        ]
        return {
            "prompt": (
                f"Cinematic montage about '{self.topic}'. {style_profile['vibe']}. "
                "Show people or objects relevant to the story, with Hebrew callouts. Avoid vendor branding."
            ),
            "duration_seconds": 180,
            "scenes": scenes,
            "music_sync": "מתחיל בסקרנות, עובר לפעולה ומסתיים בתחושת הישג או רגש חם",
            "style_guide": style_profile["style"],
        }

    def _visual_style_for_topic(self) -> Dict[str, str]:
        """Map topic/metadata cues into a visual style profile."""
        topic_lower = (self.topic or "").lower()
        mood = (self.metadata.get("mood") or "").lower()
        summary_lower = (self.summary or "").lower()

        tech_keywords = ["cloud", "azure", "aws", "tech", "data", "network", "ai", "machine"]
        art_keywords = ["music", "song", "art", "culture", "design", "creative", "מוזיקה", "שיר", "תרבות"]

        is_tech = any(k in topic_lower for k in tech_keywords) or any(k in summary_lower for k in tech_keywords)
        is_art = any(k in topic_lower for k in art_keywords) or any(k in summary_lower for k in art_keywords)

        if "cloud" in mood or "tech" in mood:
            is_tech = True
        if any(k in mood for k in ["art", "music", "culture"]):
            is_art = True

        if is_tech and not is_art:
            return {
                "style": "modern data-visualization studio, clean gradients, crisp lighting",
                "vibe": "Modern professional studio with data viz accents, respectful and clear",
                "mood": "מקצועי וחדשני",
            }
        if is_art:
            return {
                "style": "cinematic documentary, warm lighting, emotional storytelling",
                "vibe": "Cinematic documentary feel with expressive framing and human focus",
                "mood": "חם ומרגש",
            }
        return {
            "style": "professional educational illustration, clean modern design",
            "vibe": "Professional educational look tailored to the specific topic",
            "mood": "חינוכי ומזמין",
        }

    def _general_style_profile(self) -> tuple[str, str]:
        profile = self._visual_style_for_topic()
        return (
            profile["vibe"],
            f"{profile['style']}; always tailor visuals to the given topic and avoid vendor-specific branding.",
        )

    @staticmethod
    def _image_payload(
        *,
        index: int,
        title: str,
        prompt: str,
        style: str,
        mood: str,
        palette: str,
        context: str,
    ) -> Dict[str, Any]:
        return {
            "index": index,
            "title": title,
            "prompt": prompt,
            "style": style,
            "mood": mood,
            "color_palette": palette,
            "background_context": context,
        }


def build_visual_metadata_locally(
    metadata: Dict[str, Any],
    dialogue_json: Optional[Dict[str, Any]] = None,
    transcript_text: str = "",
    image_count: int = 10,
    include_video: bool = True,
) -> Dict[str, Any]:
    """
    Build visual metadata without calling external AI providers.

    Uses the NotebookLM-style story markdown as input to VisualMetadataBuilder
    and falls back to universal prompts if anything fails.
    """
    from ..outputs.story import build_story_markdown  # Lazy import to avoid cycles

    dialogue_json = dialogue_json or {}
    try:
        story_lines = build_story_markdown(metadata, dialogue_json)
    except Exception as exc:  # pragma: no cover - defensive guard
        logging.getLogger(__name__).warning(
            "[VisualMetadataBuilder] Failed to build story markdown: %s", exc
        )
        story_lines = []

    condensed_lines = [line.strip() for line in story_lines if isinstance(line, str) and line.strip()]

    try:
        builder = VisualMetadataBuilder(metadata=metadata, markdown_lines=condensed_lines)
        visual_metadata = builder.build(image_count=image_count, include_video=include_video)
        if visual_metadata.get("images"):
            return visual_metadata
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "[VisualMetadataBuilder] Story-based builder failed: %s", exc
        )

    logging.getLogger(__name__).info(
        "[VisualMetadataBuilder] Falling back to universal visual metadata prompts."
    )
    return generate_universal_visual_metadata(
        metadata,
        transcript_length=len(transcript_text or ""),
        image_count=image_count,
        include_video=include_video,
    )


def load_story_file(story_path: Path) -> Dict[str, Any]:
    data = json.loads(story_path.read_text(encoding="utf-8"))
    if "markdown" not in data:
        raise ValueError(f"Story file {story_path} missing 'markdown' key")
    return data


def generate_visual_metadata_from_story(
    story_path: Path,
    metadata_path: Optional[Path] = None,
    image_count: int = 10,
    include_video: bool = True,
) -> Dict[str, Any]:
    story_data = load_story_file(story_path)
    markdown_lines = [line.strip() for line in story_data.get("markdown", [])]

    metadata: Dict[str, Any] = {}
    if metadata_path and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    elif isinstance(story_data.get("metadata"), dict):
        metadata = story_data["metadata"]

    if not metadata:
        raise ValueError("Metadata is required either inside story.json or via --metadata path.")

    builder = VisualMetadataBuilder(metadata=metadata, markdown_lines=markdown_lines)
    return builder.build(image_count=image_count, include_video=include_video)


def generate_universal_visual_metadata(
    metadata: Dict,
    transcript_length: int = 0,
    image_count: int = 10,
    include_video: bool = True,
) -> Dict:
    """
    Generate universal visual metadata based on content analysis, not specific themes.

    This creates visual prompts that work for ANY educational content type.
    """
    topic = metadata.get("topic", "")
    key_concepts = metadata.get("key_concepts", [])
    content_type = classify_content_type(metadata)

    # Generate image concepts
    images = []
    usable_concepts = key_concepts[:max(10, image_count)]
    for i, concept in enumerate(usable_concepts, 1):
        images.append(
            {
                "index": i,
                "title": f"ויזואליזציה של {concept}",
                "prompt": generate_universal_prompt(concept, content_type, topic),
                "style": determine_visual_style(content_type),
                "mood": determine_emotional_mood(concept),
                "color_palette": determine_color_palette(content_type),
                "background_context": f"מייצג את הרעיון המרכזי של {concept} בהקשר של {topic}",
            }
        )

    # Ensure at least 8 images
    while len(images) < max(8, image_count):
        fallback_concept = f"מושג {len(images) + 1}"
        images.append(
            {
                "index": len(images) + 1,
                "title": f"אלמנט חזותי {len(images) + 1}",
                "prompt": f"Professional educational illustration representing {fallback_concept}, clean modern design, high quality 4K",
                "style": "educational infographic, professional, clean",
                "mood": "educational, informative",
                "color_palette": "professional blue and gray",
                "background_context": f"אלמנט חזותי כללי להמחשת {fallback_concept}",
            }
        )

    payload: Dict[str, Any] = {
        "background": f"ויזואליזציה חינוכית של {topic} - מטא-דאטה ליצירת תוכן מבוסס AI",
        "general_notes": {
            "aesthetics": determine_content_aesthetics(content_type),
            "style_guide": "תמונות מקצועיות וברורות, מתאימות לחינוך וטכנולוגיה",
            "technical_specs": "רזולוציה 4K, פורמט 16:9, אופטימיזציה לחינוך מקוון",
        },
        "images": images[:image_count],
    }

    if include_video:
        payload["video"] = {
            "title": f"וידאו המסביר את {topic}" if topic else "וידאו חינוכי",
            "prompt": f"Educational video explaining {topic} concepts, professional style, clear explanations",
            "duration_seconds": min(180, max(60, transcript_length // 50)),
            "scenes": [f"Scene {i+1}: Explaining {concept}" for i, concept in enumerate(usable_concepts[:5])],
            "style_guide": "Educational explainer video, professional narration",
            "mood": "חינוכי וממוקד",
            "color_palette": determine_color_palette(content_type),
        }

    return payload


def classify_content_type(metadata: Dict) -> str:
    """Classify content type for appropriate visual styling."""
    topic = (metadata.get("topic") or "").lower()
    concepts = [c.lower() for c in metadata.get("key_concepts", [])]

    if any(word in topic for word in ["programming", "code", "python", "javascript", "algorithm"]):
        return "technical_programming"

    if any(word in " ".join(concepts) for word in ["network", "server", "cloud", "azure", "aws", "infrastructure"]):
        return "technical_networking"

    if any(word in topic for word in ["business", "management", "leadership", "strategy"]):
        return "business_professional"

    if any(word in topic for word in ["science", "medical", "health", "biology"]):
        return "science_medical"

    if any(word in topic for word in ["art", "music", "design", "creative"]):
        return "creative_artistic"

    return "educational_general"


def generate_universal_prompt(concept: str, content_type: str, topic: str) -> str:
    """Generate universal AI prompt that works for any educational content."""

    base_prompts = {
        "technical_programming": f"Clean code editor interface showing {concept}, syntax highlighting, professional development environment, dark theme, high contrast, technical diagram overlay",
        "technical_networking": f"Professional network infrastructure diagram illustrating {concept}, clean technical drawing, server racks, data flow arrows, modern data center aesthetic, blue and green color scheme",
        "business_professional": f"Professional business presentation slide about {concept}, clean corporate design, charts and graphs, modern office environment, trustworthy and professional appearance",
        "science_medical": f"Scientific illustration of {concept}, detailed anatomical or molecular diagram, laboratory equipment, professional medical aesthetic, clean and precise",
        "creative_artistic": f"Creative artistic representation of {concept}, modern digital art style, vibrant colors, innovative composition, artistic freedom with professional quality",
        "educational_general": f"Educational infographic explaining {concept}, clean modern design, icons and diagrams, easy to understand, professional educational style",
    }

    prompt = base_prompts.get(content_type, base_prompts["educational_general"])
    quality_additions = (
        ", highly detailed, professional quality, 4K resolution, educational context, clear and understandable"
    )

    return f"{prompt}{quality_additions}"


def determine_visual_style(content_type: str) -> str:
    """Determine appropriate visual style based on content type."""
    styles = {
        "technical_programming": "clean technical diagram, code interface, modern UI design",
        "technical_networking": "professional network diagram, infrastructure visualization, technical illustration",
        "business_professional": "corporate presentation, business infographic, professional chart design",
        "science_medical": "scientific illustration, medical diagram, laboratory photography",
        "creative_artistic": "modern digital art, creative illustration, artistic composition",
        "educational_general": "educational infographic, clean diagram, instructional design",
    }
    return styles.get(content_type, "educational infographic, professional design")


def determine_emotional_mood(concept: str) -> str:
    """Determine emotional mood based on concept content."""
    concept_lower = concept.lower()

    if any(word in concept_lower for word in ["challenge", "difficulty", "problem", "issue"]):
        return "focused and determined"
    if any(word in concept_lower for word in ["success", "achievement", "growth"]):
        return "motivated and positive"
    if any(word in concept_lower for word in ["security", "protection", "safety"]):
        return "trustworthy and reliable"
    if any(word in concept_lower for word in ["innovation", "creative", "new"]):
        return "innovative and dynamic"
    return "educational and informative"


def determine_color_palette(content_type: str) -> str:
    """Determine appropriate color palette based on content type."""
    palettes = {
        "technical_programming": "dark theme with syntax highlighting colors, blue and green accents",
        "technical_networking": "professional blue and gray, network cable colors, data flow blues",
        "business_professional": "corporate blues and grays, professional gold accents, trustworthy colors",
        "science_medical": "clean whites and blues, medical greens, laboratory color schemes",
        "creative_artistic": "vibrant and expressive colors, artistic freedom, modern palettes",
        "educational_general": "clean educational colors, high contrast for readability, professional blues",
    }
    return palettes.get(content_type, "professional educational colors, high contrast")


def determine_content_aesthetics(content_type: str) -> str:
    """Determine overall aesthetic approach based on content type."""
    aesthetics = {
        "technical_programming": "אסתטיקה טכנית נקייה, ממשקי משתמש מודרניים, קוד ודיאגרמות טכניות",
        "technical_networking": "אסתטיקה מקצועית טכנית, דיאגרמות רשת, צבעים כחולים ואפורים",
        "business_professional": "אסתטיקה קורפורטיבית, מצגות עסקיות, צבעים אמינים ומקצועיים",
        "science_medical": "אסתטיקה מדעית מדויקת, איורים מקצועיים, צבעים נקיים ומרפאיים",
        "creative_artistic": "אסתטיקה יצירתית ומודרנית, צבעים חיים, ביטוי אמנותי",
        "educational_general": "אסתטיקה חינוכית מקצועית, עיצוב ברור ונגיש",
    }
    return aesthetics.get(content_type, "אסתטיקה חינוכית מקצועית, עיצוב ברור ונגיש")

