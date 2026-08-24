from dataclasses import dataclass


@dataclass
class StringEntry:
    form_id: str
    text: str
    is_dialog: bool = False
    actor: str | None = None
    translated_text: str | None = None
    voice_type: str | None = None
    defining_plugin: str | None = None
    local_object_id: int | None = None
    record_type: str | None = None
    subrecord_type: str | None = None
    string_index: int | None = None
    editor_id: str | None = None
    quest_edid: str | None = None
    topic_edid: str | None = None
