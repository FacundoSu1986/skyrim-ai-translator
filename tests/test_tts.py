import pytest
from pathlib import Path
from src.models import StringEntry
from src.tts_generator import generate_voice_file

@pytest.mark.asyncio
async def test_generate_voice_file(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(form_id="0001", text="Hello", translated_text="Hola", is_dialog=True)
    
    # Mocking edge_tts internally for the test
    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text("audio data")
            
    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)
    
    assert success is True
    expected_file = out_dir / f"{entry.form_id}.mp3"
    assert expected_file.exists()
    assert expected_file.read_text() == "audio data"

@pytest.mark.asyncio
async def test_generate_voice_file_not_dialog(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(form_id="0002", text="Hello", translated_text="Hola", is_dialog=False)
    
    class MockCommunicate:
        def __init__(self, text, voice):
            pass
        async def save(self, filepath):
            Path(filepath).write_text("audio data")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)
    assert success is False
    expected_file = out_dir / f"{entry.form_id}.mp3"
    assert not expected_file.exists()

@pytest.mark.asyncio
async def test_generate_voice_file_no_translation(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(form_id="0003", text="Hello", translated_text=None, is_dialog=True)
    
    class MockCommunicate:
        def __init__(self, text, voice):
            pass
        async def save(self, filepath):
            Path(filepath).write_text("audio data")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)
    assert success is False
    expected_file = out_dir / f"{entry.form_id}.mp3"
    assert not expected_file.exists()

@pytest.mark.asyncio
async def test_generate_voice_file_exception(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(form_id="0004", text="Hello", translated_text="Hola", is_dialog=True)
    
    class FailingMockCommunicate:
        def __init__(self, text, voice):
            pass
        async def save(self, filepath):
            raise RuntimeError("Network failure or rate limiting")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=FailingMockCommunicate)
    assert success is False
    expected_file = out_dir / f"{entry.form_id}.mp3"
    assert not expected_file.exists()

