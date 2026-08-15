### Task 4: DSD Exporter

**Goal:** Export the translated entries to a JSON file compatible with Dynamic String Distributor (DSD).
**Tech Stack:** Python 3.11+, pytest
**Global Constraints:** Strict TDD process (Red-Green-Refactor). Output to `output/`.

**Files:**
- Create: `src/dsd_exporter.py`
- Create: `tests/test_dsd.py`

**Interfaces:**
- Consumes: `list[StringEntry]` (from Task 2, with `translated_text` populated).
- Produces: `export_to_dsd(entries: list[StringEntry], output_file: str) -> None` creates a JSON file where the key is the `form_id` and the value is the `translated_text`. Only entries with a valid `translated_text` should be included.

- [ ] **Step 1: Write the failing test**
Create `tests/test_dsd.py` covering positive case, omitting None translations, and correct JSON formatting.
- [ ] **Step 2: Run test to fail**
- [ ] **Step 3: Write minimal implementation**
Create `src/dsd_exporter.py`. Output JSON should be properly formatted (e.g. `indent=4`). Ensure you use `pathlib.Path` to create intermediate directories if they don't exist before writing the JSON file.
- [ ] **Step 4: Run test to pass**
- [ ] **Step 5: Commit**
