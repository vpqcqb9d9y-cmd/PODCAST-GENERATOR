#!/usr/bin/env python3
"""
Direct pipeline test script for the universal content processing system.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Run the pipeline directly with test data."""
    from pipeline.runner import LecturePipeline
    from utils import Settings

    # Load settings
    settings = Settings.load()

    # Set up test paths
    transcript_path = Path("data/sample_transcript.txt")
    metadata_path = Path("data/sample_metadata.json")
    output_dir = Path("outputs/test_universal_system")

    print("🚀 Starting Universal Content Processing System Test")
    print("=" * 60)
    print(f"Transcript: {transcript_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Output: {output_dir}")
    print()

    try:
        # Create pipeline
        pipeline = LecturePipeline(settings=settings, dry_run=False)

        # Run the pipeline
        result = pipeline.run(
            transcript_path=transcript_path,
            metadata_path=metadata_path,
            output_dir=output_dir,
            force=True,
            skip_visuals=False,
            export_ppt=True,
        )

        print("✅ Pipeline completed successfully!")
        print(f"Output directory: {result.run_dir}")

        # Check outputs
        check_outputs(result.run_dir)

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

def check_outputs(output_dir: Path):
    """Check and report on generated outputs."""
    print("\n📊 Output Analysis:")
    print("-" * 30)

    # Check key files
    files_to_check = [
        ("Dialogue JSON", "dialogue.json"),
        ("Processing Log", "processing_log.txt"),
        ("Quality Report", "quality_report.json"),
        ("Metadata", "metadata.json"),
        ("Audio", "lecture_summary.mp3"),
        ("Video", "lecture_summary.mp4"),
        ("PPT", "summary.pptx"),
    ]

    for desc, filename in files_to_check:
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / 1024  # KB
            print(f"✅ {desc}: {filename} ({size:.1f} KB)")
        else:
            print(f"❌ {desc}: {filename} - MISSING")

    # Check directories
    dirs_to_check = [
        ("Audio Segments", "audio_segments"),
        ("Visuals", "visuals"),
        ("Materials", "materials"),
    ]

    print("\n📁 Directories:")
    for desc, dirname in dirs_to_check:
        dirpath = output_dir / dirname
        if dirpath.exists():
            files = list(dirpath.glob("*"))
            print(f"✅ {desc}: {len(files)} files")
        else:
            print(f"❌ {desc}: {dirname} - MISSING")

if __name__ == "__main__":
    sys.exit(main())
