import struct
from src.esp_parser import parse_esp_file
from src.voice_mapper import resolve_voice_for_entry
from src.free_translator import translate_free_text_sync, _protect_glossary, _restore_glossary, _resolve_lang_code


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
    assert translate_free_text_sync("") == ""
    assert translate_free_text_sync("   ") == "   "

    result = translate_free_text_sync("The Dragonborn travels to Whiterun to meet the Jarl.")
    assert "Sangre de Dragón" in result or "Dragonborn" in result
    assert "Carrera Blanca" in result or "Whiterun" in result


def test_free_translator_language_glossary_isolation():
    """Validates that non-Spanish languages preserve canonical lore names without inserting Spanish glossary words."""
    assert _resolve_lang_code("french") == "fr"
    assert _resolve_lang_code("German") == "de"
    assert _resolve_lang_code("italian") == "it"
    assert _resolve_lang_code("spanish") == "es"

    # French: must NOT insert "Sangre de Dragón" or "Carrera Blanca"
    french_text, french_repl = _protect_glossary("The Dragonborn arrived at Whiterun.", target_lang="French")
    for placeholder, term in french_repl.items():
        assert term in {"Dragonborn", "Whiterun"}
        assert term not in {"Sangre de Dragón", "Carrera Blanca"}

    # German: must NOT insert Spanish
    german_text, german_repl = _protect_glossary("The Jarl of Windhelm spoke.", target_lang="German")
    for placeholder, term in german_repl.items():
        assert term in {"Jarl", "Windhelm"}
        assert term not in {"Ventalia"}

    # Spanish: MUST insert Spanish lore terms
    es_text, es_repl = _protect_glossary("The Dragonborn arrived at Whiterun.", target_lang="Spanish")
    es_values = set(es_repl.values())
    assert "Sangre de Dragón" in es_values
    assert "Carrera Blanca" in es_values

    # Case-insensitive restoration verification
    text = "Le __sky_0__ voyage vers __sKy_1__."
    replacements = {"__SKY_0__": "Dragonborn", "__SKY_1__": "Whiterun"}
    restored = _restore_glossary(text, replacements)
    assert restored == "Le Dragonborn voyage vers Whiterun."


def test_esp_parser_full_speaker_resolution(tmp_path):
    """
    Validates complete Skyrim relationship chain:
    INFO (ANAM) -> NPC_ (VTCK) -> VTYP (EDID='FemaleCommander') -> StringEntry with voice_type='FemaleCommander'.
    """
    esp_path = tmp_path / "LydiaQuest.esp"
    tes4_header = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 44, 0)

    # 1. VTYP record: FormID 0x00010001 with EDID "FemaleCommander"
    vtyp_edid = b"EDID" + struct.pack("<H", 16) + b"FemaleCommander\x00"
    vtyp_rec = b"VTYP" + struct.pack("<IIIIHH", len(vtyp_edid), 0, 0x00010001, 0, 44, 0) + vtyp_edid

    # 2. NPC_ record: FormID 0x00020002 with EDID "LydiaNPC", FULL "Lydia", and VTCK 0x00010001
    npc_edid = b"EDID" + struct.pack("<H", 9) + b"LydiaNPC\x00"
    npc_full = b"FULL" + struct.pack("<H", 6) + b"Lydia\x00"
    npc_vtck = b"VTCK" + struct.pack("<H", 4) + struct.pack("<I", 0x00010001)
    npc_body = npc_edid + npc_full + npc_vtck
    npc_rec = b"NPC_" + struct.pack("<IIIIHH", len(npc_body), 0, 0x00020002, 0, 44, 0) + npc_body

    # 3. INFO record: FormID 0x00030003 with ANAM 0x00020002 (Lydia) and NAM1 dialogue text
    text = b"I am sworn to carry your burdens.\x00"
    info_anam = b"ANAM" + struct.pack("<H", 4) + struct.pack("<I", 0x00020002)
    info_nam1 = b"NAM1" + struct.pack("<H", len(text)) + text
    info_body = info_anam + info_nam1
    info_rec = b"INFO" + struct.pack("<IIIIHH", len(info_body), 0, 0x00030003, 0, 44, 0) + info_body

    # Combine into file with GRUP
    total_recs = vtyp_rec + npc_rec + info_rec
    grup_header = b"GRUP" + struct.pack("<I4sIII", 24 + len(total_recs), b"INFO", 0, 0, 0)
    esp_path.write_bytes(tes4_header + grup_header + total_recs)

    entries = parse_esp_file(esp_path)
    assert len(entries) >= 1
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "00030003"
    assert dialog_entry.text == "I am sworn to carry your burdens."
    assert dialog_entry.actor == "Lydia"
    assert dialog_entry.voice_type == "FemaleCommander"


def test_esp_parser_vanilla_master_voice_resolution(tmp_path):
    """
    Validates resolution of vanilla Skyrim master VoiceType FormIDs (e.g. 0x00013AD8 -> 'MaleBrute').
    """
    esp_path = tmp_path / "BanditQuest.esp"
    tes4_header = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 44, 0)

    # NPC_ record with VTCK pointing to Skyrim.esm MaleBrute (0x00013AD8)
    npc_edid = b"EDID" + struct.pack("<H", 11) + b"BanditBoss\x00"
    npc_vtck = b"VTCK" + struct.pack("<H", 4) + struct.pack("<I", 0x00013AD8)
    npc_body = npc_edid + npc_vtck
    npc_rec = b"NPC_" + struct.pack("<IIIIHH", len(npc_body), 0, 0x00040004, 0, 44, 0) + npc_body

    # INFO dialogue spoken by BanditBoss
    text = b"Never should have come here!\x00"
    info_anam = b"ANAM" + struct.pack("<H", 4) + struct.pack("<I", 0x00040004)
    info_nam1 = b"NAM1" + struct.pack("<H", len(text)) + text
    info_body = info_anam + info_nam1
    info_rec = b"INFO" + struct.pack("<IIIIHH", len(info_body), 0, 0x00050005, 0, 44, 0) + info_body

    total_recs = npc_rec + info_rec
    grup_header = b"GRUP" + struct.pack("<I4sIII", 24 + len(total_recs), b"INFO", 0, 0, 0)
    esp_path.write_bytes(tes4_header + grup_header + total_recs)

    entries = parse_esp_file(esp_path)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "00050005"
    assert dialog_entry.text == "Never should have come here!"
    assert dialog_entry.actor == "BanditBoss"
    assert dialog_entry.voice_type == "MaleBrute"
