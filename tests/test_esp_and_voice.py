import struct
from src.esp_parser import parse_esp_file
from src.voice_mapper import resolve_voice_for_entry
from src.free_translator import translate_free_text_sync

def test_voice_mapper():
    assert resolve_voice_for_entry("FemaleCommander") == "es-ES-ElviraNeural"
    assert resolve_voice_for_entry("MaleNord") == "es-ES-AlvaroNeural"
    assert resolve_voice_for_entry("FemaleElf") == "es-ES-ElviraNeural"
    assert resolve_voice_for_entry("MaleChild") == "es-ES-DarioNeural"
    assert resolve_voice_for_entry("UnknownFemaleNPC") == "es-ES-ElviraNeural"
    assert resolve_voice_for_entry("YoungKidBoy") == "es-ES-DarioNeural"
    assert resolve_voice_for_entry("TownGuardMan") == "es-ES-AlvaroNeural"
    assert resolve_voice_for_entry("RandomCreatureXYZ", default_fallback="es-MX-JorgeNeural") == "es-MX-JorgeNeural"
    assert resolve_voice_for_entry(None, default_fallback="es-ES-AlvaroNeural") == "es-ES-AlvaroNeural"

def test_free_translator_glossary():
    # Empty string handling
    assert translate_free_text_sync("") == ""
    assert translate_free_text_sync("   ") == "   "

    result = translate_free_text_sync("The Dragonborn travels to Whiterun to meet the Jarl.")
    assert "Sangre de Dragón" in result or "Dragonborn" in result
    assert "Carrera Blanca" in result or "Whiterun" in result

def test_esp_parser_synthetic(tmp_path):
    # Construct a minimal valid Skyrim 24-byte header TES4 .esp file with an INFO record and NAM1 subrecord
    esp_path = tmp_path / "TestPlugin.esp"
    
    # Header: TES4 (24 bytes: 4 tag + 4 size + 4 flags + 4 formid + 4 vcontrol + 2 ver + 2 unk)
    tes4_header = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 44, 0)
    
    # Subrecord: NAM1 with dialogue string
    text = b"Hello, brave warrior!\x00"
    nam1_sub = b"NAM1" + struct.pack("<H", len(text)) + text
    
    # Record: INFO (24 bytes header + subrecord body)
    info_rec = b"INFO" + struct.pack("<IIIIHH", len(nam1_sub), 0, 0x00012345, 0, 44, 0) + nam1_sub
    
    # Group: GRUP (24 bytes group header)
    grup_len = 24 + len(info_rec)
    grup_header = b"GRUP" + struct.pack("<I4sIII", grup_len, b"INFO", 0, 0, 0)
    
    esp_path.write_bytes(tes4_header + grup_header + info_rec)
    
    entries = parse_esp_file(esp_path)
    assert len(entries) == 1
    assert entries[0].form_id == "00012345"
    assert entries[0].text == "Hello, brave warrior!"
    assert entries[0].is_dialog is True
