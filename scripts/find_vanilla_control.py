"""Find a vanilla INFO dialogue line suitable as the PR #9 runtime control.

Read-only analysis of ``Skyrim.esm`` and the vanilla voice wav/DV tool BSAs:

1. Raw pass over ``Skyrim.esm`` indexing VTYP/NPC_/QUST/DIAL identity subrecords.
2. Raw pass collecting every INFO with ANAM speaker, TRDT response numbers,
   NAM1 presence and CTDA condition count.
3. Filter per the spike contract: explicit ANAM chain resolved to a known
   VoiceType, exactly one response, zero CTDA, resolvable quest EditorID
   (topic EditorID may be empty; the CK basename encodes that as empty).
4. Deterministic CK basename (``src.voice_assets``) and existence lookup in
   ``Skyrim - Voices_en0.bsa`` / ``es0.bsa``.

``Skyrim.esm`` is localized: NAM1 payloads are string-table IDs, never text.
"""

from __future__ import annotations

import json
import logging
import re
import struct
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_toolchain import discover_game_root  # noqa: E402

from src.esp_parser import _iter_records, _read_subrecords  # noqa: E402
from src.voice_assets import build_voice_basename  # noqa: E402

logger = logging.getLogger(__name__)

VOICES_BSA_FILES = ("Skyrim - Voices_en0.bsa", "Skyrim - Voices_es0.bsa")
MAX_CANDIDATES_REPORTED = 25

EARLY_QUEST_PREFIXES = ("MQ101", "MQ102", "MQ103", "MS01", "MS02", "DA01", "Favor")


def bsa_fuz_names(bsa_path: Path, read_mb: int = 8) -> set[str]:
    """
    Extract every stored ``*.fuz`` basename from a TES5 v105 BSA.

    The file-name block lives right after the header + folder records and
    stores each record's basename as a lowercase NUL-terminated string
    (e.g. ``bardscolle_bardscollegedru_000d93dc_1.fuz``). We read a bounded
    region and regex-extract the trailing basename.
    """
    with bsa_path.open("rb") as handle:
        header = handle.read(36)
        if len(header) < 36:
            return set()
        _magic, _version, hoff = struct.unpack_from("<4sIi", header, 0)
        (_af, folder_count, _fc, _fnl, _fnl2, _ff) = struct.unpack_from("<IIIIII", header, 12)
        start = hoff + folder_count * 16
        handle.seek(start)
        region = handle.read(read_mb * 1024 * 1024)

    names: set[str] = set()
    for raw in re.finditer(rb"([^\x00]+\.fuz)\x00", region):
        names.add(raw.group(1).decode("ascii", errors="replace").lower())
    return names


def _decode_edid(payload: bytes) -> str | None:
    raw = payload.rstrip(b"\x00")
    return raw.decode("ascii", errors="replace") if raw else None
def index_plugin(data: bytes) -> dict[str, Any]:
    """
    Two-pass identity index of a plugin.

    Returns dicts keyed by 32-bit FormID value: ``vtyp_edid``, ``npc_edid``,
    ``npc_vtck``, ``npc_tplt``, ``qust_edid``, ``dial_edid``, ``dial_qnam``
    plus an ``infos`` mapping with per-INFO speaker/condition/response data.
    """
    vtyp_edid: dict[int, str] = {}
    npc_edid: dict[int, str] = {}
    npc_vtck: dict[int, int] = {}
    npc_tplt: dict[int, int] = {}
    qust_edid: dict[int, str] = {}
    dial_edid: dict[int, str] = {}
    dial_qnam: dict[int, int] = {}

    for tag, _flags, fid_val, _fid_hex, body, _parent_dial in _iter_records(data):
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
    infos: dict[int, dict[str, Any]] = {}
    for tag, _flags, fid_val, fid_hex, body, parent_dial in _iter_records(data):
        if tag != b"INFO" or parent_dial is None:
            continue
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
        "vtyp_edid": vtyp_edid,
        "npc_edid": npc_edid,
        "npc_vtck": npc_vtck,
        "npc_tplt": npc_tplt,
        "qust_edid": qust_edid,
        "dial_edid": dial_edid,
        "dial_qnam": dial_qnam,
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


def find_candidates(data: bytes) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter indexed INFOs down to single-response / zero-condition controls."""
    index = index_plugin(data)

    stats = {
        "infos_total": len(index["infos"]),
        "with_explicit_anam": 0,
        "voice_resolved": 0,
        "single_response": 0,
        "zero_ctda": 0,
        "quest_resolved": 0,
        "quest_topic_resolved": 0,
    }

    candidates: list[dict[str, Any]] = []
    for info_form_id, info in index["infos"].items():
        if info["anam"] is None:
            continue
        stats["with_explicit_anam"] += 1

        voice_type = resolve_voice_type(index, info["anam"])
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
        topic_edid = index["dial_edid"].get(dial_form_id) or ""
        quest_form_id = index["dial_qnam"].get(dial_form_id) or info["qsti"]
        quest_edid = index["qust_edid"].get(quest_form_id) if quest_form_id else None
        if not quest_edid:
            continue
        stats["quest_resolved"] += 1
        stats["quest_topic_resolved"] += 1

        local_object_id = info_form_id & 0x00FFFFFF
        response = info["trdt_response_numbers"][0]
        basename = build_voice_basename(
            quest_edid=quest_edid,
            topic_edid=topic_edid,
            local_object_id=local_object_id,
            response_number=response,
        )

        candidates.append(
            {
                "info_form_id": info["form_id_hex"],
                "local_object_id": f"0x{local_object_id:06X}",
                "npc_edid": index["npc_edid"].get(info["anam"], ""),
                "voice_type": voice_type,
                "quest_edid": quest_edid,
                "topic_edid": topic_edid,
                "response_number": response,
                "basename": basename,
                "bsa_scan_path": f"sound\\voice\\skyrim.esm\\{voice_type}\\{basename}.fuz",
            }
        )

    candidates.sort(
        key=lambda c: (
            0 if c["quest_edid"].startswith(EARLY_QUEST_PREFIXES) else 1,
            c["voice_type"],
            c["quest_edid"],
            c["topic_edid"],
        )
    )
    return candidates, stats


def match_against_bsas(
    candidates: list[dict[str, Any]], data_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep candidates whose vanilla FUZ basename exists inside a voices BSA."""
    bsa_paths = {name: data_dir / name for name in VOICES_BSA_FILES}
    bsa_sizes = {name: p.stat().st_size for name, p in bsa_paths.items()}
    bsa_names = {name: bsa_fuz_names(p) for name, p in bsa_paths.items()}
    for name, names in bsa_names.items():
        logger.info("%s: %d .fuz basenames indexed", name, len(names))

    matched: list[dict[str, Any]] = []
    for candidate in candidates:
        needle = f"{candidate['basename']}.fuz".lower()
        sources = [name for name, names in bsa_names.items() if needle in names]
        if sources:
            annotated = dict(candidate)
            annotated["vanilla_bsa"] = ", ".join(sources)
            matched.append(annotated)
    return matched, bsa_sizes
def main() -> int:
    """CLI entry point: write ranked candidate evidence next to the spike docs."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    game_root = discover_game_root()
    skyrim_esm = game_root / "Data" / "Skyrim.esm"
    logger.info("Parsing %s (read-only)", skyrim_esm)
    data = skyrim_esm.read_bytes()

    candidates, stats = find_candidates(data)
    logger.info("Filter funnel: %s", stats)
    logger.info("%d structural candidates before BSA lookup", len(candidates))

    proven, bsa_sizes = match_against_bsas(candidates, game_root / "Data")
    logger.info("%d candidates have an existing vanilla FUZ asset", len(proven))

    out_dir = REPO_ROOT / "docs" / "evidence" / "pr9"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stats": stats,
        "bsa_sizes": bsa_sizes,
        "candidates_with_vanilla_fuz": proven[:MAX_CANDIDATES_REPORTED],
    }
    (out_dir / "vanilla_control_candidates.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    lines = [
        "# PR #9 - Control vanilla candidato",
        "",
        f"Funnel: `{json.dumps(stats)}`",
        f"BSA sizes: `{json.dumps(bsa_sizes)}`",
        "",
        "| # | NPC (EDID) | VoiceType | Quest | Topic | Basename | BSA |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(proven[:MAX_CANDIDATES_REPORTED], start=1):
        lines.append(
            f"| {i} | `{c['npc_edid']}` | {c['voice_type']} | {c['quest_edid']} "
            f"| `{c['topic_edid']}` | `{c['basename']}` | {c['vanilla_bsa']} |"
        )
    (out_dir / "vanilla_control_candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Evidence written to %s", out_dir / "vanilla_control_candidates.md")
    return 0 if proven else 1


if __name__ == "__main__":
    raise SystemExit(main())