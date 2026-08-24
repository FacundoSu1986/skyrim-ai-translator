import asyncio
from pathlib import Path

import pytest

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


@pytest.mark.asyncio
async def test_generate_voice_file_with_voice_type(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(
        form_id="0005", text="Stop right there!", translated_text="¡Alto ahí!", is_dialog=True, voice_type="MaleGuard"
    )

    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text("audio data")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)

    assert success is True
    expected_file = out_dir / "MaleGuard" / f"{entry.form_id}.mp3"
    assert expected_file.exists()
    assert expected_file.read_text() == "audio data"


@pytest.mark.asyncio
async def test_generate_voice_file_two_responses_same_info_distinct_files(tmp_path):
    """Two indexed responses of the same INFO FormID must produce two
    distinct staging MP3s (no overwrite/race in asyncio.gather)."""
    out_dir = tmp_path / "Sound"
    responses = [
        StringEntry(
            form_id="00000333",
            text="First",
            translated_text="Primera",
            is_dialog=True,
            voice_type="MaleGuard",
            string_index=0,
        ),
        StringEntry(
            form_id="00000333",
            text="Second",
            translated_text="Segunda",
            is_dialog=True,
            voice_type="MaleGuard",
            string_index=4,
        ),
    ]

    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text

        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(self.text)

    results = await asyncio.gather(
        *[
            generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)
            for entry in responses
        ]
    )

    assert results == [True, True]
    first_file = out_dir / "MaleGuard" / "00000333_0.mp3"
    second_file = out_dir / "MaleGuard" / "00000333_4.mp3"
    assert first_file.exists() and second_file.exists()
    assert first_file.read_text() == "Primera"
    assert second_file.read_text() == "Segunda"


@pytest.mark.asyncio
async def test_generate_voice_file_without_index_keeps_plain_name(tmp_path):
    """string_index=None keeps the legacy staging name (no invented index)."""
    out_dir = tmp_path / "Sound"
    entry = StringEntry(
        form_id="00000999", text="Hi", translated_text="Hola", is_dialog=True, voice_type="MaleGuard", string_index=None
    )

    class MockCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text("audio data")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)

    assert success is True
    assert (out_dir / "MaleGuard" / "00000999.mp3").exists()
    assert not list(out_dir.rglob("00000999_*.mp3"))
