### Phase 2: Refactor Parser & Models

**Goal:** Make the parser tolerant to errors and extend the data model.
**Tech Stack:** Python 3.11+, pytest
**Global Constraints:** Strict TDD process.

**Modifications:**
1. **`src/models.py`**:
   - Add `voice_type: Optional[str] = None` to `StringEntry`.

2. **`src/parser.py`**:
   - Instead of raising `ValueError` and crashing the whole parse if a dictionary is invalid or missing `FormID`/`Text`, use a `try...except` or `if` inside the loop, call `logging.warning()`, and `continue`.
   - Still raise `FileNotFoundError` or `ValueError` if the file doesn't exist, JSON is totally corrupt, or root is not a list.
   - Read `VoiceType` from JSON and map it to `voice_type`.

3. **`tests/test_parser.py`**:
   - Update tests to ensure that one bad entry doesn't crash the parsing of good entries in the same file.

Your Job: Implement these changes, run `pytest tests/test_parser.py -v`, commit, and report back.
