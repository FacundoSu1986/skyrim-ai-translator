import json
from pathlib import Path
from typing import Union
from src.models import StringEntry


def export_to_dsd(entries: list[StringEntry], output_file: Union[str, Path]) -> None:
    """
    Exports translated StringEntry items to a Dynamic String Distributor (DSD) JSON file.

    :param entries: List of StringEntry objects.
    :param output_file: Path to the target JSON output file (as str or Path).
    """
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dsd_data = {
        entry.form_id: entry.translated_text
        for entry in entries
        if entry.translated_text is not None
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(dsd_data, f, indent=4, ensure_ascii=False)
