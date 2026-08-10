import json
import logging
import pytest
from pathlib import Path
from src.models import StringEntry
from src.parser import parse_strings_file

def test_parse_strings_file(tmp_path):
    # Setup mock data
    mock_data = [
        {
            "FormID": "00012345",
            "Text": "Hello there",
            "IsDialog": True,
            "Actor": "Guard",
            "VoiceType": "MaleUnique"
        }
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
    assert result[0].voice_type == "MaleUnique"

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
    assert result[0].voice_type is None

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

def test_parse_strings_file_skips_malformed_entries(tmp_path, caplog):
    mock_data = [
        {"Text": "Missing FormID"},
        {"FormID": "00011111", "Text": "Good Entry 1", "VoiceType": "MaleNord"},
        "not_a_dictionary",
        {"FormID": "00022222"},  # Missing Text
        {"FormID": "00033333", "Text": "Good Entry 2"}
    ]
    file_path = tmp_path / "mixed_entries.json"
    file_path.write_text(json.dumps(mock_data))
    
    with caplog.at_level(logging.WARNING):
        result = parse_strings_file(str(file_path))
        
    assert len(result) == 2
    assert result[0].form_id == "00011111"
    assert result[0].text == "Good Entry 1"
    assert result[0].voice_type == "MaleNord"
    assert result[1].form_id == "00033333"
    assert result[1].text == "Good Entry 2"
    assert len(caplog.records) == 3


