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

        result: Dict[str, Any] = {
            "background": self.summary or f"סיפור חזותי עבור {self.topic}",
            "general_notes": {
                "aesthetics": "סטודיו טכנולוגי ישראלי, צילום דוקו-סינמטי עם נגיעות אינפוגרפיקה.",
                "style_guide": "שילוב צילום אנשים אמיתי + שכבות גרפיקה בעברית RTL, התאמה לפודקאסט לימודי.",
                "technical_specs": "1920x1080, יחס 16:9, 30fps, ניגודיות גבוהה לטקסט עברי.",
                "hebrew_support": "כל הכותרות והחיצים בעברית RTL, פונט כמו Assistant/Alef.",
            },
            "images": images,
        }

        if include_video:
            result["video"] = self._video_block()

        return result

    # --------------------------------------------------------------------- helpers

    def _hero_image(self, index: int) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[0]
        prompt = (
            "Cinematic Israeli tech studio wide shot: mentor and learner stand near a "
            "glass board while Hebrew annotations float explaining Azure Virtual Networks "
            f"for '{self.topic}'. Large holographic cloud diagram, Tel Aviv skyline lights "
            "outside, dramatic lighting, 4K detail."
        )
        return self._image_payload(
            index=index,
            title="פתיח חזותי",
            prompt=prompt,
            style="cinematic documentary + infographic overlays",
            mood="מרגש ומקצועי",
            palette=palette["colors"],
            context="פריים פתיחה שמכניס את הצופה לעולם הרשתות ב-Azure",
        )

    def _concept_image(self, index: int, concept: str) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[index % len(ISRAELI_COLOR_PALETTES)]
        prompt = (
            f"Detailed Israeli workspace close-up illustrating '{concept}' in Azure networking. "
            "Holographic diagram hovering above a laptop, Hebrew labels for inputs/outputs, "
            "soft depth of field, cinematic color grade."
        )
        return self._image_payload(
            index=index,
            title=f"המחשת {concept}",
            prompt=prompt,
            style="modern educational illustration with photoreal base",
            mood=palette["mood"],
            palette=palette["colors"],
            context=f"הצגה חזותית של המושג {concept}",
        )

    def _labs_image(self, index: int) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[1]
        prompt = (
            "Israeli student working on Azure portal during a lab exercise, Hebrew sticky notes "
            "listing steps for creating VNets and NSG rules, warm lighting, cinematic over-the-shoulder shot."
        )
        return self._image_payload(
            index=index,
            title="תרגול מעשי",
            prompt=prompt,
            style="documentary photography with UI callouts",
            mood="מעשי ומאוורר",
            palette=palette["colors"],
            context="מחישת המעבדות שהוזכרו בשיחה",
        )

    def _quote_image(self, index: int, quote: str) -> Dict[str, Any]:
        palette = ISRAELI_COLOR_PALETTES[2]
        prompt = (
            "Split-screen composition showing two podcast hosts in a modern Israeli studio, "
            "with Hebrew subtitles of a highlighted quote floating between them, warm cinematic lighting."
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
        prompt = (
            "Stylized Azure control center dashboard floating above a Mediterranean cityscape, "
            "Hebrew legends and arrows explain network traffic flow, vibrant gradients."
        )
        return self._image_payload(
            index=index,
            title=f"אלמנט חזותי {index}",
            prompt=prompt,
            style="futuristic infographic + photography blend",
            mood="חדשני",
            palette=palette["colors"],
            context="אלמנט משלים ללולאת הווידאו",
        )

    def _video_block(self) -> Dict[str, Any]:
        scenes = [
            "מבוא ל-VNet והבדלה מהרשת הארגונית",
            "חלוקה ל-Subnets כמו חדרים בבית מודרני",
            "חוקי NSG מוצגים כדלתות עם חיישנים",
            "Load Balancer מחלק תנועה בין שירותים בעברית",
        ]
        return {
            "prompt": (
                "Cinematic montage of Israeli engineers configuring Azure networking: diagramming VNets, "
                "splitting into Subnets, applying NSG protections, balancing traffic with Load Balancer. "
                "Hebrew motion-graphics callouts, no generic stock footage."
            ),
            "duration_seconds": 180,
            "scenes": scenes,
            "music_sync": "מתחיל בסקרנות, עובר לשלב פעולה ומסתיים בתחושת הישג",
            "style_guide": "דוקו-טכנולוגי, שילוב אנשים אמיתיים וגרפיקות Azure, טקסט RTL ברור.",
        }

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

