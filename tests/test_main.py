from pathlib import Path

import pytest

import main


@pytest.mark.asyncio
async def test_main_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    # Change cwd to tmp_path so main() writes its test_input.json and output/ directory relative to tmp_path
    monkeypatch.chdir(tmp_path)

    # Run main()
    await main.main()

    # The demo's legacy JSON input carries no DSD metadata: the pipeline must
    # refuse the export instead of fabricating it, and say so explicitly.
    dsd_file = tmp_path / "output" / "dsd" / "Skyrim.esm.json"
    assert not dsd_file.exists(), f"Expected {dsd_file} NOT to exist"
    assert "DSD_METADATA_MISSING" in capsys.readouterr().out

    # Check voice output directory
    voice_dir = tmp_path / "output" / "Sound" / "Voice" / "Skyrim.esm"
    assert voice_dir.exists()

    # Check created voice files
    voice_files = list(voice_dir.rglob("*.mp3"))
    assert len(voice_files) > 0
