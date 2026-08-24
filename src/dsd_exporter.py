import json
from pathlib import Path

from src.models import StringEntry


class DSDExportError(RuntimeError):
    """Base error for DSD export contract violations."""

    code = "DSD_EXPORT_ERROR"


class DSDMetadataMissingError(DSDExportError):
    code = "DSD_METADATA_MISSING"


class DSDUnsupportedTypeError(DSDExportError):
    code = "DSD_UNSUPPORTED_TYPE"


class DSDDuplicateIdentityError(DSDExportError):
    code = "DSD_DUPLICATE_IDENTITY"


# Allowlist = pairs the current pipeline implements end to end:
# (record, subrecord) combos the parser actually extracts AND that Dynamic
# String Distributor 1.4.3 can represent (Manager::getTranslationType).
# Anything outside this set fails fast instead of silently vanishing at
# game runtime (DSD only logs unknown types at debug level).
#
# Pairs the parser extracts but DSD cannot represent (FACT FULL, RACE DNAM,
# DIAL DESC) correctly produce DSD_UNSUPPORTED_TYPE. Upstream-only types the
# parser never extracts (GMST DATA, REFR FULL, MESG ITXT, PERK EPF2/EPFD,
# QUST CNAM, BOOK CNAM, CELL FULL, ...) are NOT announced as supported:
# accepting them would promise contracts PR #6 does not complete (e.g. GMST
# DATA additionally requires editor_id, which the exporter never emits).
_FULL_RECORDS = ("ACTI ALCH ARMO BOOK DIAL FLOR LCTN MESG MGEF MISC NPC_ PERK QUST RACE SPEL WEAP").split()

_DESC_RECORDS = "ARMO BOOK MESG PERK RACE SPEL WEAP".split()

DSD_SUPPORTED_TYPES = frozenset(
    # DIAL FULL is upstream kRuntime1 rather than kFullName; membership is
    # identical, so it lives with the FULL records here.
    {f"{record} FULL" for record in _FULL_RECORDS}
    | {f"{record} DESC" for record in _DESC_RECORDS}
    | {
        "INFO NAM1",
        "INFO RNAM",
        "NPC_ SHRT",
        "MGEF DNAM",
        "ACTI RNAM",
        "FLOR RNAM",
        "QUST NNAM",
    }
)

# DSD selects the exact string slot through "index" for these types.
# A missing index is metadata loss: for INFO NAM1, DSD would silently
# default it to 0 and collide with the real response 0.
INDEX_REQUIRED_TYPES = frozenset(
    {
        "INFO NAM1",
        "QUST NNAM",
    }
)


def _describe(entry: StringEntry) -> str:
    record = entry.record_type or "?"
    subrecord = entry.subrecord_type or "?"
    return f"{record} {subrecord} at FormID {entry.form_id}"


def _validate_entry(entry: StringEntry) -> tuple[str, str, object]:
    """Runs all per-entry contract checks and returns the canonical identity.

    Independent of translated_text: the pipeline preflight validates entries
    BEFORE translation exists, and every entry that can reach the export must
    be representable.
    """
    where = _describe(entry)

    if entry.defining_plugin is None:
        raise DSDMetadataMissingError(f"{where}: defining_plugin is required for DSD export")
    if entry.local_object_id is None:
        raise DSDMetadataMissingError(f"{where}: local_object_id is required for DSD export")
    if entry.record_type is None or entry.subrecord_type is None:
        raise DSDMetadataMissingError(f"{where}: record_type/subrecord_type are required for DSD export")

    dsd_type = f"{entry.record_type} {entry.subrecord_type}"
    if dsd_type not in DSD_SUPPORTED_TYPES:
        raise DSDUnsupportedTypeError(
            f"{where}: type '{dsd_type}' cannot be represented by Dynamic String Distributor 1.4.3"
        )

    # Non-indexed types never carry an index, even if a stray one is present.
    index = entry.string_index if dsd_type in INDEX_REQUIRED_TYPES else None
    if dsd_type in INDEX_REQUIRED_TYPES and index is None:
        raise DSDMetadataMissingError(f"{where}: '{dsd_type}' requires a resolved string_index for DSD export")

    canonical_form_id = f"0x{entry.local_object_id:06X}|{entry.defining_plugin}"
    return canonical_form_id, dsd_type, index


def _make_dsd_item(entry: StringEntry, identity: tuple[str, str, object]) -> dict:
    canonical_form_id, dsd_type, index = identity
    item = {
        "form_id": canonical_form_id,
        "type": dsd_type,
        "string": entry.translated_text,
    }
    if index is not None:
        item["index"] = index
    return item


def _collect_dsd_items(entries: list[StringEntry]) -> list[dict]:
    """Builds the DSD item list from translated entries, enforcing the full
    export contract (metadata, supported types, unique identities)."""
    items: list[dict] = []
    seen: dict[tuple, int] = {}
    for position, entry in enumerate(entries):
        if entry.translated_text is None:
            continue
        identity = _validate_entry(entry)
        if identity in seen:
            raise DSDDuplicateIdentityError(
                f"duplicate DSD identity '{identity[1]}' for {identity[0]} "
                f"(index={identity[2]}): entries {seen[identity]} and {position} collide"
            )
        seen[identity] = position
        items.append(_make_dsd_item(entry, identity))
    return items


def validate_dsd_entries(entries: list[StringEntry]) -> None:
    """Runs the full DSD contract validation without writing anything.

    Validates EVERY entry regardless of translated_text: the pipeline calls
    this as a preflight BEFORE translation (when no translated_text exists
    yet), so that unrepresentable or metadata-incomplete entries fail fast
    before any LLM/TTS budget is spent. export_to_dsd re-runs the same checks
    on the translated subset as its own contractual defense.
    """
    seen: dict[tuple, int] = {}
    for position, entry in enumerate(entries):
        identity = _validate_entry(entry)
        if identity in seen:
            raise DSDDuplicateIdentityError(
                f"duplicate DSD identity '{identity[1]}' for {identity[0]} "
                f"(index={identity[2]}): entries {seen[identity]} and {position} collide"
            )
        seen[identity] = position


def export_to_dsd(entries: list[StringEntry], output_file: str | Path) -> None:
    """
    Exports translated StringEntry items to a Dynamic String Distributor
    (DSD) 1.4.3 JSON file: a root list of
    {"form_id": "0x<LOCAL_ID>|<DefiningPlugin>", "type": "<RECORD> <SUBRECORD>",
    "string": <translated_text>} objects, plus "index" for indexed types.

    translated_text is None -> the entry is omitted (no translation exists).
    translated_text == ""  -> the entry is exported (intentionally empty string).
    """
    out_path = Path(output_file)
    dsd_items = _collect_dsd_items(list(entries))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(dsd_items, f, indent=4, ensure_ascii=False)
