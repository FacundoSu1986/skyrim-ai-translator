import logging
import struct

import pytest

from src.esp_parser import parse_esp_file
from src.models import StringEntry
from src.translator import translate_entries


def make_subrecord(s_type: bytes, payload: bytes) -> bytes:
    return s_type + struct.pack("<H", len(payload)) + payload


def make_record(rec_type: bytes, form_id: int, body: bytes, flags: int = 0) -> bytes:
    return rec_type + struct.pack("<IIIIHH", len(body), flags, form_id, 0, 44, 0) + body


def make_grup(label: bytes, records: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I4sIII", 24 + len(records), label, 0, 0, 0) + records


def make_tes4_header(masters=()) -> bytes:
    body = b""
    for master in masters:
        body += make_subrecord(b"MAST", master.encode("utf-8") + b"\x00")
        body += make_subrecord(b"DATA", struct.pack("<Q", 0))
    return make_record(b"TES4", 0, body)


def make_trdt(response_number: int) -> bytes:
    # xEdit (Skyrim): Emotion Type u32, Emotion Value u32, unused 4,
    # Response number u8, unused 3, Sound FormID u32,
    # Use Emotion Animation u8, unused 3.
    return struct.pack("<III B 3x I B 3x", 0, 0, 0, response_number, 0, 0)


def test_string_entry_metadata_fields_are_backwards_compatible():
    entry = StringEntry(form_id="00000001", text="Hello")

    assert entry.defining_plugin is None
    assert entry.local_object_id is None
    assert entry.record_type is None
    assert entry.subrecord_type is None
    assert entry.string_index is None
    assert entry.editor_id is None


def test_parser_preserves_local_record_metadata(tmp_path):
    esp_path = tmp_path / "TargetMod.esp"
    book_body = (
        make_subrecord(b"EDID", b"MyAncientBook\x00")
        + make_subrecord(b"FULL", b"Ancient Book\x00")
    )
    book = make_record(b"BOOK", 0x00000123, book_body)
    esp_path.write_bytes(make_tes4_header() + make_grup(b"BOOK", book))

    entries = parse_esp_file(esp_path)
    entry = next(e for e in entries if e.text == "Ancient Book")

    assert entry.form_id == "00000123"
    assert entry.defining_plugin == "TargetMod.esp"
    assert entry.local_object_id == 0x000123
    assert entry.record_type == "BOOK"
    assert entry.subrecord_type == "FULL"
    assert entry.string_index is None
    assert entry.editor_id == "MyAncientBook"


def test_parser_preserves_master_origin_for_target_override(tmp_path):
    esp_path = tmp_path / "TargetMod.esp"
    book_body = (
        make_subrecord(b"EDID", b"OverriddenBook\x00")
        + make_subrecord(b"FULL", b"Overridden Skyrim Book\x00")
    )
    # Master index 0 -> Skyrim.esm. Physically present in TargetMod.esp,
    # canonically defined by Skyrim.esm.
    book = make_record(b"BOOK", 0x0001A697, book_body)
    esp_path.write_bytes(
        make_tes4_header(["Skyrim.esm"]) + make_grup(b"BOOK", book)
    )

    entries = parse_esp_file(esp_path)
    entry = next(e for e in entries if e.text == "Overridden Skyrim Book")

    assert entry.defining_plugin == "Skyrim.esm"
    assert entry.local_object_id == 0x01A697
    assert entry.record_type == "BOOK"
    assert entry.subrecord_type == "FULL"


def test_parser_preserves_multiple_strings_from_same_record(tmp_path):
    esp_path = tmp_path / "Books.esp"
    book = make_record(
        b"BOOK",
        0x00000111,
        make_subrecord(b"FULL", b"Title\x00")
        + make_subrecord(b"DESC", b"Body text\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"BOOK", book))

    entries = [e for e in parse_esp_file(esp_path) if e.form_id == "00000111"]

    assert [(e.subrecord_type, e.text) for e in entries] == [
        ("FULL", "Title"),
        ("DESC", "Body text"),
    ]
    assert {e.local_object_id for e in entries} == {0x111}


def test_parser_info_nam1_uses_real_trdt_response_number(tmp_path):
    esp_path = tmp_path / "Dialog.esp"
    info = make_record(
        b"INFO",
        0x00000333,
        make_subrecord(b"TRDT", make_trdt(0))
        + make_subrecord(b"NAM1", b"First response\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", info))

    responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].text == "First response"
    assert responses[0].string_index == 0
    assert responses[0].record_type == "INFO"
    assert responses[0].subrecord_type == "NAM1"


def test_parser_multi_response_emission_deferred_until_consumer_update(tmp_path):
    """Regression guard for the temporary cardinality freeze.

    PR #5 keeps the pre-PR emission shape: at most one entry per
    (form_id, subrecord), so a multi-response INFO record emits only its
    first NAM1, carrying that response's real TRDT index. Multi-response
    emission keyed by string_index is deferred to PR #6, which will update
    the form_id-keyed consumers (dsd_exporter.py, tts_generator.py)
    atomically.
    """
    esp_path = tmp_path / "MultiResponse.esp"
    info = make_record(
        b"INFO",
        0x00000333,
        make_subrecord(b"TRDT", make_trdt(0))
        + make_subrecord(b"NAM1", b"First response\x00")
        + make_subrecord(b"TRDT", make_trdt(4))
        + make_subrecord(b"NAM1", b"Second response\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", info))

    responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].text == "First response"
    assert responses[0].string_index == 0


def test_parser_single_emitted_response_keeps_actor_and_voice_resolution(tmp_path):
    esp_path = tmp_path / "LydiaDialog.esp"
    vtyp = make_record(
        b"VTYP",
        0x00010001,
        make_subrecord(b"EDID", b"FemaleCommander\x00"),
    )
    npc = make_record(
        b"NPC_",
        0x00020002,
        make_subrecord(b"EDID", b"LydiaNPC\x00")
        + make_subrecord(b"FULL", b"Lydia\x00")
        + make_subrecord(b"VTCK", struct.pack("<I", 0x00010001)),
    )
    info = make_record(
        b"INFO",
        0x00030003,
        make_subrecord(b"ANAM", struct.pack("<I", 0x00020002))
        + make_subrecord(b"TRDT", make_trdt(1))
        + make_subrecord(b"NAM1", b"First line\x00")
        + make_subrecord(b"TRDT", make_trdt(7))
        + make_subrecord(b"NAM1", b"Second line\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", vtyp + npc + info))

    responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].string_index == 1
    assert responses[0].actor == "Lydia"
    assert responses[0].voice_type == "FemaleCommander"


def test_parser_quest_nnam_uses_qobj_objective_index(tmp_path):
    esp_path = tmp_path / "Quest.esp"
    quest = make_record(
        b"QUST",
        0x00000444,
        make_subrecord(b"QOBJ", struct.pack("<H", 10))
        + make_subrecord(b"FNAM", struct.pack("<I", 0))
        + make_subrecord(b"NNAM", b"Find the sword\x00")
        + make_subrecord(b"QOBJ", struct.pack("<H", 50))
        + make_subrecord(b"FNAM", struct.pack("<I", 0))
        + make_subrecord(b"NNAM", b"Return to the Jarl\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", quest))

    objectives = [
        e for e in parse_esp_file(esp_path)
        if e.record_type == "QUST" and e.subrecord_type == "NNAM"
    ]

    # Cardinality freeze: only the first NNAM is emitted until PR #6.
    assert [(e.text, e.string_index) for e in objectives] == [
        ("Find the sword", 10),
    ]


@pytest.mark.asyncio
async def test_translation_preserves_dsd_metadata():
    entry = StringEntry(
        form_id="00000333",
        text="Hello",
        is_dialog=True,
        defining_plugin="Skyrim.esm",
        local_object_id=0x333,
        record_type="INFO",
        subrecord_type="NAM1",
        string_index=4,
        editor_id="SomeInfo",
    )

    async def translate(_text: str, _context: str) -> str:
        return "Hola"

    translated = (
        await translate_entries([entry], target_lang="Spanish", api_callable=translate)
    )[0]

    assert translated.translated_text == "Hola"
    assert translated.form_id == entry.form_id
    assert translated.defining_plugin == entry.defining_plugin
    assert translated.local_object_id == entry.local_object_id
    assert translated.record_type == entry.record_type
    assert translated.subrecord_type == entry.subrecord_type
    assert translated.string_index == entry.string_index
    assert translated.editor_id == entry.editor_id


def test_parser_trdt_too_short_does_not_crash_and_dedupes_warnings(tmp_path, caplog):
    esp_path = tmp_path / "BrokenTRDT.esp"
    info = make_record(
        b"INFO",
        0x00000555,
        make_subrecord(b"TRDT", struct.pack("<I", 0))
        + make_subrecord(b"NAM1", b"Broken response\x00")
        + make_subrecord(b"TRDT", struct.pack("<I", 0))
        + make_subrecord(b"NAM1", b"Broken repeat\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", info))

    with caplog.at_level(logging.WARNING):
        responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].string_index is None

    malformed_trdt = [rec.message for rec in caplog.records if "malformed TRDT" in rec.message]
    assert len(malformed_trdt) == 1

    missing_trdt = [rec.message for rec in caplog.records if "no valid preceding TRDT" in rec.message]
    assert len(missing_trdt) == 1


def test_parser_info_nam1_without_trdt_dedupes_warnings(tmp_path, caplog):
    esp_path = tmp_path / "NoTRDT.esp"
    info = make_record(
        b"INFO",
        0x00000666,
        make_subrecord(b"NAM1", b"Loose response\x00")
        + make_subrecord(b"NAM1", b"Loose repeat\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", info))

    with caplog.at_level(logging.WARNING):
        responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].string_index is None

    nam1_warnings = [rec.message for rec in caplog.records if "no valid preceding TRDT" in rec.message]
    assert len(nam1_warnings) == 1


def test_parser_qobj_too_short_does_not_crash_and_dedupes_warnings(tmp_path, caplog):
    esp_path = tmp_path / "BrokenQOBJ.esp"
    quest = make_record(
        b"QUST",
        0x00000788,
        make_subrecord(b"QOBJ", struct.pack("<B", 0))
        + make_subrecord(b"NNAM", b"Broken objective\x00")
        + make_subrecord(b"QOBJ", struct.pack("<B", 0))
        + make_subrecord(b"NNAM", b"Broken repeat\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", quest))

    with caplog.at_level(logging.WARNING):
        objectives = [
            e for e in parse_esp_file(esp_path)
            if e.record_type == "QUST" and e.subrecord_type == "NNAM"
        ]

    assert len(objectives) == 1
    assert objectives[0].string_index is None

    malformed_qobj = [rec.message for rec in caplog.records if "malformed QOBJ" in rec.message]
    assert len(malformed_qobj) == 1

    missing_qobj = [rec.message for rec in caplog.records if "no valid preceding QOBJ" in rec.message]
    assert len(missing_qobj) == 1


def test_parser_quest_nnam_without_qobj_dedupes_warnings(tmp_path, caplog):
    esp_path = tmp_path / "NoQOBJ.esp"
    quest = make_record(
        b"QUST",
        0x00000777,
        make_subrecord(b"NNAM", b"Objective without QOBJ\x00")
        + make_subrecord(b"NNAM", b"Repeat without QOBJ\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", quest))

    with caplog.at_level(logging.WARNING):
        objectives = [
            e for e in parse_esp_file(esp_path)
            if e.record_type == "QUST" and e.subrecord_type == "NNAM"
        ]

    assert len(objectives) == 1
    assert objectives[0].string_index is None

    nnam_warnings = [rec.message for rec in caplog.records if "no valid preceding QOBJ" in rec.message]
    assert len(nnam_warnings) == 1


def test_parser_empty_nam1_does_not_leak_trdt_index_to_next_nam1(tmp_path, caplog):
    esp_path = tmp_path / "LeakyTRDT.esp"
    info = make_record(
        b"INFO",
        0x00000A01,
        make_subrecord(b"TRDT", make_trdt(3))
        + make_subrecord(b"NAM1", b"")
        + make_subrecord(b"NAM1", b"Real response\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"INFO", info))

    with caplog.at_level(logging.WARNING):
        responses = [e for e in parse_esp_file(esp_path) if e.is_dialog]

    assert len(responses) == 1
    assert responses[0].text == "Real response"
    assert responses[0].string_index is None

    nam1_warnings = [rec.message for rec in caplog.records if "no valid preceding TRDT" in rec.message]
    assert len(nam1_warnings) == 1


def test_parser_whitespace_nnam_does_not_leak_qobj_index_to_next_nnam(tmp_path, caplog):
    esp_path = tmp_path / "LeakyQOBJ.esp"
    quest = make_record(
        b"QUST",
        0x00000A02,
        make_subrecord(b"QOBJ", struct.pack("<H", 7))
        + make_subrecord(b"NNAM", b"   ")
        + make_subrecord(b"NNAM", b"Real objective\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"QUST", quest))

    with caplog.at_level(logging.WARNING):
        objectives = [
            e for e in parse_esp_file(esp_path)
            if e.record_type == "QUST" and e.subrecord_type == "NNAM"
        ]

    assert len(objectives) == 1
    assert objectives[0].text == "Real objective"
    assert objectives[0].string_index is None

    nnam_warnings = [rec.message for rec in caplog.records if "no valid preceding QOBJ" in rec.message]
    assert len(nnam_warnings) == 1


def test_parser_dedupes_accidentally_repeated_same_identity_subrecords(tmp_path):
    esp_path = tmp_path / "DupBook.esp"
    book = make_record(
        b"BOOK",
        0x00000888,
        make_subrecord(b"FULL", b"Duplicate Title\x00")
        + make_subrecord(b"FULL", b"Duplicate Title\x00"),
    )
    esp_path.write_bytes(make_tes4_header() + make_grup(b"BOOK", book))

    entries = [e for e in parse_esp_file(esp_path) if e.form_id == "00000888"]

    assert len(entries) == 1
    assert entries[0].text == "Duplicate Title"
    assert entries[0].subrecord_type == "FULL"
    assert entries[0].string_index is None
