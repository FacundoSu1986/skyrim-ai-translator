### Task 1: Parser and Data Models

**Goal:** Create the basic models and JSON parser for extracted Skyrim strings.

**Tech Stack:** Python 3.11+, pytest
**Global Constraints:** Strict TDD process (Red-Green-Refactor).

**Files:**
- Create: `src/models.py`
- Create: `src/parser.py`
- Create: `tests/test_parser.py`

**Interfaces:**
- Consumes: A JSON file representing extracted `.esp` strings.
- Produces: `parse_strings_file(filepath: str) -> list[StringEntry]`

- [ ] **Step 1: Write the failing test for models and parser**

```python
# tests/test_parser.py
import json
import pytest
from pathlib import Path
from src.models import StringEntry
from src.parser import parse_strings_file

def test_parse_strings_file(tmp_path):
    # Setup mock data
    mock_data = [
        {"FormID": "00012345", "Text": "Hello there", "IsDialog": True, "Actor": "Guard"}
    ]
    file_path = tmp_path / "strings.json"
    file_path.write_text(json.dumps(mock_data))
    
    # Execute
    result = parse_strings_file(str(file_path))
    
    # Assert
    assert len(result) == 1
    assert isinstance(result[0], StringEntry)
    assert result[0].form_id == "00012345"
    assert result[0].text == "Hello there"
    assert result[0].is_dialog is True
    assert result[0].actor == "Guard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError" for src.models.

- [ ] **Step 3: Write minimal implementation**

```python
# src/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class StringEntry:
    form_id: str
    text: str
    is_dialog: bool = False
    actor: Optional[str] = None
    translated_text: Optional[str] = None

# src/parser.py
import json
from src.models import StringEntry

def parse_strings_file(filepath: str) -> list[StringEntry]:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    entries = []
    for item in data:
        entry = StringEntry(
            form_id=item["FormID"],
            text=item["Text"],
            is_dialog=item.get("IsDialog", False),
            actor=item.get("Actor")
        )
        entries.append(entry)
    return entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py src/parser.py tests/test_parser.py
git commit -m "feat: implement data models and json parser"
```
