from dataclasses import dataclass
from typing import Optional

@dataclass
class StringEntry:
    form_id: str
    text: str
    is_dialog: bool = False
    actor: Optional[str] = None
    translated_text: Optional[str] = None
    voice_type: Optional[str] = None

