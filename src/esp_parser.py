import struct
import zlib
import logging
from pathlib import Path
from typing import Iterator, List, Tuple
from src.models import StringEntry

logger = logging.getLogger(__name__)

# Records that contain user-facing translatable strings in Skyrim
INTERESTING_RECORDS = {
    b"INFO",  # Dialogue response (NAM1: dialogue text, RNAM: prompt/topic)
    b"QUST",  # Quests (FULL: name, NNAM: objective text)
    b"DIAL",  # Dialog topics (FULL: prompt text)
    b"BOOK",  # Books and notes (FULL: title, DESC: book content)
    b"MESG",  # Message boxes (FULL: title, DESC: message content)
    b"NPC_",  # Non-player characters (FULL: name, SHRT: short name)
    b"WEAP",  # Weapons (FULL: name, DESC: description)
    b"ARMO",  # Armor (FULL: name, DESC: description)
    b"SPEL",  # Spells (FULL: name, DESC: description)
    b"ACTI",  # Activators (FULL: interaction name)
    b"ALCH",  # Potions/Ingredients (FULL: name)
    b"PERK",  # Perks (FULL: name, DESC: description)
    b"MGEF",  # Magic effects (FULL: name, DNAM: description)
    b"FACT",  # Factions (FULL: name)
    b"RACE",  # Races (FULL: name, DESC: description)
    b"MISC",  # Misc items (FULL: name)
    b"FLOR",  # Flora (FULL: name)
    b"LCTN",  # Locations (FULL: name)
}

INTERESTING_SUBRECORDS = {b"FULL", b"DESC", b"NAM1", b"NNAM", b"RNAM", b"SHRT"}
# DNAM holds text only in these record types; elsewhere it is binary data
DNAM_TEXT_RECORDS = {b"MGEF", b"RACE"}

FLAG_COMPRESSED = 0x00040000
RECORD_HEADER_SIZE = 24  # Skyrim standard record header length


def _decode_string(raw_bytes: bytes) -> str:
    """Decodes bytes to string using UTF-8 with fallback to Windows-1252 / latin1."""
    # Strip trailing null bytes
    cleaned = raw_bytes.rstrip(b"\x00")
    if not cleaned:
        return ""
    try:
        return cleaned.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return cleaned.decode("cp1252", errors="replace")
        except Exception:
            return cleaned.decode("latin1", errors="replace")


def _iter_records(data: bytes) -> Iterator[Tuple[bytes, int, str, bytes]]:
    """Yields (record_type, flags, form_id_hex, body) for every record, entering GRUPs."""
    offset = 0
    total_len = len(data)

    while offset + RECORD_HEADER_SIZE <= total_len:
        tag = data[offset:offset+4]

        if tag == b"GRUP":
            # Records live inside GRUPs: step past the 24-byte group header
            # and keep iterating the records it contains.
            offset += RECORD_HEADER_SIZE
            continue

        rec_size = struct.unpack("<I", data[offset+4:offset+8])[0]
        rec_flags = struct.unpack("<I", data[offset+8:offset+12])[0]
        form_id_val = struct.unpack("<I", data[offset+12:offset+16])[0]
        form_id_hex = f"{form_id_val:08X}"
        body = data[offset+RECORD_HEADER_SIZE:offset+RECORD_HEADER_SIZE+rec_size]

        if rec_flags & FLAG_COMPRESSED:
            if len(body) >= 4:
                decompressed_size = struct.unpack("<I", body[:4])[0]
                try:
                    body = zlib.decompress(body[4:], bufsize=decompressed_size)
                except Exception as err:
                    logger.error(f"Error decompressing record {form_id_hex} ({tag}): {err}")
                    body = b""
            else:
                body = b""

        yield tag, rec_flags, form_id_hex, body
        offset += RECORD_HEADER_SIZE + rec_size


def _read_subrecords(body: bytes) -> Iterator[Tuple[bytes, bytes]]:
    """Yields (subrecord_type, payload) pairs for a record body."""
    offset = 0
    body_len = len(body)
    while offset + 6 <= body_len:
        s_type = body[offset:offset+4]
        s_size = struct.unpack("<H", body[offset+4:offset+6])[0]
        yield s_type, body[offset+6:offset+6+s_size]
        offset += 6 + s_size


def parse_esp_file(filepath: str | Path) -> List[StringEntry]:
    """
    Parses a Skyrim Bethesda Plugin file (.esp, .esm, .esl) and extracts all
    translatable strings, quests, and dialogue responses into StringEntry items.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Plugin file not found: {path}")

    with open(path, "rb") as f:
        data = f.read()

    if len(data) < RECORD_HEADER_SIZE:
        return []

    # Verify TES4 header
    sig = data[0:4]
    if sig != b"TES4":
        logger.warning(f"File {path.name} does not start with TES4 header (got {sig})")

    # Pass 1: build FormID -> EditorID map so VTCK voice references can be
    # resolved to real voice type names (e.g. "MaleNord", "FemaleCommander")
    formid_to_edid: dict[str, str] = {}
    for tag, _flags, form_id_hex, body in _iter_records(data):
        for s_type, payload in _read_subrecords(body):
            if s_type == b"EDID" and payload:
                edid = _decode_string(payload).strip()
                if edid:
                    formid_to_edid[form_id_hex] = edid
                break

    entries: List[StringEntry] = []
    seen_keys = set()

    for tag, _flags, form_id_hex, body in _iter_records(data):
        if tag not in INTERESTING_RECORDS:
            continue

        actor_name = None
        voice_type = None
        for s_type, payload in _read_subrecords(body):
            if s_type == b"VTCK" and len(payload) >= 4:
                # Voice Type FormID: resolve against this plugin's editor IDs
                vtck_formid = f"{int.from_bytes(payload[:4], 'little'):08X}"
                voice_type = formid_to_edid.get(vtck_formid)
            elif s_type == b"ANAM" and len(payload) >= 4:
                actor_name = f"Actor_{int.from_bytes(payload[:4], 'little'):08X}"

        for s_type, payload in _read_subrecords(body):
            is_text_subrecord = s_type in INTERESTING_SUBRECORDS or (
                s_type == b"DNAM" and tag in DNAM_TEXT_RECORDS
            )
            if not is_text_subrecord or not payload:
                continue

            text_val = _decode_string(payload).strip()
            if not text_val:
                continue

            unique_key = (form_id_hex, s_type.decode("ascii", errors="ignore"))
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            is_dialog = (tag == b"INFO" and s_type == b"NAM1")
            entries.append(
                StringEntry(
                    form_id=form_id_hex,
                    text=text_val,
                    is_dialog=is_dialog,
                    actor=actor_name,
                    voice_type=voice_type or ("MaleNord" if is_dialog else None)
                )
            )

    return entries
