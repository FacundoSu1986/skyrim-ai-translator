### Task 3: TTS Generator Module

**Goal:** Generate voice audio files for translated dialogs.
**Tech Stack:** Python 3.11+, pytest, edge-tts, pytest-asyncio
**Global Constraints:** Strict TDD process (Red-Green-Refactor).

**Files:**
- Create: `src/tts_generator.py`
- Create: `tests/test_tts.py`

**Interfaces:**
- Consumes: `StringEntry` where `is_dialog == True` and `translated_text` is set.
- Produces: Audio files in `output/Sound/Voice/ModName/`. Returns boolean indicating success.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tts.py
import pytest
from pathlib import Path
from src.models import StringEntry
from src.tts_generator import generate_voice_file
import asyncio


@pytest.mark.asyncio
async def test_generate_voice_file(tmp_path):
    out_dir = tmp_path / "Sound"
    entry = StringEntry(form_id="0001", text="Hello", translated_text="Hola", is_dialog=True)

    # Mocking edge_tts internally for the test
    class MockCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text("audio data")

    success = await generate_voice_file(entry, str(out_dir), "es-ES-AlvaroNeural", tts_class=MockCommunicate)

    assert success is True
    expected_file = out_dir / f"{entry.form_id}.wav"
    assert expected_file.exists()
    assert expected_file.read_text() == "audio data"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_tts.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tts_generator.py
import os
import edge_tts
from src.models import StringEntry


async def generate_voice_file(
    entry: StringEntry, output_dir: str, voice: str = "es-ES-AlvaroNeural", tts_class=edge_tts.Communicate
) -> bool:
    if not entry.is_dialog or not entry.translated_text:
        return False

    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{entry.form_id}.wav")

    communicate = tts_class(entry.translated_text, voice)
    await communicate.save(file_path)
    return True
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_tts.py -v` (Note: requires `pytest-asyncio` installed)
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/tts_generator.py tests/test_tts.py
git commit -m "feat: implement TTS voice generator using edge-tts"
```
