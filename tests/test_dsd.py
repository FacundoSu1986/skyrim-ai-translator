import json
from pathlib import Path

import pytest

from src.dsd_exporter import (
    DSDDuplicateIdentityError,
    DSDMetadataMissingError,
    DSDUnsupportedTypeError,
    export_to_dsd,
    validate_dsd_entries,
)
from src.models import StringEntry


def make_entry(**overrides) -> StringEntry:
    """BOOK FULL target-new entry with complete, valid DSD metadata."""
    base = dict(
        form_id="01000123",
        text="Ancient Book",
        translated_text="Libro antiguo",
        defining_plugin="TargetMod.esp",
        local_object_id=0x000123,
        record_type="BOOK",
        subrecord_type="FULL",
    )
    base.update(overrides)
    return StringEntry(**base)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- A. Root shape -----------------------------------------------------------


def test_dsd_root_is_list_not_dict(tmp_path: Path):
    output_file = tmp_path / "dsd.json"
    export_to_dsd(
        [make_entry(), make_entry(form_id="01000456", local_object_id=0x000456, translated_text="Otro")],
        output_file,
    )
    content = read_json(output_file)
    assert isinstance(content, list)
    assert len(content) == 2


def test_dsd_empty_exportable_set_writes_empty_list(tmp_path: Path):
    output_file = tmp_path / "empty.json"
    export_to_dsd([], output_file)
    assert read_json(output_file) == []


# --- B. Non-indexed types carry no index -------------------------------------


def test_npc_full_is_exported_without_index(tmp_path: Path):
    output_file = tmp_path / "npc.json"
    export_to_dsd(
        [make_entry(record_type="NPC_", subrecord_type="FULL", translated_text="Guardia")],
        output_file,
    )
    (item,) = read_json(output_file)
    assert item["type"] == "NPC_ FULL"
    assert item["string"] == "Guardia"
    assert "index" not in item


# --- C/D. Indexed 1->N survival ----------------------------------------------


def test_two_info_nam1_same_form_id_both_survive(tmp_path: Path):
    output_file = tmp_path / "multi_response.json"
    export_to_dsd(
        [
            make_entry(
                form_id="01000333",
                local_object_id=0x000333,
                record_type="INFO",
                subrecord_type="NAM1",
                string_index=0,
                translated_text="Primera respuesta",
                is_dialog=True,
            ),
            make_entry(
                form_id="01000333",
                local_object_id=0x000333,
                record_type="INFO",
                subrecord_type="NAM1",
                string_index=4,
                translated_text="Segunda respuesta",
                is_dialog=True,
            ),
        ],
        output_file,
    )
    items = read_json(output_file)
    assert len(items) == 2
    by_index = {item["index"]: item for item in items}
    assert set(by_index) == {0, 4}
    for item in items:
        assert item["form_id"] == "0x000333|TargetMod.esp"
        assert item["type"] == "INFO NAM1"
    assert by_index[0]["string"] == "Primera respuesta"
    assert by_index[4]["string"] == "Segunda respuesta"


def test_two_quest_nnam_indices_both_survive(tmp_path: Path):
    output_file = tmp_path / "objectives.json"
    export_to_dsd(
        [
            make_entry(
                form_id="01000444",
                local_object_id=0x000444,
                record_type="QUST",
                subrecord_type="NNAM",
                string_index=10,
                translated_text="Encuentra la espada",
            ),
            make_entry(
                form_id="01000444",
                local_object_id=0x000444,
                record_type="QUST",
                subrecord_type="NNAM",
                string_index=50,
                translated_text="Vuelve con el Jarl",
            ),
        ],
        output_file,
    )
    items = read_json(output_file)
    assert sorted(item["index"] for item in items) == [10, 50]
    assert {item["string"] for item in items} == {"Encuentra la espada", "Vuelve con el Jarl"}


# --- E. Same record, different subrecords ------------------------------------


def test_full_and_desc_of_same_record_do_not_collide(tmp_path: Path):
    output_file = tmp_path / "book.json"
    export_to_dsd(
        [
            make_entry(subrecord_type="FULL", translated_text="Título"),
            make_entry(subrecord_type="DESC", translated_text="Cuerpo del libro"),
        ],
        output_file,
    )
    items = read_json(output_file)
    assert len(items) == 2
    assert {item["type"] for item in items} == {"BOOK FULL", "BOOK DESC"}
    assert all(item["form_id"] == "0x000123|TargetMod.esp" for item in items)


# --- F/G. Defining plugin semantics ------------------------------------------


def test_target_new_record_uses_target_plugin(tmp_path: Path):
    output_file = tmp_path / "new.json"
    export_to_dsd([make_entry()], output_file)
    (item,) = read_json(output_file)
    assert item["form_id"] == "0x000123|TargetMod.esp"


def test_target_override_of_skyrim_uses_defining_plugin_and_local_id(tmp_path: Path):
    output_file = tmp_path / "override.json"
    export_to_dsd(
        [make_entry(form_id="0001A697", defining_plugin="Skyrim.esm", local_object_id=0x01A697)],
        output_file,
    )
    (item,) = read_json(output_file)
    assert item["form_id"] == "0x01A697|Skyrim.esm"


# --- H/I. None vs empty-string translations -----------------------------------


def test_empty_translation_is_exported(tmp_path: Path):
    output_file = tmp_path / "empty_string.json"
    export_to_dsd([make_entry(translated_text="")], output_file)
    (item,) = read_json(output_file)
    assert item["string"] == ""


def test_none_translation_is_omitted_from_export(tmp_path: Path):
    output_file = tmp_path / "partial.json"
    entries = [
        make_entry(translated_text=None),
        make_entry(form_id="01000456", local_object_id=0x000456, translated_text="Traducido"),
    ]
    export_to_dsd(entries, output_file)
    items = read_json(output_file)
    assert len(items) == 1
    assert items[0]["string"] == "Traducido"


def test_preflight_validates_entries_without_translations(tmp_path: Path):
    """The pipeline preflight runs before any translation exists: metadata,
    type, and index checks must apply even when translated_text is None."""
    # Complete, representable, untranslated entry -> preflight passes.
    validate_dsd_entries([make_entry(translated_text=None)])

    # Unrepresentable type -> fails even without a translation.
    with pytest.raises(DSDUnsupportedTypeError):
        validate_dsd_entries([make_entry(translated_text=None, record_type="FACT")])

    # Missing index on an indexed type -> fails even without a translation.
    with pytest.raises(DSDMetadataMissingError):
        validate_dsd_entries(
            [
                make_entry(
                    translated_text=None,
                    record_type="INFO",
                    subrecord_type="NAM1",
                    string_index=None,
                    form_id="01000333",
                    local_object_id=0x000333,
                )
            ]
        )


# --- J. Error taxonomy --------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"defining_plugin": None}, id="defining_plugin"),
        pytest.param({"local_object_id": None}, id="local_object_id"),
        pytest.param({"record_type": None}, id="record_type"),
        pytest.param(
            {
                "record_type": "INFO",
                "subrecord_type": "NAM1",
                "string_index": None,
                "form_id": "01000333",
                "local_object_id": 0x000333,
            },
            id="info_nam1_without_index",
        ),
        pytest.param(
            {
                "record_type": "QUST",
                "subrecord_type": "NNAM",
                "string_index": None,
                "form_id": "01000444",
                "local_object_id": 0x000444,
            },
            id="quest_nnam_without_index",
        ),
    ],
)
def test_incomplete_metadata_raises_dsd_metadata_missing(tmp_path: Path, overrides):
    entries = [make_entry(**overrides)]

    with pytest.raises(DSDMetadataMissingError) as exc_info:
        export_to_dsd(entries, tmp_path / "must_not_exist.json")

    assert exc_info.value.code == "DSD_METADATA_MISSING"
    assert not (tmp_path / "must_not_exist.json").exists()

    with pytest.raises(DSDMetadataMissingError):
        validate_dsd_entries(entries)


@pytest.mark.parametrize(
    "record_type, subrecord_type",
    [
        pytest.param("FACT", "FULL", id="fact_full"),
        pytest.param("RACE", "DNAM", id="race_dnam"),
    ],
)
def test_unsupported_type_raises_dsd_unsupported_type(tmp_path: Path, record_type, subrecord_type):
    entries = [make_entry(record_type=record_type, subrecord_type=subrecord_type)]

    with pytest.raises(DSDUnsupportedTypeError) as exc_info:
        export_to_dsd(entries, tmp_path / "must_not_exist.json")

    assert exc_info.value.code == "DSD_UNSUPPORTED_TYPE"
    assert f"{record_type} {subrecord_type}" in str(exc_info.value)
    assert not (tmp_path / "must_not_exist.json").exists()

    with pytest.raises(DSDUnsupportedTypeError):
        validate_dsd_entries(entries)


def test_dial_full_is_supported(tmp_path: Path):
    """Upstream DSD 1.4.3 supports DIAL FULL (kRuntime1); the parser extracts
    it, so it must pass validation and export with its exact type string."""
    dial = make_entry(
        form_id="01000999",
        local_object_id=0x000999,
        record_type="DIAL",
        subrecord_type="FULL",
        translated_text="Tema de diálogo",
    )

    validate_dsd_entries([dial])  # must PASS

    output_file = tmp_path / "dial.json"
    export_to_dsd([dial], output_file)

    (item,) = read_json(output_file)
    assert item["type"] == "DIAL FULL"
    assert item["form_id"] == "0x000999|TargetMod.esp"
    assert item["string"] == "Tema de diálogo"
    assert "index" not in item


def test_dial_desc_is_not_supported(tmp_path: Path):
    """Upstream DSD 1.4.3 has no DIAL DESC case: it must fail fast instead of
    being announced as supported."""
    dial_desc = make_entry(record_type="DIAL", subrecord_type="DESC")

    with pytest.raises(DSDUnsupportedTypeError) as exc_info:
        export_to_dsd([dial_desc], tmp_path / "must_not_exist.json")

    assert exc_info.value.code == "DSD_UNSUPPORTED_TYPE"
    assert "DIAL DESC" in str(exc_info.value)
    assert not (tmp_path / "must_not_exist.json").exists()


@pytest.mark.parametrize(
    "dsd_type",
    [
        pytest.param("GMST DATA", id="gmst_data_needs_editor_id_not_emitted"),
        pytest.param("QUST CNAM", id="quest_cnam_not_extracted"),
        pytest.param("MESG ITXT", id="mesg_itxt_not_extracted"),
        pytest.param("PERK EPF2", id="perk_epf2_not_extracted"),
        pytest.param("PERK EPFD", id="perk_epfd_not_extracted"),
        pytest.param("BOOK CNAM", id="book_cnam_not_extracted"),
        pytest.param("REFR FULL", id="refr_full_not_extracted"),
        pytest.param("CELL FULL", id="cell_full_not_extracted"),
    ],
)
def test_not_extracted_types_are_not_announced_as_supported(tmp_path: Path, dsd_type):
    """The allowlist only contains pairs the current pipeline implements end
    to end. Types the parser never extracts (or whose contract PR #6 does not
    complete, e.g. GMST DATA needing editor_id) must fail fast instead of
    being silently accepted with an incomplete entry."""
    record_type, subrecord_type = dsd_type.split(" ", 1)
    entry = make_entry(record_type=record_type, subrecord_type=subrecord_type)

    with pytest.raises(DSDUnsupportedTypeError):
        validate_dsd_entries([entry])


def test_duplicate_canonical_identity_raises_dsd_duplicate_identity(tmp_path: Path):
    # Hand-built duplicates: the parser would deduplicate these, the exporter
    # must defend its own contract regardless of the caller.
    entries = [
        make_entry(text="First", translated_text="Primero"),
        make_entry(text="Second", translated_text="Segundo"),
    ]

    with pytest.raises(DSDDuplicateIdentityError) as exc_info:
        export_to_dsd(entries, tmp_path / "must_not_exist.json")

    assert exc_info.value.code == "DSD_DUPLICATE_IDENTITY"
    assert not (tmp_path / "must_not_exist.json").exists()


def test_duplicate_indexed_identity_with_distinct_indices_is_allowed(tmp_path: Path):
    output_file = tmp_path / "two_responses.json"
    export_to_dsd(
        [
            make_entry(
                record_type="INFO",
                subrecord_type="NAM1",
                string_index=0,
                form_id="01000333",
                local_object_id=0x000333,
                translated_text="Uno",
            ),
            make_entry(
                record_type="INFO",
                subrecord_type="NAM1",
                string_index=4,
                form_id="01000333",
                local_object_id=0x000333,
                translated_text="Dos",
            ),
        ],
        output_file,
    )
    assert len(read_json(output_file)) == 2


# --- Formatting / filesystem --------------------------------------------------


def test_dsd_json_formatting_and_utf8(tmp_path: Path):
    output_file = tmp_path / "formatted.json"
    export_to_dsd([make_entry(translated_text="¡Atención! Canción del Dragón")], output_file)

    raw_text = output_file.read_text(encoding="utf-8")
    assert "¡Atención! Canción del Dragón" in raw_text
    assert r"\u00a1" not in raw_text
    assert '        "form_id"' in raw_text  # list item at indent depth 2


def test_dsd_creates_parent_directories(tmp_path: Path):
    output_file = tmp_path / "nested" / "path" / "SkyrimAITranslator.json"
    assert not output_file.parent.exists()

    export_to_dsd([make_entry()], output_file)

    assert output_file.exists()
    assert len(read_json(output_file)) == 1
