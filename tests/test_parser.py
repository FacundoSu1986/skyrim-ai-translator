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

def test_parse_strings_file_empty_list(tmp_path):
    file_path = tmp_path / "empty.json"
    file_path.write_text("[]")
    
    result = parse_strings_file(str(file_path))
    assert result == []

def test_parse_strings_file_nonexistent_file():
    with pytest.raises(FileNotFoundError, match="File not found"):
        parse_strings_file("nonexistent_file_path_12345.json")

def test_parse_strings_file_corrupt_json(tmp_path):
    file_path = tmp_path / "corrupt.json"
    file_path.write_text("{invalid_json:")
    
    with pytest.raises(ValueError, match="Corrupt or invalid JSON content"):
        parse_strings_file(str(file_path))

def test_parse_strings_file_not_a_list(tmp_path):
    file_path = tmp_path / "object.json"
    file_path.write_text(json.dumps({"FormID": "00012345", "Text": "Hello"}))
    
    with pytest.raises(ValueError, match="expected a list"):
        parse_strings_file(str(file_path))

def test_parse_strings_file_missing_form_id(tmp_path):
    mock_data = [{"Text": "No FormID"}]
    file_path = tmp_path / "missing_form_id.json"
    file_path.write_text(json.dumps(mock_data))
    
    with pytest.raises(ValueError, match="Missing mandatory key"):
        parse_strings_file(str(file_path))

def test_parse_strings_file_missing_text(tmp_path):
    mock_data = [{"FormID": "00012345"}]
    file_path = tmp_path / "missing_text.json"
    file_path.write_text(json.dumps(mock_data))
    
    with pytest.raises(ValueError, match="Missing mandatory key"):
        parse_strings_file(str(file_path))

def test_parse_strings_file_invalid_item_type(tmp_path):
    mock_data = ["not_a_dict"]
    file_path = tmp_path / "invalid_item.json"
    file_path.write_text(json.dumps(mock_data))
    
    with pytest.raises(ValueError, match="expected dict"):
        parse_strings_file(str(file_path))

