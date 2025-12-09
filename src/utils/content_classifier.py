# src/utils/content_classifier.py - מערכת חדשה לזיהוי סוג תוכן
from typing import Dict, List


class ContentClassifier:
    """Automatically classify educational content for appropriate processing."""

    def __init__(self):
        self.content_patterns = {
            "technical_programming": {
                "keywords": ["python", "javascript", "code", "programming", "algorithm", "function", "class", "debug"],
                "concepts": ["variable", "loop", "array", "object", "api", "database"],
                "indicators": ["syntax", "compile", "runtime", "framework", "library"]
            },

            "technical_networking": {
                "keywords": ["network", "server", "cloud", "azure", "aws", "docker", "kubernetes"],
                "concepts": ["subnet", "firewall", "load balancer", "vpn", "dns", "routing"],
                "indicators": ["infrastructure", "scalability", "latency", "bandwidth", "protocol"]
            },

            "business_professional": {
                "keywords": ["business", "management", "strategy", "leadership", "marketing", "finance"],
                "concepts": ["roi", "kpi", "stakeholder", "budget", "timeline", "milestone"],
                "indicators": ["quarterly", "stakeholders", "profit", "growth", "market"]
            },

            "science_medical": {
                "keywords": ["medical", "health", "biology", "chemistry", "physics", "research"],
                "concepts": ["diagnosis", "treatment", "symptoms", "anatomy", "physiology"],
                "indicators": ["clinical", "evidence-based", "peer-reviewed", "hypothesis"]
            },

            "creative_artistic": {
                "keywords": ["design", "art", "music", "creative", "aesthetic", "composition"],
                "concepts": ["color theory", "composition", "harmony", "rhythm", "expression"],
                "indicators": ["inspiration", "portfolio", "exhibition", "performance", "original"]
            }
        }

    def classify(self, metadata: Dict) -> str:
        """Classify content based on metadata analysis."""
        topic = metadata.get("topic", "").lower()
        concepts = [c.lower() for c in metadata.get("key_concepts", [])]
        summary = metadata.get("summary", "").lower()

        # Combine all text for analysis
        all_text = f"{topic} {' '.join(concepts)} {summary}"

        # Score each content type
        scores = {}
        for content_type, patterns in self.content_patterns.items():
            score = 0

            # Check keywords (weight: 3)
            for keyword in patterns["keywords"]:
                if keyword in all_text:
                    score += 3

            # Check concepts (weight: 2)
            for concept in patterns["concepts"]:
                if concept in all_text:
                    score += 2

            # Check indicators (weight: 1)
            for indicator in patterns["indicators"]:
                if indicator in all_text:
                    score += 1

            scores[content_type] = score

        # Return highest scoring type, or educational_general as fallback
        best_match = max(scores.items(), key=lambda x: x[1])
        return best_match[0] if best_match[1] > 0 else "educational_general"

    def get_content_characteristics(self, content_type: str) -> Dict:
        """Get content characteristics for processing optimization."""
        characteristics = {
            "technical_programming": {
                "dialogue_style": "technical_explanation",
                "visual_style": "code_interface_diagram",
                "pace": "methodical",
                "complexity": "high"
            },

            "technical_networking": {
                "dialogue_style": "system_architecture",
                "visual_style": "network_diagram",
                "pace": "structured",
                "complexity": "medium"
            },

            "business_professional": {
                "dialogue_style": "strategic_discussion",
                "visual_style": "business_presentation",
                "pace": "deliberate",
                "complexity": "medium"
            },

            "science_medical": {
                "dialogue_style": "scientific_explanation",
                "visual_style": "scientific_illustration",
                "pace": "methodical",
                "complexity": "high"
            },

            "creative_artistic": {
                "dialogue_style": "creative_discussion",
                "visual_style": "artistic_representation",
                "pace": "inspirational",
                "complexity": "medium"
            },

            "educational_general": {
                "dialogue_style": "clear_explanation",
                "visual_style": "educational_infographic",
                "pace": "balanced",
                "complexity": "low"
            }
        }

        return characteristics.get(content_type, characteristics["educational_general"])
