### Phase 2.3: Refactor DSD & Main

**Goal:** Correct empty string behavior in DSD Exporter and integrate `plugin_name` in Main.
**Tech Stack:** Python 3.11+, pytest
**Global Constraints:** Strict TDD process.

**Modifications:**
1. **`src/dsd_exporter.py`**:
   - Change `if entry.translated_text is not None` to also exclude empty strings (`""` or strings with only spaces).
   - Ensure `tests/test_dsd.py` verifies this empty string filtering.

2. **`main.py`**:
   - Ensure the JSON file for DSD is named exactly after the original plugin. For example, add a variable `plugin_name = "Skyrim.esm"` and output to `output/dsd/{plugin_name}.json`.
   - Implement concurrent execution for `generate_voice_file` using `asyncio.gather`. Note: The user already made `translate_entries` awaited. Just fix the loop that generates voice files to run them concurrently.
   - Example snippet:
     ```python
     tasks = [
         generate_voice_file(entry, str(output_voice_dir), tts_class=MockCommunicate)
         for entry in translated_entries
         if entry.is_dialog
     ]
     await asyncio.gather(*tasks)
     ```

Your Job: Implement these changes, run `pytest tests/test_dsd.py -v` and `python main.py`, commit, and report back.
