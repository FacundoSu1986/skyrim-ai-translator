# Task 3 Report: TTS Generator Module

## What was implemented
Implemented the voice generation module using `edge-tts` in `src/tts_generator.py`:
- `generate_voice_file(entry: StringEntry, output_dir: str, voice: str = "es-ES-AlvaroNeural", tts_class=edge_tts.Communicate) -> bool`:
  - Filters out non-dialog entries (`is_dialog == False`) or entries without translation (`translated_text` is None/empty).
  - Creates the output directory if it does not exist.
  - Instantiates TTS generator class (defaulting to `edge_tts.Communicate`, overridable for unit test injection).
  - Generates and saves audio file as `{output_dir}/{entry.form_id}.wav`.
  - Asynchronously saves the output and returns `True` on success, `False` on skipped/invalid entries.

## What was tested & test results
Ran `pytest -v` across the entire codebase.
Total test suite pass: 18 passed in 0.38s.

Focused tests in `tests/test_tts.py`:
1. `test_generate_voice_file`: Valid dialog entry with translation generates output file `{form_id}.wav` and returns `True`.
2. `test_generate_voice_file_not_dialog`: Entry with `is_dialog=False` returns `False` and skips file creation.
3. `test_generate_voice_file_no_translation`: Entry with `translated_text=None` returns `False` and skips file creation.

## TDD Evidence

### RED Phase
Running `pytest tests/test_tts.py -v` before creating `src/tts_generator.py`:
```
=========================== short test summary info ===========================
ERROR tests/test_tts.py
ModuleNotFoundError: No module named 'src.tts_generator'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.19s ===============================
```

### GREEN Phase
Running `pytest tests/test_tts.py -v` after writing minimal implementation in `src/tts_generator.py`:
```
tests/test_tts.py::test_generate_voice_file PASSED                       [ 33%]
tests/test_tts.py::test_generate_voice_file_not_dialog PASSED            [ 66%]
tests/test_tts.py::test_generate_voice_file_no_translation PASSED        [100%]
============================== 3 passed in 0.39s ==============================
```

## Files changed
- `src/tts_generator.py` (Created)
- `tests/test_tts.py` (Created)

## Self-review findings
- Module design relies on dependency injection (`tts_class` parameter) to allow deterministic unit testing without performing external network calls during tests.
- Function interface cleanly adheres to contract requirements (`StringEntry` consumer, returns boolean success indicator, async signature for edge-tts compatibility).

---

# Task 3 Fix Report: Reviewer Feedback Adjustments

## Issues Addressed
1. **Uncaught Exception Handling (Important):**
   - Wrapped `communicate.save()` inside `try...except Exception:` in `src/tts_generator.py`.
   - Logged the error message and returned `False` gracefully upon failure so large batch processing is not interrupted.
   - Added unit test `test_generate_voice_file_exception` in `tests/test_tts.py`.

2. **Use `pathlib.Path` for File Operations (Minor):**
   - Replaced `os.makedirs` and `os.path.join` with `pathlib.Path` methods (`Path.mkdir(parents=True, exist_ok=True)` and `Path / filename`).

3. **Audio Encoding Mismatch Awareness (Minor):**
   - Changed output file format extension from `.wav` to `.mp3` inside `src/tts_generator.py` and updated unit tests in `tests/test_tts.py`.

## Verification & Test Results
Command run: `pytest tests/test_tts.py -v`
```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-8.4.2, pluggy-1.6.0
collected 4 items

tests/test_tts.py::test_generate_voice_file PASSED                       [ 25%]
tests/test_tts.py::test_generate_voice_file_not_dialog PASSED            [ 50%]
tests/test_tts.py::test_generate_voice_file_no_translation PASSED        [ 75%]
tests/test_tts.py::test_generate_voice_file_exception PASSED             [100%]

============================== 4 passed in 0.35s ==============================
```

Command run: `pytest -v` (Full suite)
```
============================= 19 passed in 0.38s ==============================
```

## Commit Information
Commit hash: `c3f7eafb002c02b26cf5278cd0ef8bed33b7d63e`
Commit message: `fix(tts): handle tts exceptions, use pathlib.Path and change output extension to .mp3`

