import json
import os
from src.models import StringEntry

def parse_strings_file(filepath: str) -> list[StringEntry]:
    """Parse Skyrim JSON string files into structured StringEntry dataclass instances.
    
    Args:
        filepath: Path to the JSON file to parse.
        
    Returns:
        List of StringEntry instances.
        
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON structure is invalid, not a list, or missing mandatory keys.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupt or invalid JSON content in file '{filepath}': {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Invalid JSON format in '{filepath}': expected a list, got {type(data).__name__}")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid entry at index {i} in '{filepath}': expected dict, got {type(item).__name__}")
        if "FormID" not in item or "Text" not in item:
            raise ValueError(f"Missing mandatory key ('FormID' or 'Text') at index {i} in '{filepath}': {item}")

    return [
        StringEntry(
            form_id=item["FormID"],
            text=item["Text"],
            is_dialog=item.get("IsDialog", False),
            actor=item.get("Actor")
        )
        for item in data
    ]

