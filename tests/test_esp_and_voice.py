import hashlib
import struct
from pathlib import Path
from src.esp_parser import parse_esp_file, MasterResolver, RecordKey, _resolve_record_key
from src.voice_mapper import resolve_voice_for_entry
from src.free_translator import translate_free_text_sync, _protect_glossary, _restore_glossary, _resolve_lang_code


def make_subrecord(s_type: bytes, payload: bytes) -> bytes:
    """Helper to build a Skyrim binary subrecord."""
    return s_type + struct.pack("<H", len(payload)) + payload


def make_record(rec_type: bytes, form_id: int, body: bytes, flags: int = 0) -> bytes:
    """Helper to build a 24-byte Skyrim standard binary record."""
    return rec_type + struct.pack("<IIIIHH", len(body), flags, form_id, 0, 44, 0) + body


def make_grup(label: bytes, records: bytes) -> bytes:
    """Helper to wrap records inside a Skyrim GRUP."""
    return b"GRUP" + struct.pack("<I4sIII", 24 + len(records), label, 0, 0, 0) + records


def make_tes4_header(masters: list[str] = ()) -> bytes:
    """Helper to build a TES4 header record with declared MAST subrecords."""
    body = b""
    for m in masters:
        body += make_subrecord(b"MAST", m.encode("utf-8") + b"\x00")
        body += make_subrecord(b"DATA", struct.pack("<Q", 0))
    return make_record(b"TES4", 0, body)


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


def test_esp_parser_local_speaker_resolution(tmp_path):
    """
    Test 1 (Local Chain): INFO -> local NPC_ -> local VTCK -> local VTYP -> EDID.
    Verifies full resolution when all records are defined locally within the plugin.
    """
    esp_path = tmp_path / "LydiaQuest.esp"

    # 1. VTYP record: FormID 0x00010001 with EDID "FemaleCommander"
    vtyp_body = make_subrecord(b"EDID", b"FemaleCommander\x00")
    vtyp_rec = make_record(b"VTYP", 0x00010001, vtyp_body)

    # 2. NPC_ record: FormID 0x00020002 with EDID "LydiaNPC", FULL "Lydia", and VTCK 0x00010001
    npc_body = (
        make_subrecord(b"EDID", b"LydiaNPC\x00") +
        make_subrecord(b"FULL", b"Lydia\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00010001))
    )
    npc_rec = make_record(b"NPC_", 0x00020002, npc_body)

    # 3. INFO record: FormID 0x00030003 with ANAM 0x00020002 (Lydia) and NAM1 dialogue text
    text = b"I am sworn to carry your burdens.\x00"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x00020002)) +
        make_subrecord(b"NAM1", text)
    )
    info_rec = make_record(b"INFO", 0x00030003, info_body)

    total_recs = vtyp_rec + npc_rec + info_rec
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", total_recs))

    entries = parse_esp_file(esp_path)
    assert len(entries) >= 1
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "00030003"
    assert dialog_entry.text == "I am sworn to carry your burdens."
    assert dialog_entry.actor == "Lydia"
    assert dialog_entry.voice_type == "FemaleCommander"


def test_esp_parser_skyrim_master_speaker_resolution(tmp_path):
    """
    Test 2 (Single Master): INFO in MyMod.esp referencing NPC defined ONLY in Skyrim.esm fixture.
    Skyrim.esm: NPC_ (0x0001A697) -> VTCK (0x00013AD8) -> VTYP EDID 'MaleCommander'.
    MyMod.esp: INFO (0x01000050) -> ANAM 0x0001A697 (mod_index 0 -> Skyrim.esm).
    """
    # 1. Create master fixture: Skyrim.esm
    skyrim_esm = tmp_path / "Skyrim.esm"
    vtyp_body = make_subrecord(b"EDID", b"MaleCommander\x00")
    vtyp_rec = make_record(b"VTYP", 0x00013AD8, vtyp_body)

    npc_body = (
        make_subrecord(b"EDID", b"JarlBalgruuf\x00") +
        make_subrecord(b"FULL", b"Jarl Balgruuf\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))
    )
    npc_rec = make_record(b"NPC_", 0x0001A697, npc_body)
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # 2. Create target mod: WhiterunQuest.esp declaring MAST Skyrim.esm
    mod_esp = tmp_path / "WhiterunQuest.esp"
    info_text = b"Whiterun stands strong with the Empire.\x00"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) +
        make_subrecord(b"NAM1", info_text)
    )
    info_rec = make_record(b"INFO", 0x01000050, info_body)
    mod_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(mod_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "01000050"
    assert dialog_entry.text == "Whiterun stands strong with the Empire."
    assert dialog_entry.actor == "Jarl Balgruuf"
    assert dialog_entry.voice_type == "MaleCommander"
    assert dialog_entry.is_dialog is True


def test_esp_parser_transitive_master_speaker_resolution(tmp_path):
    """
    Test 3 (Transitive Master): INFO in MyMod.esp -> NPC in Update.esm -> VTCK in Skyrim.esm.
    Verifies that MasterIndexData preserves each master's own declared MAST list and resolves
    FormIDs within the relative index space of the defining master.

    Hierarchy:
      - Skyrim.esm (0 masters):
          VTYP (0x00013AD8) -> EDID 'MaleCommander'
      - Update.esm (MAST: ['Skyrim.esm']):
          NPC_ (0x01000999) -> VTCK (0x00013AD8: mod_index 0 -> Skyrim.esm)
      - MyMod.esp (MAST: ['Skyrim.esm', 'Update.esm']):
          INFO (0x02000050) -> ANAM (0x01000999: mod_index 1 -> Update.esm)
    """
    # 1. Root Master: Skyrim.esm
    skyrim_esm = tmp_path / "Skyrim.esm"
    vtyp_rec = make_record(b"VTYP", 0x00013AD8, make_subrecord(b"EDID", b"MaleCommander\x00"))
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"VTYP", vtyp_rec))

    # 2. Intermediate Master: Update.esm (declares Skyrim.esm as master #0)
    update_esm = tmp_path / "Update.esm"
    npc_body = (
        make_subrecord(b"EDID", b"UpdateGuardNPC\x00") +
        make_subrecord(b"FULL", b"Update Guard\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))  # points to Skyrim.esm:0x013AD8
    )
    npc_rec = make_record(b"NPC_", 0x01000999, npc_body)
    update_esm.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", npc_rec))

    # 3. Target Plugin: MyMod.esp (declares Skyrim.esm as #0 and Update.esm as #1)
    mymod_esp = tmp_path / "MyMod.esp"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x01000999)) +  # points to Update.esm:0x000999
        make_subrecord(b"NAM1", b"I received new orders from the capital.\x00")
    )
    info_rec = make_record(b"INFO", 0x02000050, info_body)
    mymod_esp.write_bytes(make_tes4_header(["Skyrim.esm", "Update.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(mymod_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "02000050"
    assert dialog_entry.text == "I received new orders from the capital."
    assert dialog_entry.actor == "Update Guard"
    assert dialog_entry.voice_type == "MaleCommander"


def test_esp_parser_third_party_master_resolution(tmp_path):
    """
    Test 4 (Third-Party Master): MyMod.esp declaring multiple masters [Skyrim.esm, CustomMaster.esm],
    referencing an NPC defined ONLY in CustomMaster.esm (master index 1).
    """
    masters_dir = tmp_path / "masters"
    masters_dir.mkdir()

    # 1. Skyrim.esm in masters_dir
    skyrim_esm = masters_dir / "Skyrim.esm"
    skyrim_esm.write_bytes(make_tes4_header())

    # 2. CustomMaster.esm in masters_dir with custom NPC and VoiceType
    custom_esm = masters_dir / "CustomMaster.esm"
    vtyp_rec = make_record(b"VTYP", 0x00005001, make_subrecord(b"EDID", b"FemaleSultry\x00"))
    npc_body = (
        make_subrecord(b"EDID", b"SeraphinaNPC\x00") +
        make_subrecord(b"FULL", b"Seraphina\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00005001))
    )
    npc_rec = make_record(b"NPC_", 0x00007002, npc_body)
    custom_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # 3. Target plugin in tmp_path (different folder), passing master_search_paths
    target_esp = tmp_path / "TargetMod.esp"
    # ANAM has high byte 0x01 pointing to CustomMaster.esm (master index 1)
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x01007002)) +
        make_subrecord(b"NAM1", b"Care to have a drink with me?\x00")
    )
    info_rec = make_record(b"INFO", 0x02000010, info_body)
    target_esp.write_bytes(make_tes4_header(["Skyrim.esm", "CustomMaster.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(target_esp, master_search_paths=[masters_dir])
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "02000010"
    assert dialog_entry.text == "Care to have a drink with me?"
    assert dialog_entry.actor == "Seraphina"
    assert dialog_entry.voice_type == "FemaleSultry"


def test_esp_parser_master_object_id_collision_isolation(tmp_path):
    """
    Test 5 (Collision Isolation): Two masters (MasterA.esm, MasterB.esm) having identical object IDs (0x001234),
    proving that canonical RecordKey avoids any cross-contamination or confusion between masters.
    """
    # MasterA has NPC 0x001234 -> VoiceType "FemaleCommander"
    master_a = tmp_path / "MasterA.esm"
    vtyp_a = make_record(b"VTYP", 0x00000001, make_subrecord(b"EDID", b"FemaleCommander\x00"))
    npc_a = make_record(
        b"NPC_",
        0x00001234,
        make_subrecord(b"EDID", b"Alice\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000001))
    )
    master_a.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_a + npc_a))

    # MasterB has NPC 0x001234 -> VoiceType "MaleBrute"
    master_b = tmp_path / "MasterB.esm"
    vtyp_b = make_record(b"VTYP", 0x00000002, make_subrecord(b"EDID", b"MaleBrute\x00"))
    npc_b = make_record(
        b"NPC_",
        0x00001234,
        make_subrecord(b"EDID", b"Bob\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000002))
    )
    master_b.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_b + npc_b))

    # Target mod declaring masters [MasterA.esm, MasterB.esm]
    target_esp = tmp_path / "CollisionMod.esp"
    # Line 1 spoken by MasterA NPC (mod_index 0)
    info_a = make_record(
        b"INFO",
        0x02000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00001234)) +
        make_subrecord(b"NAM1", b"I am Alice from MasterA.\x00")
    )
    # Line 2 spoken by MasterB NPC (mod_index 1)
    info_b = make_record(
        b"INFO",
        0x02000002,
        make_subrecord(b"ANAM", struct.pack("<I", 0x01001234)) +
        make_subrecord(b"NAM1", b"I am Bob from MasterB.\x00")
    )
    target_esp.write_bytes(make_tes4_header(["MasterA.esm", "MasterB.esm"]) + make_grup(b"INFO", info_a + info_b))

    entries = parse_esp_file(target_esp)
    entry_alice = next(e for e in entries if e.form_id == "02000001" and e.is_dialog)
    entry_bob = next(e for e in entries if e.form_id == "02000002" and e.is_dialog)

    assert entry_alice.actor == "Alice"
    assert entry_alice.voice_type == "FemaleCommander"
    assert entry_bob.actor == "Bob"
    assert entry_bob.voice_type == "MaleBrute"


def test_esp_parser_missing_master_safe_fallback(tmp_path):
    """
    Test 6 (Missing Master): Missing master file must not crash, must not invent fake data (like 'MaleNord'),
    and must cleanly result in voice_type is None.
    """
    mod_esp = tmp_path / "MissingMasterMod.esp"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) +
        make_subrecord(b"NAM1", b"Where is my master file?\x00")
    )
    info_rec = make_record(b"INFO", 0x01000006, info_body)
    # Declares NonExistentMaster.esm which is absent on disk
    mod_esp.write_bytes(make_tes4_header(["NonExistentMaster.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(mod_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.form_id == "01000006"
    assert dialog_entry.actor == "Actor_0001A697"
    assert dialog_entry.voice_type is None
    assert dialog_entry.is_dialog is True


def test_esp_parser_invalid_master_index(tmp_path):
    """
    Test 7 (Invalid Index): Out-of-bounds master index (e.g. mod_index 5 when 1 master declared)
    must return unresolved (None) and NEVER fall back to current local plugin.
    """
    mod_esp = tmp_path / "InvalidIndexMod.esp"
    # Local NPC in plugin (local index = 1)
    local_npc = make_record(
        b"NPC_",
        0x01000555,
        make_subrecord(b"EDID", b"LocalGuard\x00") +
        make_subrecord(b"FULL", b"Local Guard\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x01000111))
    )
    local_vtyp = make_record(b"VTYP", 0x01000111, make_subrecord(b"EDID", b"MaleGuard\x00"))

    # INFO referencing invalid mod_index 0x08 (0x08000555)
    info_rec = make_record(
        b"INFO",
        0x01000999,
        make_subrecord(b"ANAM", struct.pack("<I", 0x08000555)) +
        make_subrecord(b"NAM1", b"I have an invalid index.\x00")
    )

    mod_esp.write_bytes(
        make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", local_vtyp + local_npc + info_rec)
    )

    resolved_key = _resolve_record_key(0x08000555, "InvalidIndexMod.esp", ["Skyrim.esm"])
    assert resolved_key is None

    entries = parse_esp_file(mod_esp)
    dialog_entry = next(e for e in entries if e.form_id == "01000999")
    assert dialog_entry.actor == "Actor_08000555"
    assert dialog_entry.voice_type is None


def test_esp_parser_master_read_only_immutability(tmp_path):
    """
    Test 8 (Read-Only Immutability): Verifies that parsing a mod referencing a master file strictly reads it,
    leaving master file bytes and SHA256 hash completely unmodified.
    """
    master_path = tmp_path / "ImmutableMaster.esm"
    vtyp_rec = make_record(b"VTYP", 0x00000010, make_subrecord(b"EDID", b"FemaleElf\x00"))
    npc_rec = make_record(
        b"NPC_",
        0x00000020,
        make_subrecord(b"EDID", b"ElfNPC\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000010))
    )
    master_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # Compute pre-parse SHA256
    original_bytes = master_path.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()

    # Create target mod
    mod_esp = tmp_path / "ReaderMod.esp"
    info_rec = make_record(
        b"INFO",
        0x01000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00000020)) +
        make_subrecord(b"NAM1", b"Testing read-only access.\x00")
    )
    mod_esp.write_bytes(make_tes4_header(["ImmutableMaster.esm"]) + make_grup(b"INFO", info_rec))

    # Parse mod
    entries = parse_esp_file(mod_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type == "FemaleElf"

    # Verify post-parse SHA256 and bytes
    post_bytes = master_path.read_bytes()
    post_sha256 = hashlib.sha256(post_bytes).hexdigest()
    assert post_sha256 == original_sha256
    assert post_bytes == original_bytes


def test_esp_parser_master_cache_single_parse(tmp_path, monkeypatch):
    """
    Test 9 (Master Cache): Verifies that when 500 dialogue records reference the same master,
    parse_esp_file opens and indexes the master file from disk exactly once.
    """
    master_path = tmp_path / "CachedMaster.esm"
    vtyp_rec = make_record(b"VTYP", 0x00000005, make_subrecord(b"EDID", b"MaleCommander\x00"))
    npc_rec = make_record(
        b"NPC_",
        0x00000006,
        make_subrecord(b"EDID", b"Commander\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000005))
    )
    master_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # Build 500 INFO records in target mod
    info_recs = b""
    for i in range(500):
        info_body = (
            make_subrecord(b"ANAM", struct.pack("<I", 0x00000006)) +
            make_subrecord(b"NAM1", f"Order number {i}\x00".encode("utf-8"))
        )
        info_recs += make_record(b"INFO", 0x01000000 + i, info_body)

    mod_esp = tmp_path / "BigQuest.esp"
    mod_esp.write_bytes(make_tes4_header(["CachedMaster.esm"]) + make_grup(b"INFO", info_recs))

    # Instrument MasterResolver.get_or_load_master to count actual disk parses inside parse_esp_file
    orig_get_or_load = MasterResolver.get_or_load_master
    disk_parse_count = 0

    def instrumented_get_or_load(self, master_name, origin_dir):
        nonlocal disk_parse_count
        master_file = self.find_master_file(master_name, origin_dir)
        if master_file and master_file.resolve() not in self._cache:
            disk_parse_count += 1
        return orig_get_or_load(self, master_name, origin_dir)

    monkeypatch.setattr(MasterResolver, "get_or_load_master", instrumented_get_or_load)

    entries = parse_esp_file(mod_esp)
    assert len(entries) == 500
    assert disk_parse_count == 1, f"Expected exactly 1 disk read/parse, got {disk_parse_count}"

    for e in entries:
        assert e.voice_type == "MaleCommander"
        assert e.actor == "Commander"


def test_esp_parser_esl_light_plugin_explicit_handling(tmp_path):
    """
    Test 10 (ESL / Light Plugin): ESL/light plugin references (high byte 0xFE) must be explicitly detected,
    return None for record key, and result in voice_type is None without raising unexpected errors.
    """
    # Raw FormID 0xFE001001 with mod_index 0xFE
    rec_key = _resolve_record_key(0xFE001001, "LightPluginMod.esp", ["Skyrim.esm"])
    assert rec_key is None

    mod_esp = tmp_path / "LightMod.esp"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0xFE001001)) +
        make_subrecord(b"NAM1", b"Spoken by a light plugin NPC.\x00")
    )
    info_rec = make_record(b"INFO", 0x01000001, info_body)
    mod_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(mod_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type is None
    assert dialog_entry.actor == "Actor_FE001001"


def test_esp_parser_origin_record_resolution_no_mast_override(tmp_path):
    """
    Test 11 (Origin-Record Resolution & No MAST-Order Override):
    Demonstrates that the parser resolves FormID references strictly against their
    origin owner plugin (RecordKey.plugin), and does NOT use the TES4.MAST declaration
    order as an arbitrary winning override heuristic.

    Hierarchy:
      - Skyrim.esm: NPC (0x0001A697) -> VTCK "MaleCommander", FULL "Jarl Balgruuf"
      - Patch.esm (MAST: ['Skyrim.esm']): has an override for NPC (0x0001A697) with VTCK "MaleBrute"
      - TargetMod.esp (MAST: ['Skyrim.esm', 'Patch.esm']): INFO pointing to ANAM 0x0001A697
        (mod_index 0 -> points to Skyrim.esm:0x0001A697)
        -> Resolves strictly to origin record in Skyrim.esm ('MaleCommander' / 'Jarl Balgruuf').
           Effective load-order WinningOverride is deferred to runtime discovery.
    """
    # 1. Skyrim.esm (Origin master)
    skyrim_esm = tmp_path / "Skyrim.esm"
    vtyp_skyrim = make_record(b"VTYP", 0x00013AD8, make_subrecord(b"EDID", b"MaleCommander\x00"))
    npc_skyrim = make_record(
        b"NPC_",
        0x0001A697,
        make_subrecord(b"EDID", b"JarlBalgruuf\x00") +
        make_subrecord(b"FULL", b"Jarl Balgruuf\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))
    )
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_skyrim + npc_skyrim))

    # 2. Patch.esm (Intermediate master with override for 0x0001A697)
    patch_esm = tmp_path / "Patch.esm"
    vtyp_patch = make_record(b"VTYP", 0x01013ADA, make_subrecord(b"EDID", b"MaleBrute\x00"))
    npc_patch_override = make_record(
        b"NPC_",
        0x0001A697,  # mod_index 0 -> points to Skyrim.esm:0x01A697
        make_subrecord(b"EDID", b"JarlBalgruuf\x00") +
        make_subrecord(b"FULL", b"Jarl Balgruuf (Patched)\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x01013ADA))
    )
    patch_esm.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", vtyp_patch + npc_patch_override))

    # 3. Target mod declaring Skyrim.esm and Patch.esm
    target_esp = tmp_path / "TargetMod.esp"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) +
        make_subrecord(b"NAM1", b"I speak with origin strength.\x00")
    )
    info_rec = make_record(b"INFO", 0x02000001, info_body)
    target_esp.write_bytes(make_tes4_header(["Skyrim.esm", "Patch.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(target_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type == "MaleCommander"
    assert dialog_entry.actor == "Jarl Balgruuf"


def test_esp_parser_local_tplt_resolution(tmp_path):
    """
    Test 12 (TPLT Local): When an NPC has no direct VTCK but specifies a TPLT template NPC,
    the resolver traverses the template relationship to resolve VoiceType.
    """
    esp_path = tmp_path / "TemplateQuest.esp"

    # 1. VTYP record: FormID 0x00010001 ("FemaleEvenToned")
    vtyp_rec = make_record(b"VTYP", 0x00010001, make_subrecord(b"EDID", b"FemaleEvenToned\x00"))

    # 2. Template NPC: FormID 0x00020001 with VTCK 0x00010001
    template_npc = make_record(
        b"NPC_",
        0x00020001,
        make_subrecord(b"EDID", b"BaseTemplateNPC\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00010001))
    )

    # 3. Instance NPC: FormID 0x00020002 with TPLT 0x00020001 (NO direct VTCK)
    instance_npc = make_record(
        b"NPC_",
        0x00020002,
        make_subrecord(b"EDID", b"InheritedNPC\x00") +
        make_subrecord(b"FULL", b"Inherited Citizen\x00") +
        make_subrecord(b"TPLT", struct.pack("<I", 0x00020001))
    )

    # 4. INFO record spoken by Instance NPC
    info_rec = make_record(
        b"INFO",
        0x00030001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00020002)) +
        make_subrecord(b"NAM1", b"I inherited my voice from a template.\x00")
    )

    esp_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + template_npc + instance_npc + info_rec))

    entries = parse_esp_file(esp_path)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type == "FemaleEvenToned"
    assert dialog_entry.actor == "Inherited Citizen"


def test_esp_parser_master_tplt_resolution(tmp_path):
    """
    Test 13 (TPLT Master): An NPC in MyMod.esp references a template NPC in MasterA.esm,
    which in turn inherits VTCK from Skyrim.esm.
    """
    # 1. Skyrim.esm with VTYP
    skyrim_esm = tmp_path / "Skyrim.esm"
    vtyp_rec = make_record(b"VTYP", 0x00013AD8, make_subrecord(b"EDID", b"MaleCommander\x00"))
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"VTYP", vtyp_rec))

    # 2. MasterA.esm with Base Template NPC pointing to Skyrim VTYP
    master_a = tmp_path / "MasterA.esm"
    base_npc = make_record(
        b"NPC_",
        0x01000100,
        make_subrecord(b"EDID", b"MasterBaseTemplate\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))
    )
    master_a.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", base_npc))

    # 3. TargetMod.esp with NPC pointing via TPLT to MasterA.esm:0x01000100
    target_esp = tmp_path / "TargetMod.esp"
    mod_npc = make_record(
        b"NPC_",
        0x02000200,
        make_subrecord(b"EDID", b"ModSoldier\x00") +
        make_subrecord(b"FULL", b"Mod Soldier\x00") +
        make_subrecord(b"TPLT", struct.pack("<I", 0x01000100))  # mod_index 1 -> MasterA.esm
    )
    info_rec = make_record(
        b"INFO",
        0x02000300,
        make_subrecord(b"ANAM", struct.pack("<I", 0x02000200)) +
        make_subrecord(b"NAM1", b"Ready for battle!\x00")
    )
    target_esp.write_bytes(make_tes4_header(["Skyrim.esm", "MasterA.esm"]) + make_grup(b"INFO", mod_npc + info_rec))

    entries = parse_esp_file(target_esp)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type == "MaleCommander"
    assert dialog_entry.actor == "Mod Soldier"


def test_esp_parser_tplt_cycle_protection(tmp_path):
    """
    Test 14 (TPLT Cycle Protection): Circular TPLT template references (NPC A -> NPC B -> NPC A)
    must be cleanly caught by cycle detection, returning voice_type is None without recursion errors.
    """
    esp_path = tmp_path / "CyclicTemplate.esp"

    # NPC A (0x00010001) -> TPLT NPC B (0x00010002)
    npc_a = make_record(
        b"NPC_",
        0x00010001,
        make_subrecord(b"EDID", b"CyclicA\x00") +
        make_subrecord(b"FULL", b"Cyclic Actor A\x00") +
        make_subrecord(b"TPLT", struct.pack("<I", 0x00010002))
    )

    # NPC B (0x00010002) -> TPLT NPC A (0x00010001)
    npc_b = make_record(
        b"NPC_",
        0x00010002,
        make_subrecord(b"EDID", b"CyclicB\x00") +
        make_subrecord(b"FULL", b"Cyclic Actor B\x00") +
        make_subrecord(b"TPLT", struct.pack("<I", 0x00010001))
    )

    # INFO spoken by NPC A
    info_rec = make_record(
        b"INFO",
        0x00010003,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00010001)) +
        make_subrecord(b"NAM1", b"I am stuck in an infinite template loop.\x00")
    )

    esp_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", npc_a + npc_b + info_rec))

    entries = parse_esp_file(esp_path)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type is None
    assert dialog_entry.actor == "Cyclic Actor A"
