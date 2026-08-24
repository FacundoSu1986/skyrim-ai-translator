import hashlib
import struct

from src.esp_parser import MasterResolver, _resolve_record_key, parse_esp_file
from src.free_translator import _protect_glossary, _resolve_lang_code, _restore_glossary, translate_free_text_sync
from src.voice_mapper import resolve_voice_for_entry


def make_subrecord(s_type: bytes, payload: bytes) -> bytes:
    """Helper to build a Skyrim binary subrecord."""
    return s_type + struct.pack("<H", len(payload)) + payload


def make_record(rec_type: bytes, form_id: int, body: bytes, flags: int = 0) -> bytes:
    """Helper to build a 24-byte Skyrim standard binary record."""
    return rec_type + struct.pack("<IIIIHH", len(body), flags, form_id, 0, 44, 0) + body


def make_grup(label: bytes, records: bytes, grp_type: int = 0) -> bytes:
    """Helper to wrap records inside a Skyrim GRUP."""
    return b"GRUP" + struct.pack("<I4siII", 24 + len(records), label, grp_type, 0, 0) + records


def make_tes4_header(masters: list[str] = (), flags: int = 0) -> bytes:
    """Helper to build a TES4 header record with declared MAST subrecords and flags."""
    body = b""
    for m in masters:
        body += make_subrecord(b"MAST", m.encode("utf-8") + b"\x00")
        body += make_subrecord(b"DATA", struct.pack("<Q", 0))
    return make_record(b"TES4", 0, body, flags=flags)


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


def test_free_translator_glossary(monkeypatch):
    import io
    import json
    import urllib.parse
    import urllib.request

    assert translate_free_text_sync("") == ""
    assert translate_free_text_sync("   ") == "   "

    class MockResponse:
        def __init__(self, data: bytes):
            self._data = io.BytesIO(data)

        def read(self) -> bytes:
            return self._data.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        parsed = urllib.parse.urlparse(url)
        q_param = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
        translated = f"El {q_param} en el reino."
        payload = [[[translated, q_param, None, None, 0]]]
        return MockResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    result = translate_free_text_sync("The Dragonborn travels to Whiterun to meet the Jarl.")
    assert "Sangre de Dragón" in result
    assert "Carrera Blanca" in result
    assert "Jarl" in result


def test_free_translator_error_propagation(monkeypatch):
    import urllib.error
    import urllib.request

    import pytest

    def mock_urlopen_fail(req, timeout=10):
        raise urllib.error.URLError("Simulated network timeout")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_fail)
    with pytest.raises(RuntimeError, match="Fallo del traductor gratuito"):
        translate_free_text_sync("The Dragonborn arrives.")


def test_free_translator_language_glossary_isolation():
    """Validates that non-Spanish languages preserve canonical lore names without inserting Spanish glossary words."""
    assert _resolve_lang_code("french") == "fr"
    assert _resolve_lang_code("German") == "de"
    assert _resolve_lang_code("italian") == "it"
    assert _resolve_lang_code("spanish") == "es"

    # French: must NOT insert "Sangre de Dragón" or "Carrera Blanca"
    _french_text, french_repl = _protect_glossary("The Dragonborn arrived at Whiterun.", target_lang="French")
    for _placeholder, term in french_repl.items():
        assert term in {"Dragonborn", "Whiterun"}
        assert term not in {"Sangre de Dragón", "Carrera Blanca"}

    # German: must NOT insert Spanish
    _german_text, german_repl = _protect_glossary("The Jarl of Windhelm spoke.", target_lang="German")
    for _placeholder, term in german_repl.items():
        assert term in {"Jarl", "Windhelm"}
        assert term not in {"Ventalia"}

    # Spanish: MUST insert Spanish lore terms
    _es_text, es_repl = _protect_glossary("The Dragonborn arrived at Whiterun.", target_lang="Spanish")
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
        make_subrecord(b"EDID", b"LydiaNPC\x00")
        + make_subrecord(b"FULL", b"Lydia\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00010001))
    )
    npc_rec = make_record(b"NPC_", 0x00020002, npc_body)

    # 3. INFO record: FormID 0x00030003 with ANAM 0x00020002 (Lydia) and NAM1 dialogue text
    text = b"I am sworn to carry your burdens.\x00"
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x00020002)) + make_subrecord(b"NAM1", text)
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
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))
    )
    npc_rec = make_record(b"NPC_", 0x0001A697, npc_body)
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # 2. Create target mod: WhiterunQuest.esp declaring MAST Skyrim.esm
    mod_esp = tmp_path / "WhiterunQuest.esp"
    info_text = b"Whiterun stands strong with the Empire.\x00"
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) + make_subrecord(b"NAM1", info_text)
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
        make_subrecord(b"EDID", b"UpdateGuardNPC\x00")
        + make_subrecord(b"FULL", b"Update Guard\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8))  # points to Skyrim.esm:0x013AD8
    )
    npc_rec = make_record(b"NPC_", 0x01000999, npc_body)
    update_esm.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", npc_rec))

    # 3. Target Plugin: MyMod.esp (declares Skyrim.esm as #0 and Update.esm as #1)
    mymod_esp = tmp_path / "MyMod.esp"
    info_body = (
        make_subrecord(b"ANAM", struct.pack("<I", 0x01000999))  # points to Update.esm:0x000999
        + make_subrecord(b"NAM1", b"I received new orders from the capital.\x00")
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
        make_subrecord(b"EDID", b"SeraphinaNPC\x00")
        + make_subrecord(b"FULL", b"Seraphina\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00005001))
    )
    npc_rec = make_record(b"NPC_", 0x00007002, npc_body)
    custom_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # 3. Target plugin in tmp_path (different folder), passing master_search_paths
    target_esp = tmp_path / "TargetMod.esp"
    # ANAM has high byte 0x01 pointing to CustomMaster.esm (master index 1)
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x01007002)) + make_subrecord(
        b"NAM1", b"Care to have a drink with me?\x00"
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
        make_subrecord(b"EDID", b"Alice\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000001)),
    )
    master_a.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_a + npc_a))

    # MasterB has NPC 0x001234 -> VoiceType "MaleBrute"
    master_b = tmp_path / "MasterB.esm"
    vtyp_b = make_record(b"VTYP", 0x00000002, make_subrecord(b"EDID", b"MaleBrute\x00"))
    npc_b = make_record(
        b"NPC_",
        0x00001234,
        make_subrecord(b"EDID", b"Bob\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000002)),
    )
    master_b.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_b + npc_b))

    # Target mod declaring masters [MasterA.esm, MasterB.esm]
    target_esp = tmp_path / "CollisionMod.esp"
    # Line 1 spoken by MasterA NPC (mod_index 0)
    info_a = make_record(
        b"INFO",
        0x02000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00001234))
        + make_subrecord(b"NAM1", b"I am Alice from MasterA.\x00"),
    )
    # Line 2 spoken by MasterB NPC (mod_index 1)
    info_b = make_record(
        b"INFO",
        0x02000002,
        make_subrecord(b"ANAM", struct.pack("<I", 0x01001234)) + make_subrecord(b"NAM1", b"I am Bob from MasterB.\x00"),
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
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) + make_subrecord(
        b"NAM1", b"Where is my master file?\x00"
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
        make_subrecord(b"EDID", b"LocalGuard\x00")
        + make_subrecord(b"FULL", b"Local Guard\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x01000111)),
    )
    local_vtyp = make_record(b"VTYP", 0x01000111, make_subrecord(b"EDID", b"MaleGuard\x00"))

    # INFO referencing invalid mod_index 0x08 (0x08000555)
    info_rec = make_record(
        b"INFO",
        0x01000999,
        make_subrecord(b"ANAM", struct.pack("<I", 0x08000555))
        + make_subrecord(b"NAM1", b"I have an invalid index.\x00"),
    )

    mod_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", local_vtyp + local_npc + info_rec))

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
        make_subrecord(b"EDID", b"ElfNPC\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000010)),
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
        make_subrecord(b"ANAM", struct.pack("<I", 0x00000020))
        + make_subrecord(b"NAM1", b"Testing read-only access.\x00"),
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
        make_subrecord(b"EDID", b"Commander\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000005)),
    )
    master_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # Build 500 INFO records in target mod
    info_recs = b""
    for i in range(500):
        info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x00000006)) + make_subrecord(
            b"NAM1", f"Order number {i}\x00".encode()
        )
        info_recs += make_record(b"INFO", 0x01000000 + i, info_body)

    mod_esp = tmp_path / "BigQuest.esp"
    mod_esp.write_bytes(make_tes4_header(["CachedMaster.esm"]) + make_grup(b"INFO", info_recs))

    # Instrument MasterResolver.find_master_file and get_or_load_master
    orig_find_master = MasterResolver.find_master_file
    orig_get_or_load = MasterResolver.get_or_load_master
    discovery_scan_count = 0
    disk_parse_count = 0

    def instrumented_find_master(self, master_name, origin_dir):
        nonlocal discovery_scan_count
        cache_key = (origin_dir.resolve(), master_name.lower())
        if cache_key not in self._path_cache:
            discovery_scan_count += 1
        return orig_find_master(self, master_name, origin_dir)

    def instrumented_get_or_load(self, master_name, origin_dir):
        nonlocal disk_parse_count
        master_file = self.find_master_file(master_name, origin_dir)
        if master_file and master_file.resolve() not in self._cache:
            disk_parse_count += 1
        return orig_get_or_load(self, master_name, origin_dir)

    monkeypatch.setattr(MasterResolver, "find_master_file", instrumented_find_master)
    monkeypatch.setattr(MasterResolver, "get_or_load_master", instrumented_get_or_load)

    entries = parse_esp_file(mod_esp)
    assert len(entries) == 500
    assert discovery_scan_count == 1, f"Expected exactly 1 master discovery scan, got {discovery_scan_count}"
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
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0xFE001001)) + make_subrecord(
        b"NAM1", b"Spoken by a light plugin NPC.\x00"
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
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8)),
    )
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_skyrim + npc_skyrim))

    # 2. Patch.esm (Intermediate master with override for 0x0001A697)
    patch_esm = tmp_path / "Patch.esm"
    vtyp_patch = make_record(b"VTYP", 0x01013ADA, make_subrecord(b"EDID", b"MaleBrute\x00"))
    npc_patch_override = make_record(
        b"NPC_",
        0x0001A697,  # mod_index 0 -> points to Skyrim.esm:0x01A697
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf (Patched)\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x01013ADA)),
    )
    patch_esm.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", vtyp_patch + npc_patch_override))

    # 3. Target mod declaring Skyrim.esm and Patch.esm
    target_esp = tmp_path / "TargetMod.esp"
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) + make_subrecord(
        b"NAM1", b"I speak with origin strength.\x00"
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
        make_subrecord(b"EDID", b"BaseTemplateNPC\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00010001)),
    )

    # 3. Instance NPC: FormID 0x00020002 with TPLT 0x00020001 (NO direct VTCK)
    instance_npc = make_record(
        b"NPC_",
        0x00020002,
        make_subrecord(b"EDID", b"InheritedNPC\x00")
        + make_subrecord(b"FULL", b"Inherited Citizen\x00")
        + make_subrecord(b"TPLT", struct.pack("<I", 0x00020001)),
    )

    # 4. INFO record spoken by Instance NPC
    info_rec = make_record(
        b"INFO",
        0x00030001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00020002))
        + make_subrecord(b"NAM1", b"I inherited my voice from a template.\x00"),
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
        make_subrecord(b"EDID", b"MasterBaseTemplate\x00") + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8)),
    )
    master_a.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"NPC_", base_npc))

    # 3. TargetMod.esp with NPC pointing via TPLT to MasterA.esm:0x01000100
    target_esp = tmp_path / "TargetMod.esp"
    mod_npc = make_record(
        b"NPC_",
        0x02000200,
        make_subrecord(b"EDID", b"ModSoldier\x00")
        + make_subrecord(b"FULL", b"Mod Soldier\x00")
        + make_subrecord(b"TPLT", struct.pack("<I", 0x01000100)),  # mod_index 1 -> MasterA.esm
    )
    info_rec = make_record(
        b"INFO",
        0x02000300,
        make_subrecord(b"ANAM", struct.pack("<I", 0x02000200)) + make_subrecord(b"NAM1", b"Ready for battle!\x00"),
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
        make_subrecord(b"EDID", b"CyclicA\x00")
        + make_subrecord(b"FULL", b"Cyclic Actor A\x00")
        + make_subrecord(b"TPLT", struct.pack("<I", 0x00010002)),
    )

    # NPC B (0x00010002) -> TPLT NPC A (0x00010001)
    npc_b = make_record(
        b"NPC_",
        0x00010002,
        make_subrecord(b"EDID", b"CyclicB\x00")
        + make_subrecord(b"FULL", b"Cyclic Actor B\x00")
        + make_subrecord(b"TPLT", struct.pack("<I", 0x00010001)),
    )

    # INFO spoken by NPC A
    info_rec = make_record(
        b"INFO",
        0x00010003,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00010001))
        + make_subrecord(b"NAM1", b"I am stuck in an infinite template loop.\x00"),
    )

    esp_path.write_bytes(make_tes4_header() + make_grup(b"NPC_", npc_a + npc_b + info_rec))

    entries = parse_esp_file(esp_path)
    dialog_entry = next(e for e in entries if e.is_dialog)
    assert dialog_entry.voice_type is None
    assert dialog_entry.actor == "Cyclic Actor A"


def test_esp_parser_localized_plugin_stringid_guard(tmp_path):
    """
    Test 15 (Localized Master StringID Guard):
    When a master has FLAG_LOCALIZED (0x80) set in its TES4 header (as in vanilla Skyrim.esm),
    subrecords like FULL contain 4-byte uint32 StringIDs referencing external .STRINGS tables,
    not raw inline text.
    The parser must NOT treat 4-byte printable values as actor text, falling back safely
    to EDID (if present) or Actor_<FormID>.
    """
    FLAG_LOCALIZED = 0x00000080

    # 1. Localized master with NPC having 4-byte ASCII FULL (e.g. b"HERO" -> StringID 0x4F524548) and EDID
    master_path = tmp_path / "LocalizedMaster.esm"
    vtyp_rec = make_record(b"VTYP", 0x00000001, make_subrecord(b"EDID", b"MaleCommander\x00"))

    # NPC 1: FULL is 4 printable bytes (b"HERO"), EDID is "GuardCommander"
    npc1 = make_record(
        b"NPC_",
        0x00000010,
        make_subrecord(b"EDID", b"GuardCommander\x00")
        + make_subrecord(b"FULL", b"HERO")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00000001)),
    )

    # NPC 2: FULL is 4 printable bytes (b"KING"), NO EDID
    npc2 = make_record(
        b"NPC_", 0x00000020, make_subrecord(b"FULL", b"KING") + make_subrecord(b"VTCK", struct.pack("<I", 0x00000001))
    )

    master_path.write_bytes(make_tes4_header([], flags=FLAG_LOCALIZED) + make_grup(b"NPC_", vtyp_rec + npc1 + npc2))

    # 2. Target mod referencing the NPCs in the localized master
    esp_path = tmp_path / "MyMod.esp"
    info1 = make_record(
        b"INFO",
        0x01000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00000010)) + make_subrecord(b"NAM1", b"Order from commander.\x00"),
    )
    info2 = make_record(
        b"INFO",
        0x01000002,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00000020)) + make_subrecord(b"NAM1", b"Royal decree.\x00"),
    )

    esp_path.write_bytes(make_tes4_header(["LocalizedMaster.esm"]) + make_grup(b"INFO", info1 + info2))

    entries = parse_esp_file(esp_path)
    dialog1 = next(e for e in entries if e.form_id == "01000001")
    dialog2 = next(e for e in entries if e.form_id == "01000002")

    # NPC 1: should use EDID "GuardCommander", NOT raw 4-byte StringID "HERO"
    assert dialog1.actor == "GuardCommander"
    assert dialog1.voice_type == "MaleCommander"

    # NPC 2: without EDID, should fall back to Actor_00000020, NOT raw 4-byte StringID "KING"
    assert dialog2.actor == "Actor_00000020"
    assert dialog2.voice_type == "MaleCommander"


def test_esp_parser_missing_master_repeated_warning_suppression(tmp_path, caplog, monkeypatch):
    """
    Test 16 (Missing Master Warning Suppression & Negative Cache):
    When a mod contains 500 dialogue records referencing an absent master,
    the resolver must:
      - Perform exactly 1 filesystem discovery scan for the missing master.
      - Emit exactly 1 missing-master warning in logs (suppressing 499 duplicate warnings).
      - Gracefully set voice_type=None on all entries without raising any exception.
    """
    import logging

    # Build 500 INFO records in target mod pointing to an NPC in MissingMaster.esm
    info_recs = b""
    for i in range(500):
        info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x00010001)) + make_subrecord(
            b"NAM1", f"Missing master line {i}\x00".encode()
        )
        info_recs += make_record(b"INFO", 0x01000000 + i, info_body)

    mod_esp = tmp_path / "ModWithMissingMaster.esp"
    mod_esp.write_bytes(make_tes4_header(["MissingMaster.esm"]) + make_grup(b"INFO", info_recs))

    orig_find_master = MasterResolver.find_master_file
    discovery_scan_count = 0

    def instrumented_find_master(self, master_name, origin_dir):
        nonlocal discovery_scan_count
        cache_key = (origin_dir.resolve(), master_name.lower())
        if cache_key not in self._path_cache:
            discovery_scan_count += 1
        return orig_find_master(self, master_name, origin_dir)

    monkeypatch.setattr(MasterResolver, "find_master_file", instrumented_find_master)

    with caplog.at_level(logging.WARNING):
        entries = parse_esp_file(mod_esp)

    assert len(entries) == 500
    assert discovery_scan_count == 1, f"Expected 1 discovery scan, got {discovery_scan_count}"

    missing_warnings = [
        rec.message
        for rec in caplog.records
        if "missingmaster.esm" in rec.message.lower() and "could not be found" in rec.message
    ]
    assert len(missing_warnings) == 1, f"Expected exactly 1 missing master warning, got {len(missing_warnings)}"

    for e in entries:
        assert e.voice_type is None
        assert e.actor == "Actor_00010001"


def test_esp_parser_target_plugin_master_npc_override(tmp_path):
    """
    Test 17 (Target-Plugin Master Override):
    When the target plugin being parsed overrides an NPC record originally defined in a master file
    (e.g. overriding Skyrim.esm:0x0001A697 to have a new VoiceType and Actor Name),
    the resolver MUST query the target plugin's own override first before falling back to the master.
    """
    skyrim_dir = tmp_path / "Data"
    skyrim_dir.mkdir()

    # 1. Skyrim.esm with vanilla VoiceTypes and vanilla Balgruuf
    skyrim_esm = skyrim_dir / "Skyrim.esm"
    vtyp_male = make_record(b"VTYP", 0x00013AD8, make_subrecord(b"EDID", b"MaleCommander\x00"))
    vtyp_female = make_record(b"VTYP", 0x00013AD9, make_subrecord(b"EDID", b"FemaleSultry\x00"))
    vanilla_balgruuf = make_record(
        b"NPC_",
        0x0001A697,
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8)),
    )
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_male + vtyp_female + vanilla_balgruuf))

    # 2. TargetMod.esp with an override of 0x0001A697 (mod_index 0 = Skyrim.esm)
    # Changed to FemaleSultry (0x00013AD9) and "Jarl Balgruuf Reborn"
    target_mod = tmp_path / "TargetMod.esp"
    balgruuf_override = make_record(
        b"NPC_",
        0x0001A697,  # mod_index 0 -> Skyrim.esm
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf Reborn\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD9)),
    )
    info_rec = make_record(
        b"INFO",
        0x01000100,
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) + make_subrecord(b"NAM1", b"I have been reborn.\x00"),
    )
    target_mod.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", balgruuf_override + info_rec))

    entries = parse_esp_file(target_mod, master_search_paths=[skyrim_dir])
    dialog = next(e for e in entries if e.is_dialog)

    # Must resolve to the target plugin's own override, NOT the vanilla master copy!
    assert dialog.actor == "Jarl Balgruuf Reborn"
    assert dialog.voice_type == "FemaleSultry"


def test_esp_parser_corrupt_master_negative_cache(tmp_path, monkeypatch):
    """
    Test 18 (Corrupt/Invalid Master Negative Cache):
    When a master file exists on disk but is unreadable or has a corrupt header,
    the resolver must cache the failure negatively, attempting to read/validate it exactly ONCE
    even when 500 dialogue records reference it.
    """
    master_dir = tmp_path / "Data"
    master_dir.mkdir()
    corrupt_master = master_dir / "CorruptMaster.esm"
    corrupt_master.write_bytes(b"INVALID_HEADER_GARBAGE_BYTES_1234567890")

    info_recs = b""
    for i in range(500):
        info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x00010001)) + make_subrecord(
            b"NAM1", f"Corrupt master line {i}\x00".encode()
        )
        info_recs += make_record(b"INFO", 0x01000000 + i, info_body)

    mod_esp = tmp_path / "ModWithCorruptMaster.esp"
    mod_esp.write_bytes(make_tes4_header(["CorruptMaster.esm"]) + make_grup(b"INFO", info_recs))

    orig_open = open
    open_count = 0

    def instrumented_open(file, *args, **kwargs):
        nonlocal open_count
        if "CorruptMaster.esm" in str(file):
            open_count += 1
        return orig_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", instrumented_open)

    entries = parse_esp_file(mod_esp, master_search_paths=[master_dir])
    assert len(entries) == 500
    assert open_count == 1, f"Expected exactly 1 read attempt for corrupt master, got {open_count}"
    for e in entries:
        assert e.voice_type is None


def test_esp_parser_warning_dedup_esl_and_invalid_index(tmp_path, caplog):
    """
    Test 19 (Warning Deduplication for ESL & Invalid Master Index):
    When a plugin contains hundreds of identical ESL FormIDs (0xFE...) or out-of-bounds master indexes,
    warnings must be deduplicated so logs are not flooded with 500 identical warning messages.
    """
    import logging

    # 500 ESL dialogs + 500 Invalid Index dialogs
    info_recs = b""
    for i in range(500):
        info_esl = make_subrecord(b"ANAM", struct.pack("<I", 0xFE001001)) + make_subrecord(
            b"NAM1", f"ESL line {i}\x00".encode()
        )
        info_invalid = make_subrecord(b"ANAM", struct.pack("<I", 0x09001001)) + make_subrecord(
            b"NAM1", f"Invalid index line {i}\x00".encode()
        )
        info_recs += make_record(b"INFO", 0x01000000 + i, info_esl)
        info_recs += make_record(b"INFO", 0x01001000 + i, info_invalid)

    mod_esp = tmp_path / "ModWithSpamFormIDs.esp"
    mod_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", info_recs))

    with caplog.at_level(logging.WARNING):
        entries = parse_esp_file(mod_esp)

    assert len(entries) == 1000

    esl_warnings = [rec.message for rec in caplog.records if "ESL/light plugin FormID" in rec.message]
    invalid_warnings = [rec.message for rec in caplog.records if "invalid master index" in rec.message]

    assert len(esl_warnings) == 1, f"Expected 1 deduplicated ESL warning, got {len(esl_warnings)}"
    assert len(invalid_warnings) == 1, f"Expected 1 deduplicated invalid index warning, got {len(invalid_warnings)}"


def test_esp_parser_localized_target_safety(tmp_path, caplog):
    """
    Test 20 (Localized Target Safety):
    When a target plugin has FLAG_LOCALIZED enabled in its TES4 header,
    subrecords contain binary 4-byte uint32 StringIDs referencing external .STRINGS tables.
    The parser must NOT treat these StringIDs as translatable text inline, and must emit
    a clear warning that localized string tables are unsupported.
    """
    import logging

    FLAG_LOCALIZED = 0x00000080

    mod_esp = tmp_path / "LocalizedPlugin.esp"
    # Create an INFO record where NAM1 is 4 bytes binary StringID 0x00010A3B
    info_body = make_subrecord(b"ANAM", struct.pack("<I", 0x00010001)) + make_subrecord(
        b"NAM1", struct.pack("<I", 0x00010A3B)
    )
    info_rec = make_record(b"INFO", 0x01000001, info_body)
    mod_esp.write_bytes(make_tes4_header([], flags=FLAG_LOCALIZED) + make_grup(b"INFO", info_rec))

    with caplog.at_level(logging.WARNING):
        entries = parse_esp_file(mod_esp)

    # Must NOT emit the 4-byte StringID as translatable text
    assert len(entries) == 0

    localized_warnings = [rec.message for rec in caplog.records if "FLAG_LOCALIZED" in rec.message]
    assert len(localized_warnings) >= 1


def test_esp_parser_isolated_job_skyrim_data_resolution(tmp_path):
    """
    Test 21 (Skyrim Data Path in Isolated Job Directory):
    Simulates a plugin copied to an isolated job directory (e.g. output/jobs/<uuid>/Mod.esp)
    resolving Skyrim.esm via the explicit master_search_paths pointing to Skyrim's Data directory.
    """
    data_dir = tmp_path / "SkyrimData"
    data_dir.mkdir()
    skyrim_esm = data_dir / "Skyrim.esm"
    vtyp_rec = make_record(b"VTYP", 0x00013AD8, make_subrecord(b"EDID", b"MaleCommander\x00"))
    npc_rec = make_record(
        b"NPC_",
        0x0001A697,
        make_subrecord(b"EDID", b"JarlBalgruuf\x00")
        + make_subrecord(b"FULL", b"Jarl Balgruuf\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00013AD8)),
    )
    skyrim_esm.write_bytes(make_tes4_header() + make_grup(b"NPC_", vtyp_rec + npc_rec))

    job_dir = tmp_path / "output" / "jobs" / "12345"
    job_dir.mkdir(parents=True)
    job_esp = job_dir / "CopiedMod.esp"
    info_rec = make_record(
        b"INFO",
        0x01000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697))
        + make_subrecord(b"NAM1", b"Greetings from the Jarl.\x00"),
    )
    job_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", info_rec))

    entries = parse_esp_file(job_esp, master_search_paths=[data_dir])
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.actor == "Jarl Balgruuf"
    assert dialog.voice_type == "MaleCommander"


def test_esp_parser_dialogue_hierarchy_t1_basic(tmp_path):
    """
    T1: QUST + DIAL + INFO in single plugin.
    Verifies that INFO StringEntry receives correct quest_edid and topic_edid.
    """
    esp_path = tmp_path / "TG00Quest.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"TG00\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"TG00Brynjolf\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_body = make_subrecord(b"TRDT", bytes([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0])) + make_subrecord(
        b"NAM1", b"Never done an honest day's work, eh?\x00"
    )
    info_rec = make_record(b"INFO", 0x000136C9, info_body)
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + topic_grup)

    entries = parse_esp_file(esp_path)
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.quest_edid == "TG00"
    assert dialog.topic_edid == "TG00Brynjolf"
    assert dialog.defining_plugin == "TG00Quest.esp"
    assert dialog.local_object_id == 0x0136C9
    assert dialog.string_index == 1


def test_esp_parser_dialogue_hierarchy_t2_one_quest_two_topics(tmp_path):
    """
    T2: One QUST with two DIAL records.
    Verifies that INFO records under each topic map to their respective topic_edid and shared quest_edid.
    """
    esp_path = tmp_path / "MultiTopic.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"MQ101\x00"))
    dial_a = make_record(
        b"DIAL",
        0x00002001,
        make_subrecord(b"EDID", b"MQ101RalofTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    dial_b = make_record(
        b"DIAL",
        0x00002002,
        make_subrecord(b"EDID", b"MQ101HadvarTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_a = make_record(
        b"INFO",
        0x00003001,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Hey you, you're finally awake.\x00"),
    )
    info_b = make_record(
        b"INFO",
        0x00003002,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Who are you? Step forward.\x00"),
    )

    grup_a = make_grup(struct.pack("<I", 0x00002001), info_a, grp_type=7)
    grup_b = make_grup(struct.pack("<I", 0x00002002), info_b, grp_type=7)

    esp_path.write_bytes(
        make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_a + dial_b) + grup_a + grup_b
    )

    entries = parse_esp_file(esp_path)
    dialogs = [e for e in entries if e.is_dialog]
    assert len(dialogs) == 2

    entry_a = next(d for d in dialogs if d.form_id == "00003001")
    entry_b = next(d for d in dialogs if d.form_id == "00003002")

    assert entry_a.quest_edid == "MQ101"
    assert entry_a.topic_edid == "MQ101RalofTopic"

    assert entry_b.quest_edid == "MQ101"
    assert entry_b.topic_edid == "MQ101HadvarTopic"


def test_esp_parser_dialogue_hierarchy_t3_one_topic_multiple_infos(tmp_path):
    """
    T3: One DIAL with multiple INFO records.
    Verifies that all child INFOs receive the same parent topic and quest.
    """
    esp_path = tmp_path / "SharedTopic.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"FreeformWhiterun\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"WhiterunGuardHello\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info1 = make_record(
        b"INFO",
        0x00003010,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"I used to be an adventurer like you.\x00"),
    )
    info2 = make_record(
        b"INFO",
        0x00003020,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Let me guess, someone stole your sweetroll.\x00"),
    )
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info1 + info2, grp_type=7)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + topic_grup)

    entries = parse_esp_file(esp_path)
    dialogs = [e for e in entries if e.is_dialog]
    assert len(dialogs) == 2
    for d in dialogs:
        assert d.quest_edid == "FreeformWhiterun"
        assert d.topic_edid == "WhiterunGuardHello"
        assert d.defining_plugin == "SharedTopic.esp"


def test_esp_parser_dialogue_hierarchy_t4_multi_response_info(tmp_path):
    """
    T4: Single INFO record with two TRDT/NAM1 response pairs.
    Verifies that both emitted StringEntries preserve identical quest_edid, topic_edid,
    defining_plugin, and local_object_id, but distinct raw string_index values.
    """
    esp_path = tmp_path / "MultiResponse.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"CW01\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"CW01TulliusSpeech\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_body = (
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"First sentence of the speech.\x00")
        + make_subrecord(b"TRDT", bytes([0] * 12 + [2] + [0] * 3))
        + make_subrecord(b"NAM1", b"Second sentence of the speech.\x00")
    )
    info_rec = make_record(b"INFO", 0x00004000, info_body)
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + topic_grup)

    entries = parse_esp_file(esp_path)
    dialogs = [e for e in entries if e.is_dialog]
    assert len(dialogs) == 2

    resp1, resp2 = dialogs[0], dialogs[1]
    assert resp1.quest_edid == "CW01"
    assert resp2.quest_edid == "CW01"
    assert resp1.topic_edid == "CW01TulliusSpeech"
    assert resp2.topic_edid == "CW01TulliusSpeech"
    assert resp1.defining_plugin == "MultiResponse.esp"
    assert resp2.defining_plugin == "MultiResponse.esp"
    assert resp1.local_object_id == 0x004000
    assert resp2.local_object_id == 0x004000
    assert resp1.string_index == 1
    assert resp2.string_index == 2


def test_esp_parser_dialogue_hierarchy_t5_master_override(tmp_path):
    """
    T5: Master-owned INFO override in child .esp.
    Verifies that defining_plugin remains the master plugin, and quest_edid/topic_edid
    are resolved across the master index.
    """
    master_path = tmp_path / "Skyrim.esm"
    qust_rec = make_record(b"QUST", 0x00010000, make_subrecord(b"EDID", b"DialogueWhiterun\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00020000,
        make_subrecord(b"EDID", b"DialogueWhiterunCarlottaIntro\x00")
        + make_subrecord(b"QNAM", struct.pack("<I", 0x00010000)),
    )
    info_rec = make_record(
        b"INFO",
        0x0006497C,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Original English text.\x00"),
    )
    master_path.write_bytes(
        make_tes4_header()
        + make_grup(b"QUST", qust_rec)
        + make_grup(b"DIAL", dial_rec)
        + make_grup(struct.pack("<I", 0x00020000), info_rec, grp_type=7)
    )

    child_path = tmp_path / "CarlottaSpanishPatch.esp"
    # Child overrides the INFO FormID 0x0006497C (master index 0 -> 0x0006497C)
    override_body = make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3)) + make_subrecord(
        b"NAM1", b"Texto traducido en espanol.\x00"
    )
    override_rec = make_record(b"INFO", 0x0006497C, override_body)
    override_grup = make_grup(struct.pack("<I", 0x00020000), override_rec, grp_type=7)

    child_path.write_bytes(make_tes4_header(["Skyrim.esm"]) + override_grup)

    entries = parse_esp_file(child_path, master_search_paths=[tmp_path])
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.defining_plugin == "Skyrim.esm"
    assert dialog.local_object_id == 0x06497C
    assert dialog.quest_edid == "DialogueWhiterun"
    assert dialog.topic_edid == "DialogueWhiterunCarlottaIntro"
    assert dialog.string_index == 1


# --- TES5 TOPIC CHILDREN GROUP REGRESSION TESTS (T-GRUP-1 to T-GRUP-5) ---


def test_tes5_topic_children_group_type_7_association(tmp_path):
    """
    T-GRUP-1: Proves that TES5 Topic Children GRUP with group_type=7 and label=DIAL.FormID
    correctly associates child INFO records with the DIAL's topic_edid and parent quest_edid.
    """
    esp_path = tmp_path / "Grup7Test.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"MyQuest\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"MyTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_rec = make_record(
        b"INFO",
        0x00003000,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Hello from group type 7.\x00"),
    )
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + topic_grup)

    entries = parse_esp_file(esp_path)
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.topic_edid == "MyTopic"
    assert dialog.quest_edid == "MyQuest"


def test_tes5_group_type_5_not_interpreted_as_topic_children(tmp_path):
    """
    T-GRUP-2: Proves that GRUP type 5 (Exterior Cell Sub-Block in TES5) is NOT interpreted
    as Topic Children. If an INFO is enclosed in a type 5 group, topic_edid must remain None.
    """
    esp_path = tmp_path / "Grup5Test.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"MyQuest\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"MyTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_rec = make_record(
        b"INFO",
        0x00003000,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Orphaned line in type 5 group.\x00"),
    )
    # Group type 5 (Exterior Cell Sub-Block)
    grup_type_5 = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=5)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + grup_type_5)

    entries = parse_esp_file(esp_path)
    dialog = next(e for e in entries if e.is_dialog)
    # Must NOT associate with MyTopic because grp_type=5 is Exterior Cell Sub-Block
    assert dialog.topic_edid is None
    assert dialog.quest_edid is None


def test_tes5_two_type_7_groups_no_parent_leak(tmp_path):
    """
    T-GRUP-3: Proves that two consecutive type-7 groups do not leak parent context to each other.
    """
    esp_path = tmp_path / "GrupLeakTest.esp"
    qust1 = make_record(b"QUST", 0x00001001, make_subrecord(b"EDID", b"QuestOne\x00"))
    qust2 = make_record(b"QUST", 0x00001002, make_subrecord(b"EDID", b"QuestTwo\x00"))
    dial1 = make_record(
        b"DIAL",
        0x00002001,
        make_subrecord(b"EDID", b"TopicOne\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001001)),
    )
    dial2 = make_record(
        b"DIAL",
        0x00002002,
        make_subrecord(b"EDID", b"TopicTwo\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001002)),
    )
    info1 = make_record(
        b"INFO",
        0x00003001,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3)) + make_subrecord(b"NAM1", b"Topic one line.\x00"),
    )
    info2 = make_record(
        b"INFO",
        0x00003002,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3)) + make_subrecord(b"NAM1", b"Topic two line.\x00"),
    )

    grup1 = make_grup(struct.pack("<I", 0x00002001), info1, grp_type=7)
    grup2 = make_grup(struct.pack("<I", 0x00002002), info2, grp_type=7)

    esp_path.write_bytes(
        make_tes4_header() + make_grup(b"QUST", qust1 + qust2) + make_grup(b"DIAL", dial1 + dial2) + grup1 + grup2
    )

    entries = parse_esp_file(esp_path)
    d1 = next(e for e in entries if e.form_id == "00003001")
    d2 = next(e for e in entries if e.form_id == "00003002")

    assert d1.topic_edid == "TopicOne"
    assert d1.quest_edid == "QuestOne"
    assert d2.topic_edid == "TopicTwo"
    assert d2.quest_edid == "QuestTwo"


def test_tes5_type_7_group_master_dial_reference(tmp_path):
    """
    T-GRUP-4: Proves that a type-7 group whose label references a DIAL defined in a master file
    correctly resolves topic_edid and quest_edid across the master index.
    """
    master_path = tmp_path / "Skyrim.esm"
    qust_rec = make_record(b"QUST", 0x00010000, make_subrecord(b"EDID", b"MasterQuest\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00020000,
        make_subrecord(b"EDID", b"MasterTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00010000)),
    )
    master_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec))

    child_path = tmp_path / "ChildMod.esp"
    # Child defines a new INFO under the master's DIAL 0x00020000
    info_rec = make_record(
        b"INFO",
        0x01003000,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"New child line under master topic.\x00"),
    )
    # Topic children group labeled with master's DIAL FormID (master index 0 -> 0x00020000)
    topic_grup = make_grup(struct.pack("<I", 0x00020000), info_rec, grp_type=7)

    child_path.write_bytes(make_tes4_header(["Skyrim.esm"]) + topic_grup)

    entries = parse_esp_file(child_path, master_search_paths=[tmp_path])
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.topic_edid == "MasterTopic"
    assert dialog.quest_edid == "MasterQuest"
    assert dialog.defining_plugin == "ChildMod.esp"


def test_tes5_type_7_group_interleaved_unrelated_records(tmp_path):
    """
    T-GRUP-5: Interleaves unrelated records (NPC_, BOOK) and an
    unrelated DIAL before the Topic Children group, proving that
    INFO identity comes from the type-7 group label rather than
    record proximity or the last DIAL seen.
    """
    esp_path = tmp_path / "InterleavedTest.esp"
    qust_real = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"RealQuest\x00"))
    dial_real = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"RealTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    dial_unrelated = make_record(
        b"DIAL",
        0x00002999,
        make_subrecord(b"EDID", b"UnrelatedProximityTopic\x00")
        + make_subrecord(b"QNAM", struct.pack("<I", 0x00001999)),
    )
    unrelated_npc = make_record(b"NPC_", 0x00005000, make_subrecord(b"EDID", b"DummyNPC\x00"))
    unrelated_book = make_record(
        b"BOOK", 0x00006000, make_subrecord(b"EDID", b"DummyBook\x00") + make_subrecord(b"FULL", b"Book Title\x00")
    )
    info_rec = make_record(
        b"INFO",
        0x00003000,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Strictly associated via GRUP label 0x00002000.\x00"),
    )
    # The topic children group label explicitly points to RealTopic (0x00002000), even though
    # UnrelatedProximityTopic (0x00002999) was declared more recently.
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)

    esp_path.write_bytes(
        make_tes4_header()
        + make_grup(b"QUST", qust_real)
        + make_grup(b"DIAL", dial_real)
        + make_grup(b"NPC_", unrelated_npc)
        + make_grup(b"BOOK", unrelated_book)
        + make_grup(b"DIAL", dial_unrelated)  # Proximity trap
        + topic_grup
    )

    entries = parse_esp_file(esp_path)
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.topic_edid == "RealTopic"
    assert dialog.quest_edid == "RealQuest"
    assert dialog.topic_edid != "UnrelatedProximityTopic"


def test_tes5_nested_dial_topic_children_realistic_layout(tmp_path):
    """
    Authentic nested TES5 dialogue layout fixture:
      GRUP type 0 label="QUST"
        QUST record (0x00001000, EDID "TG00")
      GRUP type 0 label="DIAL"
        DIAL record (0x00002000, EDID "TG00Brynjolf", QNAM 0x00001000)
        GRUP type 7 label=0x00002000 (Topic Children)
          INFO record (0x000136C9, TRDT response=1, NAM1 text)
    """
    esp_path = tmp_path / "NestedLayout.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"TG00\x00"))
    qust_top_grup = make_grup(b"QUST", qust_rec, grp_type=0)

    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"TG00Brynjolf\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_rec = make_record(
        b"INFO",
        0x000136C9,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Never done an honest day's work, eh?\x00"),
    )
    topic_children_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)
    dial_top_grup = make_grup(b"DIAL", dial_rec + topic_children_grup, grp_type=0)

    esp_path.write_bytes(make_tes4_header() + qust_top_grup + dial_top_grup)

    entries = parse_esp_file(esp_path)
    dialogs = [e for e in entries if e.is_dialog]
    assert len(dialogs) == 1
    d = dialogs[0]
    assert d.topic_edid == "TG00Brynjolf"
    assert d.quest_edid == "TG00"
    assert d.string_index == 1
    assert d.defining_plugin == "NestedLayout.esp"
    assert d.local_object_id == 0x0136C9


def test_esp_parser_info_without_anam_yields_none_voice_type(tmp_path):
    """
    Proves that an INFO record without an explicit ANAM speaker subrecord
    yields voice_type is None in StringEntry (boundary for Phase 2).
    """
    esp_path = tmp_path / "NoAnam.esp"
    qust_rec = make_record(b"QUST", 0x00001000, make_subrecord(b"EDID", b"MyQuest\x00"))
    dial_rec = make_record(
        b"DIAL",
        0x00002000,
        make_subrecord(b"EDID", b"MyTopic\x00") + make_subrecord(b"QNAM", struct.pack("<I", 0x00001000)),
    )
    info_rec = make_record(
        b"INFO",
        0x00003000,
        make_subrecord(b"TRDT", bytes([0] * 12 + [1] + [0] * 3))
        + make_subrecord(b"NAM1", b"Generic dialogue line without ANAM.\x00"),
    )
    topic_grup = make_grup(struct.pack("<I", 0x00002000), info_rec, grp_type=7)

    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", qust_rec) + make_grup(b"DIAL", dial_rec) + topic_grup)

    entries = parse_esp_file(esp_path)
    dialog = next(e for e in entries if e.is_dialog)
    assert dialog.voice_type is None
