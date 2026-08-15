import io
import struct
import zlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple
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

INTERESTING_SUBRECORDS = {b"FULL", b"DESC", b"NAM1", b"NNAM", b"RNAM", b"DNAM", b"SHRT"}

FLAG_COMPRESSED = 0x00040000


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

    entries: List[StringEntry] = []
    seen_keys = set()
    offset = 0
    total_len = len(data)

    if total_len < 24:
        return []

    # Verify TES4 header
    sig = data[0:4]
    if sig != b"TES4":
        logger.warning(f"File {path.name} does not start with TES4 header (got {sig})")

    def parse_subrecords(sub_data: bytes, form_id_hex: str, rec_type: bytes) -> None:
        sub_offset = 0
        sub_len = len(sub_data)
        actor_name = None
        voice_type = None

        # First pass to find voice type or actor if present
        scan_offset = 0
        while scan_offset + 6 <= sub_len:
            s_type = sub_data[scan_offset:scan_offset+4]
            s_size = struct.unpack("<H", sub_data[scan_offset+4:scan_offset+6])[0]
            s_payload = sub_data[scan_offset+6:scan_offset+6+s_size]
            if s_type == b"VTCK":  # Voice Type FormID or identifier
                voice_type = f"Voice_{form_id_hex}"
            elif s_type == b"ANAM":  # Speaker actor FormID
                actor_name = f"Actor_{int.from_bytes(s_payload[:4], 'little'):08X}"
            scan_offset += 6 + s_size

        # Second pass to extract texts
        sub_offset = 0
        while sub_offset + 6 <= sub_len:
            s_type = sub_data[sub_offset:sub_offset+4]
            s_size = struct.unpack("<H", sub_data[sub_offset+4:sub_offset+6])[0]
            s_content = sub_data[sub_offset+6:sub_offset+6+s_size]

            if s_type in INTERESTING_SUBRECORDS and s_size > 0:
                text_val = _decode_string(s_content).strip()
                if text_val and len(text_val) > 0:
                    unique_key = (form_id_hex, s_type.decode("ascii", errors="ignore"))
                    if unique_key not in seen_keys:
                        seen_keys.add(unique_key)
                        is_dialog = (rec_type == b"INFO" and s_type == b"NAM1")
                        
                        entries.append(
                            StringEntry(
                                form_id=form_id_hex,
                                text=text_val,
                                is_dialog=is_dialog,
                                actor=actor_name,
                                voice_type=voice_type or ("MaleNord" if is_dialog else None)
                            )
                        )

            sub_offset += 6 + s_size

    # Iterate through chunks / GRUP / records
    while offset + 24 <= total_len:
        tag = data[offset:offset+4]

        if tag == b"GRUP":
            grup_size = struct.unpack("<I", data[offset+4:offset+8])[0]
            if grup_size == 0 or offset + grup_size > total_len:
                offset += 24
            else:
                # Move inside group header (24 bytes)
                offset += 24
            continue

        # Regular Record
        rec_size = struct.unpack("<I", data[offset+4:offset+8])[0]
        rec_flags = struct.unpack("<I", data[offset+8:offset+12])[0]
        form_id_val = struct.unpack("<I", data[offset+12:offset+16])[0]
        form_id_hex = f"{form_id_val:08X}"

        rec_header_size = 24  # Skyrim standard record header length
        rec_body = data[offset+rec_header_size:offset+rec_header_size+rec_size]

        if tag in INTERESTING_RECORDS:
            if rec_flags & FLAG_COMPRESSED:
                if len(rec_body) >= 4:
                    decompressed_size = struct.unpack("<I", rec_body[:4])[0]
                    try:
                        decompressed_body = zlib.decompress(rec_body[4:], bufsize=decompressed_size)
                        parse_subrecords(decompressed_body, form_id_hex, tag)
                    except Exception as err:
                        logger.error(f"Error decompressing record {form_id_hex} ({tag}): {err}")
            else:
                parse_subrecords(rec_body, form_id_hex, tag)

        offset += rec_header_size + rec_size

    return entries
