### Task 2: Translation Module (Mockable)

**Goal:** Build the LLM translation integration module.
**Tech Stack:** Python 3.11+, pytest
**Global Constraints:** Strict TDD process (Red-Green-Refactor).

**Files:**
- Create: `src/translator.py`
- Create: `tests/test_translator.py`

**Interfaces:**
- Consumes: `list[StringEntry]` (from Task 1)
- Produces: `translate_entries(entries: list[StringEntry], target_lang: str) -> list[StringEntry]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_translator.py
from src.models import StringEntry
from src.translator import translate_entries


def test_translate_entries():
    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="Attack!", is_dialog=True, actor="Bandit"),
    ]

    # We will pass a simple mock translator function
    def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"

    result = translate_entries(entries, "spanish", api_callable=mock_api_call)

    assert result[0].translated_text == "[ES] Hello"
    assert result[1].translated_text == "[ES] Attack!"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_translator.py -v`
Expected: FAIL with "ImportError" or "function not defined".

- [ ] **Step 3: Write minimal implementation**

```python
# src/translator.py
from typing import Callable, List
from src.models import StringEntry


def default_llm_call(text: str, context: str) -> str:
    # This is a placeholder for the actual LLM API call (OpenAI/Gemini)
    return f"Translated: {text}"


def translate_entries(
    entries: List[StringEntry], target_lang: str, api_callable: Callable = default_llm_call
) -> List[StringEntry]:
    for entry in entries:
        context = f"Context: This is spoken by {entry.actor}." if entry.actor else "Context: UI or generic text."
        entry.translated_text = api_callable(entry.text, context)
    return entries
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_translator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/translator.py tests/test_translator.py
git commit -m "feat: implement translation module with mock API support"
```
