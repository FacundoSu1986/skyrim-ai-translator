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

def test_parse_strings_file_defaults(tmp_path):
    # Setup mock data without optional fields
    mock_data = [
        {"FormID": "00067890", "Text": "Iron Sword"}
    ]
    file_path = tmp_path / "strings_default.json"
    file_path.write_text(json.dumps(mock_data))
    
    # Execute
    result = parse_strings_file(str(file_path))
    
    # Assert
    assert len(result) == 1
    assert result[0].form_id == "00067890"
    assert result[0].text == "Iron Sword"
    assert result[0].is_dialog is False
    assert result[0].actor is None
    assert result[0].translated_text is None
