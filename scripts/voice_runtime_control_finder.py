"""Find vanilla INFO dialogue lines suitable as an in-game voice runtime control.

Read-only analysis of ``Skyrim.esm`` and the vanilla voice BSAs, producing a
strictly-ranked shortlist of dialogue records prepared for manual runtime
validation in-game with ``player.placeatme`` + ``say``. LOW risk is a heuristic,
never a runtime-proven control.

A candidate MUST be deterministic at runtime:

1. **DIAL cardinality**: the DIAL's Topic-children GRUP contains exactly one
   INFO (``child_info_count == 1``), so ``say <DIAL>`` cannot branch. "One
   INFO with one TRDT" and "one DIAL with exactly one INFO child" are two
   distinct gates and both are counted separately.
2. **Speaker identity**: ``INFO.ANAM`` must resolve to an ``NPC_`` with a
   known ``VTYP`` VoiceType. Talking Activators and other actor base types
   are rejected, never silently inferred as ``NPC_``.
3. **Token determinism**: exactly one TRDT response, zero CTDA, resolvable
   quest/topic EditorIDs.
4. **Exact asset existence**: the full normalized path
   ``Sound\\Voice\\Skyrim.esm\\<VoiceType>\\<basename>.fuz`` must exist in a
   vanilla voices BSA. Only an exact equality between the normalized expected
   path and the normalized BSA path counts; basename-only existence is not
   accepted.

The pipeline order is contractual: structural candidates are collected first
(no risk assigned), then exact BSA paths are matched, then exact-match
metadata is populated, and only then is runtime risk classified. Structural
candidates without an exact FUZ match keep ``runtime_risk`` unset (``None``)
and can never be LOW.

The BSA index is built strictly from BSA header/name-table metadata using the
real record sizes and totals (no fixed-size read window, no payload
extraction, archives opened read-only). Every structural assumption is
cross-validated against header totals and per-file name hashes, and any
unsupported or corrupt structure fails fast.

Output is written to ``docs/evidence/voice-in-game-proof/``.
``Skyrim.esm`` is localized: ``NAM1`` payloads are string-table IDs, never text.
"""

from __future__ import annotations

import json
import logging
import struct
import sys
from pathlib import Path
from typing import Any, BinaryIO

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_toolchain import discover_game_root  # noqa: E402

from src.esp_parser import _iter_records, _read_subrecords  # noqa: E402
from src.voice_assets import build_voice_basename  # noqa: E402

logger = logging.getLogger(__name__)

VOICES_BSA_FILES = ("Skyrim - Voices_en0.bsa", "Skyrim - Voices_es0.bsa")
PLUGIN_FOR_VOICE = "Skyrim.esm"

MAX_CANDIDATES_REPORTED = 25
BSA_MAGIC = b"BSA\x00"
BSA_TES5_VERSION = 105
BSA_HEADER_SIZE = 36
BSA_FOLDER_RECORD_SIZE = 24
BSA_FILE_RECORD_SIZE = 16
BSA_ARCHIVE_FLAG_FILE_NAMES = 0x1
BSA_ARCHIVE_FLAG_FOLDER_NAMES = 0x2

# Preferred/early quest-EDID prefix heuristic: a naming-convention signal used
# to rank candidates. It does NOT prove runtime quest availability and never
# upgrades a candidate on its own.
EARLY_QUEST_PREFIXES = ("MQ101", "MQ102", "MQ103", "MS01", "MS02", "MS03", "DA01", "Favor")

_COMMON_GENERIC_VOICES = frozenset(
    {
        "MaleNord",
        "FemaleNord",
        "MaleEvenToned",
        "FemaleEvenToned",
        "MaleCommoner",
        "FemaleCommoner",
        "MaleBandit",
        "FemaleBandit",
        "MaleGuard",
        "FemaleGuard",
        "MaleSoldier",
        "FemaleSoldier",
        "MaleYoungEager",
        "FemaleYoungEager",
        "MaleCommander",
        "FemaleCommander",
        "MaleElfHaughty",
        "FemaleElfHaughty",
    }
)


class BsaVoiceLoadError(RuntimeError):
    """Raised when a voices BSA header/name table is unsupported or corrupt."""


def _read_exact(handle: BinaryIO, size: int, label: str) -> bytes:
    """Read exactly ``size`` bytes or fail fast with a bounds error."""
    data = handle.read(size)
    if len(data) < size:
        raise BsaVoiceLoadError(f"{label}: truncated (wanted {size} bytes, got {len(data)})")
    return data


def _tes5_name_hash_low32(stem: bytes) -> int:
    """Low 32 bits of the TES5 per-file BSA name hash over the extension-less basename.

    Empirically derived and validated against the installed vanilla voice
    archives read-only (``Skyrim - Voices_en0.bsa``: 75408/75408 names,
    ``Skyrim - Voices_es0.bsa``: 74716/74716 names):
    ``low32 = (first << 24) | (length << 16) | (penultimate << 8) | last``.
    """
    n = len(stem)
    if n == 0:
        return 0
    if n == 1:
        return (stem[0] << 24) | (n << 16)
    return (stem[0] << 24) | (n << 16) | (stem[n - 2] << 8) | stem[n - 1]


class BsaVoiceIndex:
    """Exact per-file index of a TES5 v105 voices BSA, built from header metadata.

    Only the header, folder/file name tables and folder-record metadata are
    read. Voice payload data is never read or extracted and the archive is
    never modified.

    Layout contract (validated against both installed vanilla voice archives):

    - 36-byte header (magic ``BSA\\0``, version 105, totals and counts). The
      declared folder-records offset is validated to equal 36: vanilla TES5
      v105 archives always place folder records immediately after the header,
      and any other value is treated as unsupported rather than honored.
    - Folder records: 24 bytes each (name hash u64, file count u32, reserved
      u32, data offset u64). The reserved dword is ignored: the installed
      archives carry a nonzero value in exactly one record without affecting
      any count.
    - Interleaved region, in folder-record order: one length byte (value
      includes the NUL terminator), the NUL-terminated folder name, then
      ``fileCount`` 16-byte file records (name hash u64, size u32, offset u32).
    - Global file-name block: ``totalFileNameLength`` bytes of consecutive
      NUL-terminated basenames (no length prefix), exactly ``fileCount``
      names, sequentially paired with the file records above.
    - Every mapped name must reproduce its file-record hash low 32 bits,
      which proves the folder/name/record pairing instead of assuming it.

    Validation counters (``header_file_count``, ``parsed_file_names``,
    ``hash_validated``, ``hash_mismatches``) substantiate the empirical proof
    and are persisted into the evidence metadata: a successful index requires
    ``header_file_count == parsed_file_names == hash_validated`` with
    ``hash_mismatches == 0``.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.full_paths: set[str] = set()  # lowercased "folder\\filename.ext"
        self.folder_files: dict[str, set[str]] = {}
        self.name_table_bytes = 0
        self.header_file_count = 0
        self.parsed_file_names = 0
        self.hash_validated = 0
        self.hash_mismatches = 0
        self._load()

    def _load(self) -> None:
        with self.path.open("rb") as handle:
            label = self.path.name

            header = _read_exact(handle, BSA_HEADER_SIZE, f"{label}: header")
            magic, version, folder_records_offset = struct.unpack_from("<4sIi", header, 0)
            if magic != BSA_MAGIC:
                raise BsaVoiceLoadError(f"{label}: not a BSA (magic={magic!r})")
            if version != BSA_TES5_VERSION:
                raise BsaVoiceLoadError(f"{label}: unsupported BSA version {version} (expected {BSA_TES5_VERSION})")
            if folder_records_offset != BSA_HEADER_SIZE:
                raise BsaVoiceLoadError(
                    f"{label}: unsupported folder-records offset {folder_records_offset} "
                    f"(vanilla TES5 v105 archives pin it to {BSA_HEADER_SIZE})"
                )

            (
                archive_flags,
                folder_count,
                file_count,
                total_folder_name_length,
                total_file_name_length,
                _file_flags,
            ) = struct.unpack_from("<IIIIII", header, 12)

            if not archive_flags & BSA_ARCHIVE_FLAG_FILE_NAMES or not archive_flags & BSA_ARCHIVE_FLAG_FOLDER_NAMES:
                raise BsaVoiceLoadError(
                    f"{label}: archive flags {archive_flags:#x} omit folder/file names; cannot build an exact index"
                )

            # 1) Folder records array.
            folder_records = _read_exact(handle, folder_count * BSA_FOLDER_RECORD_SIZE, f"{label}: folder records")
            counts: list[int] = []
            for i in range(folder_count):
                count = struct.unpack_from("<I", folder_records, i * BSA_FOLDER_RECORD_SIZE + 8)[0]
                if count > file_count:
                    raise BsaVoiceLoadError(f"{label}: folder {i} claims {count} files > header total {file_count}")
                counts.append(count)
            if sum(counts) != file_count:
                raise BsaVoiceLoadError(f"{label}: folder counts {sum(counts)} != header fileCount {file_count}")
            self.header_file_count = file_count

            # 2) Interleaved region: per folder, in record order, a
            #    length-prefixed NUL-terminated folder name followed by
            #    fileCount 16-byte file records. Record name hashes are kept
            #    for pairing validation; no asset payload is read.
            folder_names: list[str] = []
            record_hashes: list[int] = []
            interleaved_name_bytes = 0
            for i, count in enumerate(counts):
                length = _read_exact(handle, 1, f"{label}: folder name {i} length")[0]
                raw_name = _read_exact(handle, length, f"{label}: folder name {i}")
                if not raw_name.endswith(b"\x00"):
                    raise BsaVoiceLoadError(f"{label}: folder name {i} is not NUL-terminated")
                folder_names.append(raw_name[:-1].decode("ascii", errors="replace").lower())
                interleaved_name_bytes += 1 + length
                for _ in range(count):
                    record = _read_exact(handle, BSA_FILE_RECORD_SIZE, f"{label}: file record in folder {i}")
                    record_hashes.append(struct.unpack_from("<Q", record, 0)[0])
            # Header totalFolderNameLength counts length-byte values (name +
            # NUL) but not the prefix bytes themselves; the on-disk region
            # therefore adds exactly one byte per folder.
            if interleaved_name_bytes != folder_count + total_folder_name_length:
                raise BsaVoiceLoadError(
                    f"{label}: interleaved folder-name bytes {interleaved_name_bytes} != "
                    f"header totalFolderNameLength {total_folder_name_length} + {folder_count}"
                )

            # 3) Global file-name block: exactly totalFileNameLength bytes of
            #    consecutive NUL-terminated names covering all fileCount files.
            file_name_block = _read_exact(handle, total_file_name_length, f"{label}: file name table")
            file_names = file_name_block.split(b"\x00")[:-1]
            if len(file_names) != file_count:
                raise BsaVoiceLoadError(f"{label}: parsed {len(file_names)} file names != header {file_count}")
            if sum(len(raw) + 1 for raw in file_names) != total_file_name_length:
                raise BsaVoiceLoadError(
                    f"{label}: file-name bytes do not tile the header totalFileNameLength {total_file_name_length}"
                )
            self.parsed_file_names = len(file_names)

            self.name_table_bytes = interleaved_name_bytes + total_file_name_length

            # 4) Pair folders with their file names sequentially and prove the
            #    pairing through the per-file name hash (low 32 bits).
            cursor = 0
            for folder_key, count in zip(folder_names, counts, strict=True):
                bucket: set[str] = set()
                for _ in range(count):
                    raw = file_names[cursor]
                    if not raw.endswith(b".fuz"):
                        raise BsaVoiceLoadError(f"{label}: non-.fuz entry {raw!r} in a voices archive is unsupported")
                    stem = raw[:-4]
                    if _tes5_name_hash_low32(stem) != record_hashes[cursor] & 0xFFFFFFFF:
                        self.hash_mismatches += 1
                        raise BsaVoiceLoadError(f"{label}: name-hash mismatch at file index {cursor} ({raw!r})")
                    self.hash_validated += 1
                    bucket.add(stem.decode("ascii", errors="replace").lower() + ".fuz")
                    cursor += 1
                self.folder_files[folder_key] = bucket
                for filename in bucket:
                    self.full_paths.add(f"{folder_key}\\{filename}")
            if cursor != file_count:
                raise BsaVoiceLoadError(f"{label}: consumed {cursor} file names != header {file_count}")

    def contains(self, folder: str, filename: str) -> bool:
        """Confirm an exact lowercased ``folder\\filename`` path exists."""
        return f"{folder.lower()}\\{filename.lower()}" in self.full_paths


def _bsa_meta_for(path: Path, index: BsaVoiceIndex) -> dict[str, int]:
    """Persisted per-archive validation metadata substantiating the BSA index proof."""
    return {
        "size_bytes": path.stat().st_size,
        "indexed_voice_paths": len(index.full_paths),
        "name_table_bytes": index.name_table_bytes,
        "header_file_count": index.header_file_count,
        "parsed_file_names": index.parsed_file_names,
        "hash_validated": index.hash_validated,
        "hash_mismatches": index.hash_mismatches,
    }


# ---------------------------------------------------------------------------
# Skyrim.esm identity indexing (read-only).
# ---------------------------------------------------------------------------


def _decode_edid(payload: bytes) -> str | None:
    raw = payload.rstrip(b"\x00")
    return raw.decode("ascii", errors="replace") if raw else None


def index_plugin(data: bytes) -> dict[str, Any]:
    """
    Two-pass identity index of a plugin.

    Pass 1 maps every record FormID to its record type, EditorID, and the
    NPC_/VTYP/QUST/DIAL identity subrecords needed for voice resolution.

    Pass 2 collects per-INFO token/condition metadata and the DIAL -> child
    INFO adjacency (needed for the single-child-cardinality gate).
    """
    # Pass 1: record types + identity records.
    record_types: dict[int, str] = {}
    vtyp_edid: dict[int, str] = {}
    npc_edid: dict[int, str] = {}
    npc_vtck: dict[int, int] = {}
    npc_tplt: dict[int, int] = {}
    qust_edid: dict[int, str] = {}
    dial_edid: dict[int, str] = {}
    dial_qnam: dict[int, int] = {}
    dial_dnam: dict[int, int] = {}

    for tag, _flags, fid_val, _fid_hex, body, _parent_dial in _iter_records(data):
        record_types[fid_val] = tag.decode("ascii", errors="replace")
        if tag == b"VTYP":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and (edid := _decode_edid(payload)):
                    vtyp_edid[fid_val] = edid
                    break
        elif tag == b"NPC_":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID":
                    if edid := _decode_edid(payload):
                        npc_edid[fid_val] = edid
                elif s_type == b"VTCK" and len(payload) >= 4:
                    npc_vtck[fid_val] = int.from_bytes(payload[:4], "little")
                elif s_type == b"TPLT" and len(payload) >= 4:
                    npc_tplt[fid_val] = int.from_bytes(payload[:4], "little")
        elif tag == b"QUST":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and (edid := _decode_edid(payload)):
                    qust_edid[fid_val] = edid
                    break
        elif tag == b"DIAL":
            for s_type, payload in _read_subrecords(body):
                if s_type == b"EDID" and (edid := _decode_edid(payload)):
                    dial_edid[fid_val] = edid
                elif s_type == b"QNAM" and len(payload) >= 4:
                    dial_qnam[fid_val] = int.from_bytes(payload[:4], "little")
                elif s_type == b"DNAM" and payload:
                    dial_dnam[fid_val] = payload[0]

    # Pass 2: INFO metadata + DIAL -> child INFO cardinality.
    infos: dict[int, dict[str, Any]] = {}
    dial_children: dict[int, list[int]] = {}
    for tag, _flags, fid_val, fid_hex, body, parent_dial in _iter_records(data):
        if tag != b"INFO" or parent_dial is None:
            continue
        dial_children.setdefault(parent_dial, []).append(fid_val)
        info = infos.setdefault(
            fid_val,
            {
                "form_id_hex": fid_hex,
                "dial_form_id": parent_dial,
                "anam": None,
                "qsti": None,
                "ctda_count": 0,
                "trdt_response_numbers": [],
                "nam1_count": 0,
            },
        )
        for s_type, payload in _read_subrecords(body):
            if s_type == b"ANAM" and len(payload) >= 4:
                info["anam"] = int.from_bytes(payload[:4], "little")
            elif s_type == b"CTDA":
                info["ctda_count"] += 1
            elif s_type == b"TRDT" and len(payload) >= 13:
                info["trdt_response_numbers"].append(payload[12])
            elif s_type == b"NAM1" and payload:
                info["nam1_count"] += 1
            elif s_type == b"QSTI" and len(payload) >= 4:
                info["qsti"] = int.from_bytes(payload[:4], "little")

    return {
        "record_types": record_types,
        "vtyp_edid": vtyp_edid,
        "npc_edid": npc_edid,
        "npc_vtck": npc_vtck,
        "npc_tplt": npc_tplt,
        "qust_edid": qust_edid,
        "dial_edid": dial_edid,
        "dial_qnam": dial_qnam,
        "dial_dnam": dial_dnam,
        "dial_children": dial_children,
        "infos": infos,
    }


def resolve_voice_type(index: dict[str, Any], npc_form_id: int) -> str | None:
    """Follow NPC_.VTCK/TPLT -> VTYP.EDID, tolerating template chains."""
    vtck = index["npc_vtck"].get(npc_form_id)
    if vtck is not None and vtck & 0x00FFFFFF == 0:
        vtck = None

    tplt = index["npc_tplt"].get(npc_form_id)
    seen: set[int] = set()
    while vtck is None and tplt and tplt not in seen:
        seen.add(tplt)
        candidate_vtck = index["npc_vtck"].get(tplt)
        if candidate_vtck and candidate_vtck & 0x00FFFFFF != 0:
            vtck = candidate_vtck
            break
        tplt = index["npc_tplt"].get(tplt)

    if vtck is not None:
        return index["vtyp_edid"].get(vtck)
    return None


def _classify_runtime(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify runtime risk using only evidence surfaced from Skyrim.esm and BSA metadata.

    LOW is granted conservatively: an ordinary ``NPC_`` speaker using a generic
    humanoid VoiceType, a preferred/early quest-EDID prefix (a naming heuristic
    only; runtime quest availability is NOT proven by it), zero CTDA, a single
    child INFO, and a confirmed exact vanilla FUZ path match. LOW is only
    reachable after exact-match metadata has been populated: a candidate whose
    ``matched_full_fuz_path`` is empty can never classify LOW. A LOW-risk
    candidate is a risk heuristic, not a runtime-proven control.
    Scene hints, non-NPC speakers, unresolved voices, unique/special VoiceTypes
    and non-early quests are escalated with explicit reasons and never labelled
    LOW without reproducible justification. Empty topic EDIDs are the vanilla
    norm for single-child DIALs (the deterministic CK basename encodes them),
    and TES5 ``DIAL`` records carry no ``DNAM`` topic-type subrecord (verified
    against Skyrim.esm: 15037/15037 DIALs without DNAM), so neither is treated
    as special-context evidence; the raw topic type is still registered in the
    candidate when present.
    """
    reasons: list[str] = []

    if not candidate.get("matched_full_fuz_path"):
        reasons.append("no exact vanilla FUZ path match confirmed")

    if candidate["speaker_record_type"] != "NPC_":
        reasons.append(f"speaker is {candidate['speaker_record_type']}, not NPC_")
    if not candidate["voice_type"]:
        reasons.append("voice_type unresolved")
    elif candidate["voice_type"] not in _COMMON_GENERIC_VOICES:
        reasons.append(f"non-generic/special VoiceType {candidate['voice_type']}")

    dial_topic_type = candidate.get("dial_topic_type")
    if dial_topic_type:
        reasons.append(f"DIAL DNAM topic type {dial_topic_type} is non-default")

    haystack = f"{candidate['quest_edid']} {candidate['topic_edid']}".lower()
    if "scene" in haystack:
        reasons.append("scene-associated name (quest/topic)")

    if not candidate["quest_edid"].startswith(EARLY_QUEST_PREFIXES):
        reasons.append(f"non-early quest prefix {candidate['quest_edid']}")

    if not reasons:
        return (
            "LOW",
            ["ordinary NPC_, generic voice, early quest-prefix heuristic, single child, exact vanilla FUZ match"],
        )
    if len(reasons) == 1:
        return ("MEDIUM", reasons)
    return ("HIGH", reasons)


def collect_candidates(data: bytes) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply the tight runtime-determinism funnel over indexed INFO records."""
    index = index_plugin(data)

    stats: dict[str, int] = {
        "infos_total": len(index["infos"]),
        "explicit_anam": 0,
        "npc_speaker": 0,
        "voice_resolved": 0,
        "single_response": 0,
        "zero_ctda": 0,
        "single_child_dial": 0,
        "quest_resolved": 0,
    }

    candidates: list[dict[str, Any]] = []
    for info_form_id, info in index["infos"].items():
        if info["anam"] is None:
            continue
        stats["explicit_anam"] += 1

        anam_form_id = info["anam"]
        speaker_type = index["record_types"].get(anam_form_id, "?")
        if speaker_type != "NPC_":
            continue
        stats["npc_speaker"] += 1

        voice_type = resolve_voice_type(index, anam_form_id)
        if voice_type is None:
            continue
        stats["voice_resolved"] += 1

        if len(info["trdt_response_numbers"]) != 1 or info["nam1_count"] < 1:
            continue
        stats["single_response"] += 1
        if info["ctda_count"] != 0:
            continue
        stats["zero_ctda"] += 1

        dial_form_id = info["dial_form_id"]
        child_info_count = len(index["dial_children"].get(dial_form_id, []))
        if child_info_count != 1:
            continue
        stats["single_child_dial"] += 1

        topic_edid = index["dial_edid"].get(dial_form_id) or ""
        quest_form_id = index["dial_qnam"].get(dial_form_id) or info["qsti"]
        quest_edid = index["qust_edid"].get(quest_form_id) if quest_form_id else None
        if not quest_edid:
            continue
        stats["quest_resolved"] += 1

        local_object_id = info_form_id & 0x00FFFFFF
        response = info["trdt_response_numbers"][0]
        basename = build_voice_basename(
            quest_edid=quest_edid,
            topic_edid=topic_edid,
            local_object_id=local_object_id,
            response_number=response,
        )

        candidate = {
            "dial_form_id": dial_form_id,
            "dial_form_hex": f"0x{dial_form_id & 0xFFFFFFFF:08X}",
            "info_form_id": info_form_id,
            "info_form_hex": f"0x{info_form_id & 0xFFFFFFFF:08X}",
            "anam_form_id": anam_form_id,
            "anam_form_hex": f"0x{anam_form_id & 0xFFFFFFFF:08X}",
            "npc_edid": index["npc_edid"].get(anam_form_id, ""),
            "speaker_record_type": speaker_type,
            "voice_type": voice_type,
            "quest_form_id": quest_form_id,
            "quest_form_hex": f"0x{quest_form_id & 0xFFFFFFFF:08X}",
            "quest_edid": quest_edid,
            "topic_edid": topic_edid,
            "dial_topic_type": index["dial_dnam"].get(dial_form_id),
            "child_info_count": child_info_count,
            "response_number": response,
            "ctda_count": info["ctda_count"],
            "basename": basename,
            "expected_full_fuz_path": (f"Sound\\Voice\\{PLUGIN_FOR_VOICE}\\{voice_type}\\{basename}.fuz"),
            "matched_full_fuz_path": "",
            "matching_bsas": [],
            "runtime_risk": None,
            "runtime_risk_reasons": [],
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda c: (
            0 if c["quest_edid"].startswith(EARLY_QUEST_PREFIXES) else 1,
            c["voice_type"],
            c["quest_edid"],
            c["topic_edid"],
        )
    )
    return candidates, stats


def _match_candidate(candidate: dict[str, Any], indexes: list[BsaVoiceIndex]) -> tuple[str, list[str]] | None:
    """Exact full-path match: Sound\\Voice\\Skyrim.esm\\<VoiceType>\\<basename>.fuz.

    Returns ``(normalized_matched_path, matching_bsas)`` or ``None``.
    ``matching_bsas`` lists every provided archive containing the exact full
    path, in enumeration order; it is an attribution of all archives holding
    the asset, not a claim about which archive the game selects at load time.
    Only an exact equality between the normalized expected path and the
    normalized BSA path counts as a match.
    """
    folder = f"sound\\voice\\{PLUGIN_FOR_VOICE.lower()}\\{candidate['voice_type'].lower()}"
    filename = f"{candidate['basename'].lower()}.fuz"
    matching_bsas = [index.path.name for index in indexes if index.contains(folder, filename)]
    if not matching_bsas:
        return None
    return f"{folder}\\{filename}", matching_bsas


def match_and_classify(candidates: list[dict[str, Any]], indexes: list[BsaVoiceIndex]) -> list[dict[str, Any]]:
    """Exact-match structural candidates against the vanilla voice BSAs, then classify risk.

    Pipeline order is contractual: exact BSA path matching first, exact-match
    metadata population second, and only then ``runtime_risk`` classification.
    Candidates without an exact match keep ``runtime_risk`` unset (``None``)
    and are not returned; LOW is unreachable without a confirmed exact FUZ path.
    """
    matched: list[dict[str, Any]] = []
    for candidate in candidates:
        match = _match_candidate(candidate, indexes)
        if match is None:
            continue
        candidate["matched_full_fuz_path"], candidate["matching_bsas"] = match
        candidate["runtime_risk"], candidate["runtime_risk_reasons"] = _classify_runtime(candidate)
        matched.append(candidate)
    return matched


def _render_markdown(
    stats: dict[str, int],
    bsa_meta: dict[str, dict[str, int]],
    matched: list[dict[str, Any]],
) -> str:
    """Render the evidence Markdown with full runtime identity per candidate."""
    lines = [
        "# Voice runtime control - vanilla candidates",
        "",
        "Structurally deterministic vanilla candidates prepared for manual runtime "
        "validation with `player.placeatme <ANAM BaseFormID>` + `say <DIAL FormID>` "
        "(all identity fields below come from the read-only finder run; no Skyrim.esm "
        "re-consultation needed).",
        "",
        "Reading this evidence:",
        "",
        "- `ANAM` is the NPC **base FormID**. `player.placeatme` spawns a new actor whose "
        "runtime reference FormID is created at runtime; never fabricate a reference FormID.",
        "- `say` is a reference command: it must be executed on the spawned reference "
        "selected in the console, not on the base FormID.",
        "- The `quest_edid` prefix gate is only a preferred/early quest-prefix heuristic; "
        "runtime quest availability was not proven.",
        "- A LOW-risk candidate is a risk heuristic, not a runtime-proven control. No "
        'candidate below is "working", "runtime-proven", or "verified in-game" yet.',
        "",
        f"Funnel: `{json.dumps(stats, sort_keys=True)}`",
        f"BSA metadata: `{json.dumps(bsa_meta, sort_keys=True)}`",
        "",
        "| # | NPC (EDID) | Speaker | ANAM | VoiceType | Quest | Topic | DIAL | INFO | Resp | CTDA | Child INFO | Risk |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(matched, start=1):
        lines.append(
            f"| {i} | `{c['npc_edid']}` | {c['speaker_record_type']} | `{c['anam_form_hex']}` "
            f"| {c['voice_type']} | {c['quest_edid']} | `{c['topic_edid']}` "
            f"| `{c['dial_form_hex']}` | `{c['info_form_hex']}` | {c['response_number']} "
            f"| {c['ctda_count']} | {c['child_info_count']} | {c['runtime_risk']} |"
        )

    lines += [
        "",
        "## Manual runtime reproduction procedure",
        "",
        "Per candidate: spawn the NPC with its base FormID, then select/click the "
        "spawned reference in the console and verify it, and only then run `say` on "
        "that selected reference. The runtime reference FormID is created at runtime "
        "and is intentionally not listed here.",
        "",
        "```text",
    ]
    for c in matched:
        anam = c["anam_form_hex"][2:]
        lines += [
            f"# {c['npc_edid']} ({c['voice_type']}) - {c['quest_edid']} / {c['topic_edid']} [{c['runtime_risk']}]",
            f"player.placeatme {anam} 1",
            "",
            f"# In the console, select/click the newly spawned {c['npc_edid']}.",
            f"# Verify its BaseID is {anam}.",
            "# Only with that NPC reference selected:",
            "",
            f"say {c['dial_form_hex'][2:]}",
            f"# INFO {c['info_form_hex']} | FUZ {c['matched_full_fuz_path']} | matching BSAs: {', '.join(c['matching_bsas'])}",
            "",
        ]
    lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> int:
    """CLI entry point: build the runtime-control shortlist and write evidence."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    game_root = discover_game_root()
    skyrim_esm = game_root / "Data" / "Skyrim.esm"
    logger.info("Parsing %s (read-only)", skyrim_esm)
    data = skyrim_esm.read_bytes()

    candidates, stats = collect_candidates(data)
    logger.info("Structural funnel: %s", json.dumps(stats, sort_keys=True))
    logger.info("%d structural candidates before exact BSA match", len(candidates))

    indexes: list[BsaVoiceIndex] = []
    bsa_meta: dict[str, dict[str, int]] = {}
    for name in VOICES_BSA_FILES:
        path = game_root / "Data" / name
        index = BsaVoiceIndex(path)
        indexes.append(index)
        bsa_meta[name] = _bsa_meta_for(path, index)
        logger.info(
            "%s: %d voice paths indexed (hash-validated %d/%d, mismatches %d)",
            name,
            len(index.full_paths),
            index.hash_validated,
            index.header_file_count,
            index.hash_mismatches,
        )

    matched = match_and_classify(candidates, indexes)
    stats["exact_fuz_match"] = len(matched)
    stats["runtime_low_risk"] = sum(1 for c in matched if c["runtime_risk"] == "LOW")
    stats["reported_count"] = min(MAX_CANDIDATES_REPORTED, len(matched))
    logger.info("%d candidates have an exact vanilla FUZ path match", len(matched))

    out_dir = REPO_ROOT / "docs" / "evidence" / "voice-in-game-proof"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stats": stats,
        "bsa_meta": bsa_meta,
        "runtime_controls": matched[:MAX_CANDIDATES_REPORTED],
    }
    (out_dir / "voice_runtime_controls.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")

    markdown = _render_markdown(stats, bsa_meta, matched[:MAX_CANDIDATES_REPORTED])
    (out_dir / "voice_runtime_controls.md").write_text(markdown, encoding="utf-8", newline="\n")
    logger.info("Evidence written to %s", out_dir / "voice_runtime_controls.md")
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
