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
