import pytest
from pathlib import Path
import main


@pytest.mark.asyncio
async def test_main_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Change cwd to tmp_path so main() writes its test_input.json and output/ directory relative to tmp_path
    monkeypatch.chdir(tmp_path)

    # Run main()
    await main.main()

    # Check DSD output path based on plugin_name = Skyrim.esm
    dsd_file = tmp_path / "output" / "dsd" / "Skyrim.esm.json"
    assert dsd_file.exists(), f"Expected {dsd_file} to exist"

    # Check voice output directory
    voice_dir = tmp_path / "output" / "Sound" / "Voice" / "Skyrim.esm"
    assert voice_dir.exists()
    
    # Check created voice files
    voice_files = list(voice_dir.rglob("*.mp3"))
    assert len(voice_files) > 0
