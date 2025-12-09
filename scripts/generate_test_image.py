from __future__ import annotations

import json
from pathlib import Path
from typing import List

import typer

from src.utils import Settings
from src.visuals.google_ai_visuals import GoogleAIVisualGenerator


app = typer.Typer(help="Generate a single visual asset to verify Imagen/placeholder flow.")


def _load_metadata(metadata_path: Path) -> dict:
    if not metadata_path.exists():
        raise typer.BadParameter(f"Metadata not found: {metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _extract_concepts(payload: dict) -> List[str]:
    concepts = payload.get("key_concepts") or []
    if isinstance(concepts, list) and concepts:
        return [str(concept) for concept in concepts]
    topic = payload.get("topic") or payload.get("summary") or "visual validation"
    return [topic]


@app.command()
def run(
    metadata: Path = typer.Option(
        Path("data/sample_metadata.json"),
        "--metadata",
        "-m",
        exists=True,
        readable=True,
        help="Metadata JSON used to derive concepts.",
    ),
    output: Path = typer.Option(
        Path("outputs/test_image/network_map.png"),
        "--output",
        "-o",
        help="Where to store the generated image.",
    ),
    mode: typer.Option = typer.Option(
        "network_map",
        "--mode",
        "-t",
        help="Visual type: network_map | slide | concept",
    ),
) -> None:
    """Generate a quick visual to ensure the Imagen integration (or placeholder) works."""
    settings = Settings.load()
    generator = GoogleAIVisualGenerator(settings)
    metadata_payload = _load_metadata(metadata)
    concepts = _extract_concepts(metadata_payload)
    output.parent.mkdir(parents=True, exist_ok=True)

    result = None
    mode_lower = mode.lower()

    if mode_lower == "slide":
        topic = metadata_payload.get("topic") or concepts[0]
        result = generator.generate_slide_background(topic=topic, output_path=output)
    elif mode_lower == "concept":
        summary = metadata_payload.get("summary", "")
        result = generator.generate_concept_illustration(concept=concepts[0], context=summary, output_path=output)
    else:
        result = generator.generate_network_map(concepts=concepts, metadata=metadata_payload, output_path=output)

    if result:
        typer.echo(f"✅ Test image saved to {result}")
    else:
        typer.echo("⚠️ Image generation failed – check logs for details.")


if __name__ == "__main__":
    app()
