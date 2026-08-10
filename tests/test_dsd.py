import json
from pathlib import Path
from src.models import StringEntry
from src.dsd_exporter import export_to_dsd


def test_export_to_dsd_positive(tmp_path: Path):
    output_file = tmp_path / "dsd_output.json"
    entries = [
        StringEntry(form_id="0x000123", text="Hello", translated_text="Hola", is_dialog=False),
        StringEntry(form_id="0x000456", text="Goodbye", translated_text="Adiós", is_dialog=True, actor="Guard"),
    ]

    export_to_dsd(entries, str(output_file))

    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content == {
        "0x000123": "Hola",
        "0x000456": "Adiós",
    }


def test_export_to_dsd_omits_none_translations(tmp_path: Path):
    output_file = tmp_path / "dsd_partial.json"
    entries = [
        StringEntry(form_id="0x01", text="Sword", translated_text="Espada"),
        StringEntry(form_id="0x02", text="Shield", translated_text=None),
        StringEntry(form_id="0x03", text="Bow", translated_text="Arco"),
    ]

    export_to_dsd(entries, output_file)

    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content == {
        "0x01": "Espada",
        "0x03": "Arco",
    }
    assert "0x02" not in content


def test_export_to_dsd_omits_empty_and_whitespace_translations(tmp_path: Path):
    output_file = tmp_path / "dsd_empty_omitted.json"
    entries = [
        StringEntry(form_id="0x01", text="Sword", translated_text="Espada"),
        StringEntry(form_id="0x02", text="Shield", translated_text=None),
        StringEntry(form_id="0x03", text="Bow", translated_text=""),
        StringEntry(form_id="0x04", text="Axe", translated_text="   "),
        StringEntry(form_id="0x05", text="Staff", translated_text="\t\n"),
    ]

    export_to_dsd(entries, output_file)

    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content == {
        "0x01": "Espada",
    }
    assert "0x02" not in content
    assert "0x03" not in content
    assert "0x04" not in content
    assert "0x05" not in content



def test_export_to_dsd_json_formatting_and_utf8(tmp_path: Path):
    output_file = tmp_path / "dsd_formatted.json"
    entries = [
        StringEntry(form_id="0x01", text="Special", translated_text="¡Atención! Canción del Dragón"),
    ]

    export_to_dsd(entries, str(output_file))

    raw_text = output_file.read_text(encoding="utf-8")

    # Check UTF-8 characters are intact without ascii escape sequences (\uXXXX)
    assert "¡Atención! Canción del Dragón" in raw_text
    assert r"\u00a1" not in raw_text

    # Check standard JSON indent formatting (4 spaces)
    lines = raw_text.splitlines()
    assert len(lines) >= 3
    assert '    "0x01": "¡Atención! Canción del Dragón"' in lines


def test_export_to_dsd_creates_parent_directories(tmp_path: Path):
    output_file = tmp_path / "nested" / "path" / "output" / "dsd.json"
    entries = [
        StringEntry(form_id="0x10", text="Key", translated_text="Llave"),
    ]

    assert not output_file.parent.exists()

    export_to_dsd(entries, output_file)

    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content == {"0x10": "Llave"}


def test_export_to_dsd_empty_list(tmp_path: Path):
    output_file = tmp_path / "empty.json"

    export_to_dsd([], output_file)

    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content == {}
