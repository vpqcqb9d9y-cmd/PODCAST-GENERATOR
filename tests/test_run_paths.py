from pathlib import Path

from src.utils.storage import RunPaths


def test_run_paths_builds_directories(tmp_path: Path):
    paths = RunPaths(tmp_path, "2025-11-24", "Azure Networking 101")
    assert paths.run_dir.exists()
    assert paths.audio_dir.exists()
    assert paths.visuals_dir.exists()
    assert paths.cache_dir.exists()
    log_message = "test entry"
    paths.log(log_message)
    assert log_message in paths.log_path.read_text(encoding="utf-8")

