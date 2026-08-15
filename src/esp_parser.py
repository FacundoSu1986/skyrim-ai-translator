import struct
import zlib
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
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

INTERESTING_SUBRECORDS = {b"FULL", b"DESC", b"NAM1", b"NNAM", b"RNAM", b"SHRT"}
# DNAM holds text only in these record types; elsewhere it is binary data
DNAM_TEXT_RECORDS = {b"MGEF", b"RACE"}

FLAG_COMPRESSED = 0x00040000
RECORD_HEADER_SIZE = 24  # Skyrim standard record header length


def _norm_plugin(name: str) -> str:
    """Normalizes plugin filename for case-insensitive canonical mapping."""
    return Path(name).name.lower()


def _is_valid_text(s: str) -> bool:
    """Returns True if string is non-empty, printable, and not raw binary/localized string IDs."""
    if not s or not s.strip():
        return False
    return s.isprintable() and not any(ord(c) < 32 for c in s if c not in "\t\n\r")


@dataclass(frozen=True, slots=True)
class RecordKey:
    """
    Canonical record identifier across plugins and masters.
    object_id is the 24-bit local integer (form_id & 0x00FFFFFF).
    """
    plugin: str
    object_id: int

    def __repr__(self) -> str:
        return f"RecordKey({self.plugin}:0x{self.object_id:06X})"


def _decode_string(raw_bytes: bytes) -> str:
    """Decodes bytes to string using UTF-8 with fallback to Windows-1252 / latin1."""
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


def _iter_records(data: bytes) -> Iterator[Tuple[bytes, int, int, str, bytes]]:
    """Yields (record_type, flags, form_id_val, form_id_hex, body) for every record, entering GRUPs."""
    offset = 0
    total_len = len(data)

    while offset + RECORD_HEADER_SIZE <= total_len:
        tag = data[offset:offset+4]

        if tag == b"GRUP":
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
                    logger.error("Error decompressing record %s (%s): %s", form_id_hex, tag, err)
                    body = b""
            else:
                body = b""

        yield tag, rec_flags, form_id_val, form_id_hex, body
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


def _extract_masters_from_tes4(body: bytes) -> list[str]:
    """Extracts declared MAST master filenames in order from a TES4 record body."""
    masters: list[str] = []
    for s_type, payload in _read_subrecords(body):
        if s_type == b"MAST" and payload:
            m_name = _decode_string(payload).strip()
            if m_name:
                masters.append(m_name)
    return masters


def _resolve_record_key(
    raw_form_id: int,
    current_plugin: str,
    masters: Sequence[str]
) -> Optional[RecordKey]:
    """
    Resolves a raw 32-bit FormID into a canonical RecordKey(plugin, object_id).

    Resolution rules:
      - mod_index == 0xFE: ESL / Light plugin reference -> not supported yet, returns None with warning.
      - 0 <= mod_index < len(masters): Master reference -> RecordKey(masters[mod_index], object_id).
      - mod_index == len(masters): Local record -> RecordKey(current_plugin, object_id).
      - Otherwise: Out of bounds / invalid -> returns None with warning (never treated as local).
    """
    mod_index = (raw_form_id >> 24) & 0xFF
    object_id = raw_form_id & 0x00FFFFFF

    if mod_index == 0xFE:
        logger.warning(
            "ESL/light plugin FormID 0x%08X master resolution: not supported yet",
            raw_form_id
        )
        return None

    num_masters = len(masters)
    if 0 <= mod_index < num_masters:
        owner = masters[mod_index]
        return RecordKey(plugin=_norm_plugin(owner), object_id=object_id)
    elif mod_index == num_masters:
        return RecordKey(plugin=_norm_plugin(current_plugin), object_id=object_id)
    else:
        logger.warning(
            "FormID 0x%08X has invalid master index %d (declared masters count: %d)",
            raw_form_id, mod_index, num_masters
        )
        return None


@dataclass
class MasterIndexData:
    """In-memory read-only index of master records required for VoiceType and Actor resolution."""
    plugin_name: str
    masters: list[str]
    npc_to_vtck: dict[RecordKey, int]
    npc_to_name: dict[RecordKey, str]
    vtyp_to_edid: dict[RecordKey, str]


class MasterResolver:
    """
    Lightweight read-only resolver and cache for Skyrim master files.
    Opens master files strictly for reading ('rb') and caches their index.
    """

    def __init__(self, search_paths: Optional[Sequence[Path | str]] = None):
        self.search_paths: list[Path] = [
            Path(p) for p in (search_paths or []) if Path(p).is_dir()
        ]
        self._cache: dict[Path, MasterIndexData] = {}

    def find_master_file(self, master_name: str, origin_dir: Path) -> Optional[Path]:
        """Locates a master file case-insensitively in origin_dir or search_paths."""
        target_lower = _norm_plugin(master_name)
        search_dirs = [origin_dir] + [p for p in self.search_paths if p != origin_dir]

        for directory in search_dirs:
            if not directory.is_dir():
                continue
            try:
                for entry in directory.iterdir():
                    if entry.is_file() and _norm_plugin(entry.name) == target_lower:
                        return entry
            except OSError as err:
                logger.warning("Error accessing master search directory %s: %s", directory, err)
        return None

    def get_or_load_master(self, master_name: str, origin_dir: Path) -> Optional[MasterIndexData]:
        """Loads and indexes master records in read-only mode, with in-memory caching."""
        master_path = self.find_master_file(master_name, origin_dir)
        if not master_path:
            logger.warning(
                "Master file '%s' could not be found in search paths (origin: %s)",
                master_name, origin_dir
            )
            return None

        resolved_path = master_path.resolve()
        if resolved_path in self._cache:
            return self._cache[resolved_path]

        try:
            with open(resolved_path, "rb") as f:
                data = f.read()
        except OSError as err:
            logger.error("Failed to read master file %s in read-only mode: %s", resolved_path, err)
            return None

        if len(data) < RECORD_HEADER_SIZE or data[0:4] != b"TES4":
            logger.warning("Master file %s is invalid or does not start with TES4 header", resolved_path)
            return None

        # Extract declared masters in the master's own TES4 header
        masters: list[str] = []
        for tag, _flags, _form_id_val, _form_id_hex, body in _iter_records(data):
            if tag == b"TES4":
                masters = _extract_masters_from_tes4(body)
                break

        plugin_name = master_path.name
        npc_to_vtck: dict[RecordKey, int] = {}
        npc_to_name: dict[RecordKey, str] = {}
        vtyp_to_edid: dict[RecordKey, str] = {}

        for tag, _flags, form_id_val, _form_id_hex, body in _iter_records(data):
            rec_key = _resolve_record_key(form_id_val, plugin_name, masters)
            if rec_key is None:
                continue

            if tag == b"VTYP":
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID" and payload:
                        vtyp_to_edid[rec_key] = _decode_string(payload).strip()
            elif tag == b"NPC_":
                edid = None
                full_name = None
                vtck_formid = None
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID" and payload:
                        edid = _decode_string(payload).strip()
                    elif s_type == b"FULL" and payload:
                        full_name = _decode_string(payload).strip()
                    elif s_type == b"VTCK" and len(payload) >= 4:
                        vtck_formid = int.from_bytes(payload[:4], "little")

                if full_name and _is_valid_text(full_name):
                    npc_to_name[rec_key] = full_name
                elif edid and _is_valid_text(edid):
                    npc_to_name[rec_key] = edid

                if vtck_formid is not None:
                    npc_to_vtck[rec_key] = vtck_formid

        index_data = MasterIndexData(
            plugin_name=plugin_name,
            masters=masters,
            npc_to_vtck=npc_to_vtck,
            npc_to_name=npc_to_name,
            vtyp_to_edid=vtyp_to_edid,
        )
        self._cache[resolved_path] = index_data
        return index_data


def parse_esp_file(
    filepath: str | Path,
    master_search_paths: Optional[Sequence[Path | str]] = None,
) -> List[StringEntry]:
    """
    Parses a Skyrim Bethesda Plugin file (.esp, .esm, .esl) and extracts all
    translatable strings, quests, and dialogue responses into StringEntry items.
    Follows the speaker relation chain across masters in read-only mode:
      INFO (ANAM) -> NPC_ (VTCK) -> VTYP (EDID).
    When an NPC or VoiceType cannot be resolved, cleanly leaves voice_type=None.
    Masters are opened strictly read-only and never modified.
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

    # Pass 0: Extract declared masters from TES4 header
    local_masters: list[str] = []
    for tag, _flags, _form_id_val, _form_id_hex, body in _iter_records(data):
        if tag == b"TES4":
            local_masters = _extract_masters_from_tes4(body)
            break

    plugin_name = path.name
    master_resolver = MasterResolver(search_paths=master_search_paths)

    # Pass 1: Build local indexes for VoiceTypes, NPC records, and EditorIDs
    local_npc_to_vtck: dict[RecordKey, int] = {}
    local_npc_to_name: dict[RecordKey, str] = {}
    local_vtyp_to_edid: dict[RecordKey, str] = {}

    for tag, _flags, form_id_val, _form_id_hex, body in _iter_records(data):
        rec_key = _resolve_record_key(form_id_val, plugin_name, local_masters)
        if rec_key is None:
            continue

        if tag == b"VTYP":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and payload:
                    local_vtyp_to_edid[rec_key] = _decode_string(payload).strip()
        elif tag == b"NPC_":
            edid = None
            full_name = None
            vtck_formid = None
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and payload:
                    edid = _decode_string(payload).strip()
                elif s_type == b"FULL" and payload:
                    full_name = _decode_string(payload).strip()
                elif s_type == b"VTCK" and len(payload) >= 4:
                    vtck_formid = int.from_bytes(payload[:4], "little")

            if full_name and _is_valid_text(full_name):
                local_npc_to_name[rec_key] = full_name
            elif edid and _is_valid_text(edid):
                local_npc_to_name[rec_key] = edid

            if vtck_formid is not None:
                local_npc_to_vtck[rec_key] = vtck_formid

    # Pass 2: Extract translatable strings and resolve dialogue voice types
    entries: List[StringEntry] = []
    seen_keys = set()

    for tag, _flags, form_id_val, form_id_hex, body in _iter_records(data):
        if tag not in INTERESTING_RECORDS:
            continue

        speaker_formid: Optional[int] = None
        direct_vtck: Optional[int] = None

        for s_type, payload in _read_subrecords(body):
            if s_type == b"ANAM" and len(payload) >= 4:
                speaker_formid = int.from_bytes(payload[:4], "little")
            elif s_type == b"VTCK" and len(payload) >= 4:
                direct_vtck = int.from_bytes(payload[:4], "little")

        actor_name: Optional[str] = None
        voice_type: Optional[str] = None

        if speaker_formid is not None:
            speaker_key = _resolve_record_key(speaker_formid, plugin_name, local_masters)
            if speaker_key is not None:
                npc_vtck_raw: Optional[int] = None
                npc_owner_plugin: str = speaker_key.plugin
                npc_owner_masters: list[str] = []

                if speaker_key in local_npc_to_name or speaker_key in local_npc_to_vtck:
                    actor_name = local_npc_to_name.get(speaker_key)
                    npc_vtck_raw = local_npc_to_vtck.get(speaker_key)
                    npc_owner_masters = local_masters
                else:
                    master_data = master_resolver.get_or_load_master(speaker_key.plugin, path.parent)
                    if master_data:
                        actor_name = master_data.npc_to_name.get(speaker_key)
                        npc_vtck_raw = master_data.npc_to_vtck.get(speaker_key)
                        npc_owner_masters = master_data.masters
                    else:
                        logger.warning(
                            "No se pudo resolver VoiceType para NPC %s: master '%s' no disponible",
                            speaker_key, speaker_key.plugin
                        )

                if not actor_name:
                    actor_name = f"Actor_{speaker_formid:08X}"

                if npc_vtck_raw is not None:
                    vtck_key = _resolve_record_key(npc_vtck_raw, npc_owner_plugin, npc_owner_masters)
                    if vtck_key is not None:
                        if vtck_key in local_vtyp_to_edid:
                            voice_type = local_vtyp_to_edid[vtck_key]
                        else:
                            vtyp_master_data = master_resolver.get_or_load_master(vtck_key.plugin, path.parent)
                            if vtyp_master_data:
                                voice_type = vtyp_master_data.vtyp_to_edid.get(vtck_key)
                            else:
                                logger.warning(
                                    "No se pudo resolver VoiceType %s: master '%s' no disponible",
                                    vtck_key, vtck_key.plugin
                                )
                    else:
                        logger.warning("No se pudo resolver VTCK FormID 0x%08X para NPC %s", npc_vtck_raw, speaker_key)
            else:
                actor_name = f"Actor_{speaker_formid:08X}"

        elif direct_vtck is not None:
            vtck_key = _resolve_record_key(direct_vtck, plugin_name, local_masters)
            if vtck_key is not None:
                if vtck_key in local_vtyp_to_edid:
                    voice_type = local_vtyp_to_edid[vtck_key]
                else:
                    vtyp_master_data = master_resolver.get_or_load_master(vtck_key.plugin, path.parent)
                    if vtyp_master_data:
                        voice_type = vtyp_master_data.vtyp_to_edid.get(vtck_key)

        if tag == b"NPC_" and not actor_name:
            rec_key = _resolve_record_key(form_id_val, plugin_name, local_masters)
            if rec_key and rec_key in local_npc_to_name:
                actor_name = local_npc_to_name[rec_key]
            else:
                actor_name = f"Actor_{form_id_hex}"

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
                    voice_type=voice_type
                )
            )

    return entries
