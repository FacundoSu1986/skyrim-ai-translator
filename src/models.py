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
    defining_plugin: Optional[str] = None
    local_object_id: Optional[int] = None
    record_type: Optional[str] = None
    subrecord_type: Optional[str] = None
    string_index: Optional[int] = None
    editor_id: Optional[str] = None
    quest_edid: Optional[str] = None
    topic_edid: Optional[str] = None

