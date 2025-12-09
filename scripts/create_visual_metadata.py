from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from src.utils.visual_metadata_builder import generate_visual_metadata_from_story

app = typer.Typer(help="Generate visual_metadata.json from story/metadata files.")


@app.command()
def build(
    story: Path = typer.Argument(..., exists=True, readable=True, help="Path to story.json"),
    metadata: Optional[Path] = typer.Option(
        None,
        "--metadata",
        "-m",
        exists=True,
        readable=True,
        help="Optional metadata.json (if not embedded in story.json).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Where to write visual_metadata.json (defaults to story directory).",
    ),
    image_count: int = typer.Option(
        10,
        "--image-count",
        "-c",
        min=4,
        max=20,
        help="Number of image prompts to generate.",
    ),
    include_video: bool = typer.Option(
        True,
        "--include-video/--no-video",
        help="Also create a video prompt block.",
    ),
) -> None:
    """Create a rich visual_metadata.json file using the story + metadata context."""
    typer.echo(f"📘 Loading story from {story}")
    result = generate_visual_metadata_from_story(
        story_path=story,
        metadata_path=metadata,
        image_count=image_count,
        include_video=include_video,
    )

    output_path = output or (story.parent / "visual_metadata.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"✅ visual_metadata.json saved to {output_path}")


if __name__ == "__main__":
    app()

