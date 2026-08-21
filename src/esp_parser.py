import struct
import zlib
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
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
FLAG_LOCALIZED = 0x00000080
RECORD_HEADER_SIZE = 24  # Skyrim standard record header length


def _norm_plugin(name: str) -> str:
    """Normalizes plugin filename for case-insensitive canonical mapping."""
    return Path(name).name.lower()


def _is_valid_text(s: str) -> bool:
    """
    Basic sanity check to filter out non-printable binary data.
    Note: This is a defensive filter and does not constitute full .STRINGS localization support.
    """
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


def _iter_records(data: bytes) -> Iterator[Tuple[bytes, int, int, str, bytes, Optional[int]]]:
    """
    Yields (record_type, flags, form_id_val, form_id_hex, body, parent_dial_formid)
    for every record, entering GRUPs and tracking parent Topic Children GRUPs (grp_type == 7 in TES5).
    """
    offset = 0
    total_len = len(data)
    # Stack of enclosing GRUPs: list of (end_offset, grp_type, label_formid)
    grup_stack: list[tuple[int, int, int]] = []

    while offset + RECORD_HEADER_SIZE <= total_len:
        # Pop expired GRUPs
        while grup_stack and offset >= grup_stack[-1][0]:
            grup_stack.pop()

        tag = data[offset:offset+4]

        if tag == b"GRUP":
            rec_size = struct.unpack("<I", data[offset+4:offset+8])[0]
            label_val = struct.unpack("<I", data[offset+8:offset+12])[0]
            grp_type = struct.unpack("<i", data[offset+12:offset+16])[0]
            grup_end = offset + rec_size
            grup_stack.append((grup_end, grp_type, label_val))
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

        # Find enclosing Topic Children GRUP (grp_type == 7 in TES5)
        parent_dial_formid: Optional[int] = None
        for _g_end, g_type, g_label in reversed(grup_stack):
            if g_type == 7:
                parent_dial_formid = g_label
                break

        yield tag, rec_flags, form_id_val, form_id_hex, body, parent_dial_formid
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


def _extract_record_editor_id(body: bytes) -> Optional[str]:
    """Returns a record's EDID when it is present and contains sane text."""
    for s_type, payload in _read_subrecords(body):
        if s_type == b"EDID" and payload:
            editor_id = _decode_string(payload).strip()
            if _is_valid_text(editor_id):
                return editor_id
            return None
    return None


def _parse_info_response_number(payload: bytes) -> Optional[int]:
    """Decodes Skyrim INFO.TRDT's u8 Response number at offset 12."""
    if len(payload) < 13:
        return None
    return payload[12]


def _parse_quest_objective_index(payload: bytes) -> Optional[int]:
    """Decodes Skyrim QUST.QOBJ Objective Index (u16 little-endian)."""
    if len(payload) < 2:
        return None
    return int.from_bytes(payload[:2], "little")


def _resolve_record_key(
    raw_form_id: int,
    current_plugin: str,
    masters: Sequence[str],
    warned_esl: Optional[set[int]] = None,
    warned_invalid_index: Optional[set[tuple[int, int]]] = None,
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
        if warned_esl is None or 0xFE not in warned_esl:
            if warned_esl is not None:
                warned_esl.add(0xFE)
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
        inv_key = (mod_index, num_masters)
        if warned_invalid_index is None or inv_key not in warned_invalid_index:
            if warned_invalid_index is not None:
                warned_invalid_index.add(inv_key)
            logger.warning(
                "FormID 0x%08X has invalid master index %d (declared masters count: %d)",
                raw_form_id, mod_index, num_masters
            )
        return None


@dataclass
class MasterIndexData:
    """In-memory read-only index of master records required for VoiceType, Template, Actor, Quest, and Dialogue resolution."""
    plugin_name: str
    masters: list[str]
    npc_to_vtck: dict[RecordKey, int]
    npc_to_tplt: dict[RecordKey, int]
    npc_to_name: dict[RecordKey, str]
    vtyp_to_edid: dict[RecordKey, str]
    qust_to_edid: dict[RecordKey, str] = field(default_factory=dict)
    dial_to_edid: dict[RecordKey, str] = field(default_factory=dict)
    dial_to_qnam: dict[RecordKey, int] = field(default_factory=dict)


class MasterResolver:
    """
    Lightweight read-only resolver and cache for Skyrim master files.
    Opens master files strictly for reading ('rb') and caches both master file paths
    and their indexed data.
    """

    def __init__(self, search_paths: Optional[Sequence[Path | str]] = None):
        self.search_paths: list[Path] = []
        for p in (search_paths or []):
            path_obj = Path(p)
            if path_obj.is_dir():
                self.search_paths.append(path_obj)
            else:
                logger.warning("Search path '%s' does not exist or is not a directory", p)
        self._path_cache: dict[tuple[Path, str], Optional[Path]] = {}
        self._cache: dict[Path, Optional[MasterIndexData]] = {}

    def find_master_file(self, master_name: str, origin_dir: Path) -> Optional[Path]:
        """Locates a master file case-insensitively in origin_dir or search_paths, with caching."""
        origin_resolved = origin_dir.resolve()
        target_lower = _norm_plugin(master_name)
        cache_key = (origin_resolved, target_lower)

        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        search_dirs = [origin_dir] + [p for p in self.search_paths if p != origin_dir]
        found_path: Optional[Path] = None

        for directory in search_dirs:
            if not directory.is_dir():
                continue
            try:
                for entry in directory.iterdir():
                    if entry.is_file() and _norm_plugin(entry.name) == target_lower:
                        found_path = entry
                        break
                if found_path is not None:
                    break
            except OSError as err:
                logger.warning("Error accessing master search directory %s: %s", directory, err)

        if found_path is None:
            logger.warning(
                "Master file '%s' could not be found in search paths (origin: %s)",
                master_name, origin_dir
            )

        self._path_cache[cache_key] = found_path
        return found_path

    def get_or_load_master(self, master_name: str, origin_dir: Path) -> Optional[MasterIndexData]:
        """Loads and indexes master records in read-only mode, with in-memory caching."""
        master_path = self.find_master_file(master_name, origin_dir)
        if not master_path:
            return None

        resolved_path = master_path.resolve()
        if resolved_path in self._cache:
            return self._cache[resolved_path]

        try:
            with open(resolved_path, "rb") as f:
                data = f.read()
        except OSError as err:
            logger.error("Failed to read master file %s in read-only mode: %s", resolved_path, err)
            self._cache[resolved_path] = None
            return None

        if len(data) < RECORD_HEADER_SIZE or data[0:4] != b"TES4":
            logger.warning("Master file %s is invalid or does not start with TES4 header", resolved_path)
            self._cache[resolved_path] = None
            return None

        # Extract declared masters and localized status in the master's own TES4 header
        masters: list[str] = []
        is_localized = False
        for tag, flags, _form_id_val, _form_id_hex, body, _parent_dial in _iter_records(data):
            if tag == b"TES4":
                masters = _extract_masters_from_tes4(body)
                if flags & FLAG_LOCALIZED:
                    is_localized = True
                break

        plugin_name = master_path.name
        npc_to_vtck: dict[RecordKey, int] = {}
        npc_to_tplt: dict[RecordKey, int] = {}
        npc_to_name: dict[RecordKey, str] = {}
        vtyp_to_edid: dict[RecordKey, str] = {}
        qust_to_edid: dict[RecordKey, str] = {}
        dial_to_edid: dict[RecordKey, str] = {}
        dial_to_qnam: dict[RecordKey, int] = {}

        for tag, _flags, form_id_val, _form_id_hex, body, _parent_dial in _iter_records(data):
            rec_key = _resolve_record_key(form_id_val, plugin_name, masters)
            if rec_key is None:
                continue

            if tag == b"VTYP":
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID" and payload:
                        vtyp_to_edid[rec_key] = _decode_string(payload).strip()
            elif tag == b"QUST":
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID" and payload:
                        qust_to_edid[rec_key] = _decode_string(payload).strip()
                        break
            elif tag == b"DIAL":
                d_edid: Optional[str] = None
                d_qnam: Optional[int] = None
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID":
                        d_edid = _decode_string(payload).strip()
                    elif s_type == b"QNAM" and len(payload) >= 4:
                        d_qnam = int.from_bytes(payload[:4], "little")
                if d_edid is not None:
                    dial_to_edid[rec_key] = d_edid
                if d_qnam is not None:
                    dial_to_qnam[rec_key] = d_qnam
            elif tag == b"NPC_":
                edid = None
                full_name = None
                vtck_formid = None
                tplt_formid = None
                for s_type, payload in _read_subrecords(body):
                    if s_type == b"EDID" and payload:
                        edid = _decode_string(payload).strip()
                    elif s_type == b"FULL" and payload and not is_localized:
                        full_name = _decode_string(payload).strip()
                    elif s_type == b"VTCK" and len(payload) >= 4:
                        vtck_formid = int.from_bytes(payload[:4], "little")
                    elif s_type == b"TPLT" and len(payload) >= 4:
                        tplt_formid = int.from_bytes(payload[:4], "little")

                if full_name and _is_valid_text(full_name):
                    npc_to_name[rec_key] = full_name
                elif edid and _is_valid_text(edid):
                    npc_to_name[rec_key] = edid

                if vtck_formid is not None:
                    npc_to_vtck[rec_key] = vtck_formid
                if tplt_formid is not None:
                    npc_to_tplt[rec_key] = tplt_formid

        index_data = MasterIndexData(
            plugin_name=plugin_name,
            masters=masters,
            npc_to_vtck=npc_to_vtck,
            npc_to_tplt=npc_to_tplt,
            npc_to_name=npc_to_name,
            vtyp_to_edid=vtyp_to_edid,
            qust_to_edid=qust_to_edid,
            dial_to_edid=dial_to_edid,
            dial_to_qnam=dial_to_qnam,
        )
        self._cache[resolved_path] = index_data
        return index_data


def _find_npc_data(
    npc_key: RecordKey,
    local_plugin_name: str,
    local_masters: list[str],
    local_npc_vtck: dict[RecordKey, int],
    local_npc_tplt: dict[RecordKey, int],
    local_npc_name: dict[RecordKey, str],
    master_resolver: MasterResolver,
    origin_dir: Path,
) -> tuple[Optional[int], Optional[int], Optional[str], str, list[str]]:
    """
    Finds NPC record data, prioritizing the target plugin's own contained definitions
    and overrides before querying external master files.

    Returns (vtck_raw, tplt_raw, actor_name, owning_plugin, owning_masters).
    """
    # 1. Target plugin overrides/definitions have highest priority
    if (
        npc_key in local_npc_vtck
        or npc_key in local_npc_tplt
        or npc_key in local_npc_name
        or npc_key.plugin == _norm_plugin(local_plugin_name)
    ):
        return (
            local_npc_vtck.get(npc_key),
            local_npc_tplt.get(npc_key),
            local_npc_name.get(npc_key),
            local_plugin_name,
            local_masters,
        )

    # 2. Query origin master file
    origin_data = master_resolver.get_or_load_master(npc_key.plugin, origin_dir)
    if origin_data:
        return (
            origin_data.npc_to_vtck.get(npc_key),
            origin_data.npc_to_tplt.get(npc_key),
            origin_data.npc_to_name.get(npc_key),
            origin_data.plugin_name,
            origin_data.masters,
        )

    return None, None, None, npc_key.plugin, []


def _find_dial_data(
    dial_key: RecordKey,
    local_plugin_name: str,
    local_masters: list[str],
    local_dial_to_edid: dict[RecordKey, str],
    local_dial_to_qnam: dict[RecordKey, int],
    master_resolver: MasterResolver,
    origin_dir: Path,
) -> tuple[Optional[str], Optional[int], str, list[str]]:
    """
    Retrieves topic_edid and qnam FormID for a given DIAL RecordKey.
    Returns (topic_edid, qnam_raw_formid, owning_plugin, owning_masters).
    """
    if (
        dial_key in local_dial_to_edid
        or dial_key in local_dial_to_qnam
        or dial_key.plugin == _norm_plugin(local_plugin_name)
    ):
        return (
            local_dial_to_edid.get(dial_key),
            local_dial_to_qnam.get(dial_key),
            local_plugin_name,
            local_masters,
        )

    origin_data = master_resolver.get_or_load_master(dial_key.plugin, origin_dir)
    if origin_data:
        return (
            origin_data.dial_to_edid.get(dial_key),
            origin_data.dial_to_qnam.get(dial_key),
            origin_data.plugin_name,
            origin_data.masters,
        )

    return None, None, dial_key.plugin, []


def _find_quest_edid(
    qust_key: RecordKey,
    local_plugin_name: str,
    local_qust_to_edid: dict[RecordKey, str],
    master_resolver: MasterResolver,
    origin_dir: Path,
) -> Optional[str]:
    """
    Retrieves quest_edid for a given QUST RecordKey.
    """
    if qust_key in local_qust_to_edid or qust_key.plugin == _norm_plugin(local_plugin_name):
        return local_qust_to_edid.get(qust_key)

    origin_data = master_resolver.get_or_load_master(qust_key.plugin, origin_dir)
    if origin_data:
        return origin_data.qust_to_edid.get(qust_key)

    return None


def _resolve_voice_type_for_npc(
    speaker_key: RecordKey,
    local_plugin_name: str,
    local_masters: list[str],
    local_npc_vtck: dict[RecordKey, int],
    local_npc_tplt: dict[RecordKey, int],
    local_npc_name: dict[RecordKey, str],
    local_vtyp_edid: dict[RecordKey, str],
    master_resolver: MasterResolver,
    origin_dir: Path,
    warned_esl: Optional[set[int]] = None,
    warned_invalid_index: Optional[set[tuple[int, int]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolves the Actor Name and VoiceType EDID for a given speaker RecordKey.
    Traverses template inheritance (TPLT) if VTCK is not directly defined on the NPC.
    Protected against cycles with a visited set and a maximum traversal depth of 10.

    Returns (actor_name, voice_type_edid).
    """
    visited_templates: set[RecordKey] = set()
    curr_key: Optional[RecordKey] = speaker_key
    depth = 0
    max_depth = 10
    primary_actor_name: Optional[str] = None

    while curr_key is not None and depth < max_depth:
        if curr_key in visited_templates:
            logger.warning("Cyclic TPLT template reference detected for NPC %s", curr_key)
            return primary_actor_name, None

        visited_templates.add(curr_key)
        depth += 1

        vtck_raw, tplt_raw, actor_name, owning_plugin, owning_masters = _find_npc_data(
            curr_key,
            local_plugin_name,
            local_masters,
            local_npc_vtck,
            local_npc_tplt,
            local_npc_name,
            master_resolver,
            origin_dir,
        )

        # Store primary actor name from first NPC in chain if not yet set
        if primary_actor_name is None and actor_name:
            primary_actor_name = actor_name

        # Case 1: NPC has direct VTCK
        if vtck_raw is not None:
            vtck_key = _resolve_record_key(
                vtck_raw, owning_plugin, owning_masters,
                warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
            )
            if vtck_key is not None:
                # Check if target plugin has an override/definition for this VTYP first
                if vtck_key in local_vtyp_edid:
                    return primary_actor_name, local_vtyp_edid[vtck_key]
                if vtck_key.plugin == _norm_plugin(local_plugin_name):
                    return primary_actor_name, local_vtyp_edid.get(vtck_key)

                origin_vtyp_data = master_resolver.get_or_load_master(vtck_key.plugin, origin_dir)
                if origin_vtyp_data:
                    resolved_vtyp = origin_vtyp_data.vtyp_to_edid.get(vtck_key)
                    if resolved_vtyp is None:
                        logger.warning("VoiceType %s not found in master '%s'", vtck_key, vtck_key.plugin)
                    return primary_actor_name, resolved_vtyp
            else:
                logger.warning("Invalid VTCK FormID 0x%08X on NPC %s", vtck_raw, curr_key)
            return primary_actor_name, None

        # Case 2: No direct VTCK, check TPLT inheritance
        if tplt_raw is not None:
            curr_key = _resolve_record_key(
                tplt_raw, owning_plugin, owning_masters,
                warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
            )
            continue

        # Case 3: Neither VTCK nor TPLT present
        break

    if depth >= max_depth:
        logger.warning("Exceeded maximum TPLT template recursion depth (%d) for NPC %s", max_depth, speaker_key)

    return primary_actor_name, None


def parse_esp_file(
    filepath: str | Path,
    master_search_paths: Optional[Sequence[Path | str]] = None,
) -> List[StringEntry]:
    """
    Parses a Skyrim Bethesda Plugin file (.esp, .esm, .esl) and extracts all
    translatable strings, quests, and dialogue responses into StringEntry items.
    Follows the speaker relation chain across masters in read-only mode:
      INFO (ANAM) -> NPC_ (VTCK / TPLT) -> VTYP (EDID).
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

    # Extract declared masters and localized status in order from TES4 header
    local_masters: list[str] = []
    is_localized = False
    for tag, flags, _form_id_val, _form_id_hex, body, _parent_dial in _iter_records(data):
        if tag == b"TES4":
            local_masters = _extract_masters_from_tes4(body)
            if flags & FLAG_LOCALIZED:
                is_localized = True
            break

    plugin_name = path.name
    canonical_plugin_names = {
        _norm_plugin(plugin_name): plugin_name,
        **{_norm_plugin(master): master for master in local_masters},
    }
    master_resolver = MasterResolver(search_paths=master_search_paths)
    warned_esl: set[int] = set()
    warned_invalid_index: set[tuple[int, int]] = set()
    warned_string_index: set[tuple[str, str]] = set()

    # Pass 1: Build local indexes for VoiceTypes, NPC records, and EditorIDs
    local_npc_to_vtck: dict[RecordKey, int] = {}
    local_npc_to_tplt: dict[RecordKey, int] = {}
    local_npc_to_name: dict[RecordKey, str] = {}
    local_vtyp_to_edid: dict[RecordKey, str] = {}
    local_qust_to_edid: dict[RecordKey, str] = {}
    local_dial_to_edid: dict[RecordKey, str] = {}
    local_dial_to_qnam: dict[RecordKey, int] = {}

    for tag, _flags, form_id_val, _form_id_hex, body, _parent_dial in _iter_records(data):
        rec_key = _resolve_record_key(
            form_id_val, plugin_name, local_masters,
            warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
        )
        if rec_key is None:
            continue

        if tag == b"VTYP":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and payload:
                    local_vtyp_to_edid[rec_key] = _decode_string(payload).strip()
        elif tag == b"QUST":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and payload:
                    local_qust_to_edid[rec_key] = _decode_string(payload).strip()
                    break
        elif tag == b"DIAL":
            d_edid: Optional[str] = None
            d_qnam: Optional[int] = None
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID":
                    d_edid = _decode_string(payload).strip()
                elif s_type == b"QNAM" and len(payload) >= 4:
                    d_qnam = int.from_bytes(payload[:4], "little")
            if d_edid is not None:
                local_dial_to_edid[rec_key] = d_edid
            if d_qnam is not None:
                local_dial_to_qnam[rec_key] = d_qnam
        elif tag == b"NPC_":
            edid = None
            full_name = None
            vtck_formid = None
            tplt_formid = None
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and payload:
                    edid = _decode_string(payload).strip()
                elif s_type == b"FULL" and payload and not is_localized:
                    full_name = _decode_string(payload).strip()
                elif s_type == b"VTCK" and len(payload) >= 4:
                    vtck_formid = int.from_bytes(payload[:4], "little")
                elif s_type == b"TPLT" and len(payload) >= 4:
                    tplt_formid = int.from_bytes(payload[:4], "little")

            if full_name and _is_valid_text(full_name):
                local_npc_to_name[rec_key] = full_name
            elif edid and _is_valid_text(edid):
                local_npc_to_name[rec_key] = edid

            if vtck_formid is not None:
                local_npc_to_vtck[rec_key] = vtck_formid
            if tplt_formid is not None:
                local_npc_to_tplt[rec_key] = tplt_formid

    # If the target plugin is localized, external .STRINGS tables are required.
    # Ingesting raw 4-byte StringIDs as inline text would corrupt translation data.
    if is_localized:
        logger.warning(
            "Plugin '%s' has FLAG_LOCALIZED enabled. External .STRINGS parsing is not supported yet; "
            "skipping localized binary StringIDs to prevent translating invalid text.",
            path.name
        )
        return []

    # Pass 2: Extract translatable strings and resolve dialogue voice types
    entries: List[StringEntry] = []
    # Indexed 1->N identity: (form_id, subrecord, string_index). Multi-response
    # INFO.NAM1 / QUST.NNAM records emit one entry per resolved index. For
    # string_index=None no index is ever invented, so unresolved-index
    # duplicates of the same (form_id, subrecord) collapse to the first
    # occurrence; the DSD layer fails fast on any unresolved indexed entry.
    seen_keys: set[tuple[str, bytes, Optional[int]]] = set()

    for tag, _flags, form_id_val, form_id_hex, body, parent_dial_formid in _iter_records(data):
        if tag not in INTERESTING_RECORDS:
            continue

        record_key = _resolve_record_key(
            form_id_val, plugin_name, local_masters,
            warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
        )
        defining_plugin = None
        local_object_id = None
        if record_key is not None:
            defining_plugin = canonical_plugin_names.get(record_key.plugin, record_key.plugin)
            local_object_id = record_key.object_id

        record_type = tag.decode("ascii", errors="ignore")
        editor_id = _extract_record_editor_id(body)
        speaker_formid: Optional[int] = None
        info_qsti_formid: Optional[int] = None
        quest_edid: Optional[str] = None
        topic_edid: Optional[str] = None

        if tag == b"INFO":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"ANAM" and len(payload) >= 4:
                    speaker_formid = int.from_bytes(payload[:4], "little")
                elif s_type == b"QSTI" and len(payload) >= 4:
                    info_qsti_formid = int.from_bytes(payload[:4], "little")

            if parent_dial_formid is not None:
                dial_key = _resolve_record_key(
                    parent_dial_formid, plugin_name, local_masters,
                    warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
                )
                if dial_key is not None:
                    d_edid, qnam_raw, dial_owning_plugin, dial_owning_masters = _find_dial_data(
                        dial_key,
                        plugin_name,
                        local_masters,
                        local_dial_to_edid,
                        local_dial_to_qnam,
                        master_resolver,
                        path.parent,
                    )
                    topic_edid = d_edid
                    target_qust_formid = qnam_raw if qnam_raw is not None else info_qsti_formid
                    qust_owning_plugin = dial_owning_plugin if qnam_raw is not None else plugin_name
                    qust_owning_masters = dial_owning_masters if qnam_raw is not None else local_masters

                    if target_qust_formid is not None:
                        qust_key = _resolve_record_key(
                            target_qust_formid, qust_owning_plugin, qust_owning_masters,
                            warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
                        )
                        if qust_key is not None:
                            quest_edid = _find_quest_edid(
                                qust_key,
                                plugin_name,
                                local_qust_to_edid,
                                master_resolver,
                                path.parent,
                            )
            elif info_qsti_formid is not None:
                qust_key = _resolve_record_key(
                    info_qsti_formid, plugin_name, local_masters,
                    warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
                )
                if qust_key is not None:
                    quest_edid = _find_quest_edid(
                        qust_key,
                        plugin_name,
                        local_qust_to_edid,
                        master_resolver,
                        path.parent,
                    )

        actor_name: Optional[str] = None
        voice_type: Optional[str] = None

        if speaker_formid is not None:
            speaker_key = _resolve_record_key(
                speaker_formid, plugin_name, local_masters,
                warned_esl=warned_esl, warned_invalid_index=warned_invalid_index
            )
            if speaker_key is not None:
                resolved_actor, resolved_voice = _resolve_voice_type_for_npc(
                    speaker_key,
                    plugin_name,
                    local_masters,
                    local_npc_to_vtck,
                    local_npc_to_tplt,
                    local_npc_to_name,
                    local_vtyp_to_edid,
                    master_resolver,
                    path.parent,
                    warned_esl=warned_esl,
                    warned_invalid_index=warned_invalid_index,
                )
                actor_name = resolved_actor or f"Actor_{speaker_formid:08X}"
                voice_type = resolved_voice
            else:
                actor_name = f"Actor_{speaker_formid:08X}"

        if tag == b"NPC_" and not actor_name:
            if record_key is not None and record_key in local_npc_to_name:
                actor_name = local_npc_to_name[record_key]
            else:
                actor_name = f"Actor_{form_id_hex}"

        current_info_response_index: Optional[int] = None
        current_quest_objective_index: Optional[int] = None

        for s_type, payload in _read_subrecords(body):
            if tag == b"INFO" and s_type == b"TRDT":
                current_info_response_index = _parse_info_response_number(payload)
                if current_info_response_index is None:
                    gap = ("malformed_trdt", form_id_hex)
                    if gap not in warned_string_index:
                        warned_string_index.add(gap)
                        logger.warning(
                            "INFO %s has malformed TRDT (%d bytes); NAM1 index will remain unresolved",
                            form_id_hex, len(payload)
                        )
                continue

            if tag == b"QUST" and s_type == b"QOBJ":
                current_quest_objective_index = _parse_quest_objective_index(payload)
                if current_quest_objective_index is None:
                    gap = ("malformed_qobj", form_id_hex)
                    if gap not in warned_string_index:
                        warned_string_index.add(gap)
                        logger.warning(
                            "QUST %s has malformed QOBJ (%d bytes); NNAM index will remain unresolved",
                            form_id_hex, len(payload)
                        )
                continue

            is_text_subrecord = s_type in INTERESTING_SUBRECORDS or (
                s_type == b"DNAM" and tag in DNAM_TEXT_RECORDS
            )
            if not is_text_subrecord or not payload:
                # A skipped NAM1/NNAM still consumes its pending index so the
                # next indexed string cannot inherit a stale TRDT/QOBJ value.
                if tag == b"INFO" and s_type == b"NAM1":
                    current_info_response_index = None
                elif tag == b"QUST" and s_type == b"NNAM":
                    current_quest_objective_index = None
                continue

            text_val = _decode_string(payload).strip()
            if not text_val:
                if tag == b"INFO" and s_type == b"NAM1":
                    current_info_response_index = None
                elif tag == b"QUST" and s_type == b"NNAM":
                    current_quest_objective_index = None
                continue

            is_dialog = (tag == b"INFO" and s_type == b"NAM1")
            string_index: Optional[int] = None
            if is_dialog:
                string_index = current_info_response_index
                if string_index is None:
                    gap = ("nam1_missing_trdt", form_id_hex)
                    if gap not in warned_string_index:
                        warned_string_index.add(gap)
                        logger.warning(
                            "INFO %s NAM1 has no valid preceding TRDT response number",
                            form_id_hex
                        )
                current_info_response_index = None
            elif tag == b"QUST" and s_type == b"NNAM":
                string_index = current_quest_objective_index
                if string_index is None:
                    gap = ("nnam_missing_qobj", form_id_hex)
                    if gap not in warned_string_index:
                        warned_string_index.add(gap)
                        logger.warning(
                            "QUST %s NNAM has no valid preceding QOBJ objective index",
                            form_id_hex
                        )
                current_quest_objective_index = None

            unique_key = (form_id_hex, s_type, string_index)
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            entries.append(
                StringEntry(
                    form_id=form_id_hex,
                    text=text_val,
                    is_dialog=is_dialog,
                    actor=actor_name,
                    voice_type=voice_type,
                    defining_plugin=defining_plugin,
                    local_object_id=local_object_id,
                    record_type=record_type,
                    subrecord_type=s_type.decode("ascii", errors="ignore"),
                    string_index=string_index,
                    editor_id=editor_id,
                    quest_edid=quest_edid if is_dialog else None,
                    topic_edid=topic_edid if is_dialog else None,
                )
            )

    return entries
