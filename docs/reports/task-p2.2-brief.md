### Phase 2.2: Refactor Async & TTS

**Goal:** Parallelize network-bound translation calls and add voice_type routing to TTS.
**Tech Stack:** Python 3.11+, pytest, asyncio
**Global Constraints:** Strict TDD process.

**Modifications:**
1. **`src/translator.py`**:
   - Change `translate_entries` to `async def translate_entries(...)`.
   - Ensure the passed `api_callable` is expected to be an async function.
   - Use `asyncio.gather` with an `asyncio.Semaphore(10)` to process entries concurrently without overloading the API.

2. **`src/tts_generator.py`**:
   - In `generate_voice_file`, if `entry.voice_type` exists, append it to the path: `{output_dir}/{entry.voice_type}/{entry.form_id}.mp3`.
   - If not, save it in the root `{output_dir}/{entry.form_id}.mp3`.

3. **`tests/test_translator.py`** & **`tests/test_tts.py`**:
   - Update translator tests to use `pytest.mark.asyncio` and `await`.
   - Update TTS tests to verify the sub-folder creation for `voice_type`.

Your Job: Implement these changes, run `pytest tests/test_translator.py tests/test_tts.py -v`, commit, and report back.
