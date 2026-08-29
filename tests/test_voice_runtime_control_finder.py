"""Hermetic tests for the deterministic vanilla voice runtime control finder.

All fixtures are synthetic: plugin bytes are hand-built TES5 records and the
BSA bytes are hand-built TES5 v105 archives following the layout contract
validated against the real vanilla voice archives. The real Skyrim.esm and
the real BSAs are never touched here.
"""

import struct
from pathlib import Path
from typing import Any

import pytest

from scripts.voice_runtime_control_finder import (
    BsaVoiceIndex,
    BsaVoiceLoadError,
    _bsa_meta_for,
    _classify_runtime,
    _match_candidate,
    _render_markdown,
    _tes5_name_hash_low32,
    collect_candidates,
    match_and_classify,
)

# ---------------------------------------------------------------------------
# Synthetic TES5 plugin builder
# ---------------------------------------------------------------------------


def _sub(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<H", len(payload)) + payload


def _edid(edid: str) -> bytes:
    return _sub(b"EDID", edid.encode("ascii") + b"\x00")


def _form(form_id: int) -> bytes:
    return struct.pack("<I", form_id)


def _record(tag: bytes, form_id: int, body: bytes) -> bytes:
    return tag + struct.pack("<I", len(body)) + struct.pack("<I", 0) + struct.pack("<I", form_id) + b"\x00" * 8 + body


def _grup(label: int, grp_type: int, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<III", 24 + len(body), label, grp_type) + b"\x00" * 8 + body


def _vtyp(form_id: int, edid: str) -> bytes:
    return _record(b"VTYP", form_id, _edid(edid))


def _npc(form_id: int, edid: str, voice_type_form: int, template_form: int | None = None) -> bytes:
    """Build an NPC_ record; ``template_form`` optionally adds a TPLT chain link."""
    body = _edid(edid) + _sub(b"VTCK", _form(voice_type_form))
    if template_form is not None:
        body += _sub(b"TPLT", _form(template_form))
    return _record(b"NPC_", form_id, body)


def _qust(form_id: int, edid: str) -> bytes:
    return _record(b"QUST", form_id, _edid(edid))


def _dial(form_id: int, edid: str, quest_form: int, topic_type: int = 0) -> bytes:
    body = _edid(edid) + _sub(b"QNAM", _form(quest_form)) + _sub(b"DNAM", bytes([topic_type]))
    return _record(b"DIAL", form_id, body)


def _tact(form_id: int, edid: str) -> bytes:
    return _record(b"TACT", form_id, _edid(edid))


def _info(
    form_id: int,
    speaker_form: int,
    quest_form: int,
    response: int = 1,
    ctda_count: int = 0,
    trdt_count: int = 1,
) -> bytes:
    """Build an INFO record; ``trdt_count``>1 simulates multi-response records."""
    body = _sub(b"ANAM", _form(speaker_form)) + _sub(b"QSTI", _form(quest_form))
    body += _sub(b"CTDA", b"\x00" * 32) * ctda_count
    body += _sub(b"TRDT", b"\x00" * 12 + bytes([response])) * trdt_count
    body += _sub(b"NAM1", _form(1))
    return _record(b"INFO", form_id, body)


VTYP_FID = 0x00000101
NPC_FID = 0x00000201
QUEST_FID = 0x00000301
DIAL_FID = 0x00000401
DIAL_EDID = "MQ101TestTopic"
QUEST_EDID = "MQ101"
INFO_FID = 0x00000402

TALKING_ACTIVATOR_FID = 0x00000501


def _valid_plugin(info_form: int = INFO_FID, speaker_form: int = NPC_FID) -> bytes:
    """Fully valid single-child plugin whose only INFO is a structurally clean candidate."""
    return b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(DIAL_FID, 7, _info(info_form, speaker_form, QUEST_FID)),
        ]
    )


# ---------------------------------------------------------------------------
# Synthetic TES5 v105 BSA builder (voices archive layout contract)
# ---------------------------------------------------------------------------


def build_bsa(folders: list[tuple[str, list[str]]]) -> bytes:
    """Build a minimal but contract-valid TES5 v105 voices BSA."""
    folder_count = len(folders)
    file_count = sum(len(files) for _, files in folders)
    folder_records = bytearray()
    interleaved = bytearray()
    file_name_block = bytearray()
    for folder, files in folders:
        raw_name = folder.encode("ascii").lower() + b"\x00"
        folder_records += struct.pack("<QIIQ", 0, len(files), 0, 0)
        interleaved += bytes([len(raw_name)]) + raw_name
        for filename in files:
            stem = filename.encode("ascii").lower()[:-4]
            interleaved += struct.pack("<QII", _tes5_name_hash_low32(stem), 16, 0)
            file_name_block += filename.encode("ascii").lower() + b"\x00"
    header = struct.pack(
        "<4sIiIIIIII",
        b"BSA\x00",
        105,
        36,
        0x0003,
        folder_count,
        file_count,
        sum(len(f.encode("ascii").lower()) + 1 for f, _ in folders),
        len(file_name_block),
        0x18,
    )
    return header + bytes(folder_records) + bytes(interleaved) + bytes(file_name_block)


def _write_bsa(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "Skyrim - Voices_en0.bsa"
    path.write_bytes(data)
    return path


def _voice_folder(voice_type: str) -> str:
    return f"sound\\voice\\skyrim.esm\\{voice_type.lower()}"


# ---------------------------------------------------------------------------
# T1/T2: DIAL cardinality gates
# ---------------------------------------------------------------------------


def test_t1_dial_with_two_info_children_rejected(tmp_path: Path) -> None:
    """T1: a DIAL with 2 INFO children is rejected even if one child is clean."""
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(
                DIAL_FID,
                7,
                _info(INFO_FID, NPC_FID, QUEST_FID) + _info(0x00000403, NPC_FID, QUEST_FID),
            ),
        ]
    )

    candidates, stats = collect_candidates(plugin)

    assert stats["infos_total"] == 2
    assert stats["single_child_dial"] == 0
    assert candidates == []


def test_t2_dial_with_exactly_one_info_child_survives(tmp_path: Path) -> None:
    """T2: a DIAL with exactly one INFO child survives the cardinality gate."""
    candidates, stats = collect_candidates(_valid_plugin())

    assert stats["infos_total"] == 1
    assert stats["single_child_dial"] == 1
    assert len(candidates) == 1
    assert candidates[0]["child_info_count"] == 1
    assert candidates[0]["info_form_id"] == INFO_FID


# ---------------------------------------------------------------------------
# Response-number semantics: single TRDT, response number is a raw value
# ---------------------------------------------------------------------------


def test_single_trdt_with_response_number_two_is_valid() -> None:
    """A single TRDT whose response-number byte is 2 passes single_response."""
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(DIAL_FID, 7, _info(INFO_FID, NPC_FID, QUEST_FID, response=2)),
        ]
    )

    candidates, stats = collect_candidates(plugin)

    assert stats["single_response"] == 1
    assert stats["single_child_dial"] == 1
    assert len(candidates) == 1
    assert candidates[0]["response_number"] == 2
    assert candidates[0]["basename"].endswith("_2")


# ---------------------------------------------------------------------------
# T3/T4: exact full-path FUZ matching
# ---------------------------------------------------------------------------


def _single_candidate() -> list[dict[str, Any]]:
    candidates, _ = collect_candidates(_valid_plugin())
    assert len(candidates) == 1
    return candidates


def test_t3_basename_under_wrong_voicetype_folder_is_no_match(tmp_path: Path) -> None:
    """T3: basename present under a wrong VoiceType folder is NOT an exact match."""
    candidate = _single_candidate()[0]
    wrong_folder = _voice_folder("FemaleNord")
    data = build_bsa([(wrong_folder, [candidate["basename"].lower() + ".fuz"])])

    index = BsaVoiceIndex(_write_bsa(tmp_path, data))

    assert _match_candidate(candidate, [index]) is None


def test_t4_correct_full_path_is_exact_match(tmp_path: Path) -> None:
    """T4: the full correct path is an exact match with every-archive attribution."""
    candidate = _single_candidate()[0]
    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])

    index = BsaVoiceIndex(_write_bsa(tmp_path, data))

    match = _match_candidate(candidate, [index])
    assert match is not None
    matched_path, matching_bsas = match
    assert matched_path == candidate["expected_full_fuz_path"].lower()
    assert matched_path.endswith(f"\\{candidate['basename'].lower()}.fuz")
    assert matching_bsas == ["Skyrim - Voices_en0.bsa"]


# ---------------------------------------------------------------------------
# TPLT template-chain resolution (NPC_ VTCK local id 0 ignored, cycle safe)
# ---------------------------------------------------------------------------


def _chained_plugin(template_npc: int, chained_npc: int) -> bytes:
    return b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(template_npc, "TemplateNord", VTYP_FID),
            _npc(chained_npc, "ChainedNord", 0, template_form=template_npc),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(DIAL_FID, 7, _info(INFO_FID, chained_npc, QUEST_FID)),
        ]
    )


def test_t14_vtck_local_zero_falls_through_to_tplt_chain() -> None:
    """T14: VTCK with local object id 0 is ignored and the TPLT chain resolves VTYP."""
    template_npc, chained_npc = 0x00000210, 0x00000211

    candidates, stats = collect_candidates(_chained_plugin(template_npc, chained_npc))

    assert stats["voice_resolved"] == 1
    assert len(candidates) == 1
    assert candidates[0]["voice_type"] == "MaleNord"


def test_t15_tplt_cycle_terminates_without_voicetype() -> None:
    """T15: a TPLT cycle ends via the seen-set instead of looping forever."""
    npc_a, npc_b = 0x00000220, 0x00000221
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(npc_a, "CycleA", 0, template_form=npc_b),
            _npc(npc_b, "CycleB", 0, template_form=npc_a),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(DIAL_FID, 7, _info(INFO_FID, npc_a, QUEST_FID)),
        ]
    )

    candidates, stats = collect_candidates(plugin)

    assert stats["voice_resolved"] == 0
    assert candidates == []


# ---------------------------------------------------------------------------
# T5: corrupt / truncated BSA fail-fast
# ---------------------------------------------------------------------------


def _flip_record_hash(data: bytearray) -> bytes:
    """Corrupt the first file-record name hash inside the interleaved region."""
    folder_name = _voice_folder(_single_candidate()[0]["voice_type"]).encode("ascii") + b"\x00"
    offset = 36 + 24 + 1 + len(folder_name)
    data[offset] = (data[offset] + 1) % 0x100
    return bytes(data)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda data: data[:20], id="truncated-header"),
        pytest.param(lambda data: b"XSA\x00" + data[4:], id="bad-magic"),
        pytest.param(lambda data: data[:4] + struct.pack("<I", 104) + data[8:], id="bad-version"),
        pytest.param(
            lambda data: data[:8] + struct.pack("<i", 999) + data[12:],
            id="unsupported-folder-records-offset",
        ),
        pytest.param(
            lambda data: data[:16] + struct.pack("<I", 0x7FFFFFFF) + data[20:],
            id="oversized-header-folder-count",
        ),
        pytest.param(
            lambda data: data[:28] + struct.pack("<I", 0x7FFFFFF0) + data[32:],
            id="oversized-total-file-name-length",
        ),
        pytest.param(
            lambda data: data[:12] + struct.pack("<I", 0x0) + data[16:],
            id="folder-file-names-flags-cleared",
        ),
        pytest.param(lambda data: data[:-1], id="truncated-file-name-table"),
        pytest.param(lambda data: data[: 36 + 24 + 6], id="truncated-interleaved-region"),
        pytest.param(
            lambda data: data[:44] + struct.pack("<I", 2) + data[48:],
            id="folder-count-overflow",
        ),
        pytest.param(_flip_record_hash, id="name-hash-mismatch"),
    ],
)
def test_t5_corrupt_or_truncated_bsa_fails_fast(tmp_path: Path, mutate: Any) -> None:
    """T5: every unsupported or corrupt structure raises BsaVoiceLoadError."""
    candidate = _single_candidate()[0]
    folder = _voice_folder(candidate["voice_type"])
    data = bytearray(build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])]))

    path = _write_bsa(tmp_path, mutate(data))

    with pytest.raises(BsaVoiceLoadError):
        BsaVoiceIndex(path)


# ---------------------------------------------------------------------------
# T6: non-NPC speakers are never LOW
# ---------------------------------------------------------------------------


def test_t6_talking_activator_speaker_rejected_and_never_low() -> None:
    """T6: a Talking Activator speaker is rejected from the funnel and never LOW."""
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _tact(TALKING_ACTIVATOR_FID, "MagicActivator"),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, DIAL_EDID, QUEST_FID),
            _grup(DIAL_FID, 7, _info(INFO_FID, TALKING_ACTIVATOR_FID, QUEST_FID)),
        ]
    )

    candidates, stats = collect_candidates(plugin)

    assert stats["explicit_anam"] == 1
    assert stats["npc_speaker"] == 0
    assert stats["voice_resolved"] == 0
    assert candidates == []

    escalated = {
        "speaker_record_type": "TACT",
        "voice_type": "MaleNord",
        "dial_topic_type": 0,
        "quest_edid": "MQ101",
        "topic_edid": DIAL_EDID,
    }
    risk, reasons = _classify_runtime(escalated)
    assert risk != "LOW"
    assert any("TACT" in reason for reason in reasons)


# ---------------------------------------------------------------------------
# T7: LOW candidate runtime contract completeness
# ---------------------------------------------------------------------------


def test_t7_low_candidate_carries_all_runtime_ids(tmp_path: Path) -> None:
    """T7: a matched-and-classified LOW candidate contains every runtime-mandatory identity field."""
    candidates = _single_candidate()
    folder = _voice_folder(candidates[0]["voice_type"])
    data = build_bsa([(folder, [candidates[0]["basename"].lower() + ".fuz"])])

    index = BsaVoiceIndex(_write_bsa(tmp_path, data))
    matched = match_and_classify(candidates, [index])
    assert len(matched) == 1
    candidate = matched[0]

    assert candidate["runtime_risk"] == "LOW"
    assert candidate["runtime_risk_reasons"]

    mandatory_fields = (
        "dial_form_id",
        "info_form_id",
        "anam_form_id",
        "npc_edid",
        "speaker_record_type",
        "voice_type",
        "quest_form_id",
        "quest_edid",
        "topic_edid",
        "child_info_count",
        "response_number",
        "ctda_count",
        "basename",
        "expected_full_fuz_path",
        "matched_full_fuz_path",
        "matching_bsas",
        "runtime_risk",
        "runtime_risk_reasons",
    )
    for field in mandatory_fields:
        assert field in candidate, f"missing runtime contract field: {field}"
    for field in (
        "npc_edid",
        "voice_type",
        "quest_edid",
        "basename",
        "expected_full_fuz_path",
        "matched_full_fuz_path",
    ):
        assert candidate[field], f"empty runtime contract field: {field}"
    # topic_edid MUST exist as a field and be a string, but MAY be "": vanilla
    # single-child DIALs commonly carry no EditorID (e.g. the Nelacar DA01
    # control has topic_edid == "").
    assert "topic_edid" in candidate
    assert isinstance(candidate["topic_edid"], str)
    assert candidate["matching_bsas"] == ["Skyrim - Voices_en0.bsa"]
    assert candidate["matched_full_fuz_path"] == candidate["expected_full_fuz_path"].lower()
    assert candidate["speaker_record_type"] == "NPC_"
    assert candidate["ctda_count"] == 0
    assert candidate["child_info_count"] == 1


# ---------------------------------------------------------------------------
# T8: structural LOW-lookalike without exact FUZ can never be LOW
# ---------------------------------------------------------------------------


def test_t8_structural_low_lookalike_without_exact_fuz_never_low(tmp_path: Path) -> None:
    """T8: a perfect structural candidate without an exact FUZ match cannot become LOW."""
    candidates, _ = collect_candidates(_valid_plugin())
    assert len(candidates) == 1
    candidate = candidates[0]

    # Structural stage: no exact-match metadata and no risk classification.
    assert candidate["matched_full_fuz_path"] == ""
    assert candidate["matching_bsas"] == []
    assert candidate["runtime_risk"] is None

    # An archive holding the basename under a wrong VoiceType folder is no match.
    data = build_bsa([(_voice_folder("FemaleNord"), [candidate["basename"].lower() + ".fuz"])])
    index = BsaVoiceIndex(_write_bsa(tmp_path, data))
    assert _match_candidate(candidate, [index]) is None
    assert match_and_classify(candidates, [index]) == []
    assert candidate["runtime_risk"] is None

    # The classifier itself refuses LOW without exact-match metadata.
    risk, reasons = _classify_runtime(candidate)
    assert risk != "LOW"
    assert any("FUZ" in reason for reason in reasons)


# ---------------------------------------------------------------------------
# T9: risk classification only after exact-match metadata
# ---------------------------------------------------------------------------


def test_t9_risk_classification_only_after_exact_match_metadata(tmp_path: Path) -> None:
    """T9: runtime risk is assigned only after exact-match metadata is populated."""
    candidate = _single_candidate()[0]

    # Structural stage leaves the candidate unclassified.
    assert candidate["runtime_risk"] is None
    assert candidate["matched_full_fuz_path"] == ""

    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])
    index = BsaVoiceIndex(_write_bsa(tmp_path, data))

    matched = match_and_classify([candidate], [index])
    assert matched == [candidate]
    # Metadata is populated before classification: a LOW verdict implies both.
    assert candidate["matched_full_fuz_path"] == candidate["expected_full_fuz_path"].lower()
    assert candidate["matching_bsas"] == ["Skyrim - Voices_en0.bsa"]
    assert candidate["runtime_risk"] == "LOW"


# ---------------------------------------------------------------------------
# T10: same exact path in en0 and es0 preserves both archives
# ---------------------------------------------------------------------------


def test_t10_exact_path_in_both_archives_preserves_both(tmp_path: Path) -> None:
    """T10: a path present in en0 and es0 is attributed to both archives."""
    candidate = _single_candidate()[0]
    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])

    en0 = tmp_path / "Skyrim - Voices_en0.bsa"
    es0 = tmp_path / "Skyrim - Voices_es0.bsa"
    en0.write_bytes(data)
    es0.write_bytes(data)
    indexes = [BsaVoiceIndex(en0), BsaVoiceIndex(es0)]

    matched = match_and_classify([candidate], indexes)
    assert len(matched) == 1
    assert matched[0]["matching_bsas"] == ["Skyrim - Voices_en0.bsa", "Skyrim - Voices_es0.bsa"]


# ---------------------------------------------------------------------------
# T11: rendered procedure selects/verifies the spawned reference before `say`
# ---------------------------------------------------------------------------


def test_t11_rendered_procedure_selects_spawned_reference_before_say(tmp_path: Path) -> None:
    """T11: the manual procedure requires spawned-reference selection before `say`."""
    candidate = _single_candidate()[0]
    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])
    path = _write_bsa(tmp_path, data)
    index = BsaVoiceIndex(path)
    matched = match_and_classify([candidate], [index])

    stats = {"infos_total": 1, "exact_fuz_match": 1, "reported_count": 1}
    markdown = _render_markdown(stats, {"Skyrim - Voices_en0.bsa": _bsa_meta_for(path, index)}, matched)

    anam = matched[0]["anam_form_hex"][2:]
    dial = matched[0]["dial_form_hex"][2:]
    placeatme_line = f"player.placeatme {anam} 1"
    select_line = f"# In the console, select/click the newly spawned {matched[0]['npc_edid']}."
    verify_line = f"# Verify its BaseID is {anam}."
    only_selected_line = "# Only with that NPC reference selected:"
    say_line = f"say {dial}"

    assert placeatme_line in markdown
    assert select_line in markdown
    assert verify_line in markdown
    assert only_selected_line in markdown
    assert say_line in markdown
    assert (
        0
        < markdown.index(placeatme_line)
        < markdown.index(select_line)
        < markdown.index(verify_line)
        < markdown.index(only_selected_line)
        < markdown.index(say_line)
    )
    # The runtime reference FormID is created at runtime and never fabricated.
    assert "prid" not in markdown.lower()
    assert "runtime reference" in markdown
    assert "created at runtime" in markdown
    # No overclaim: LOW is a heuristic, nothing is runtime-proven yet.
    assert "not a runtime-proven control" in markdown
    assert "quest-prefix heuristic" in markdown


# ---------------------------------------------------------------------------
# Deterministic ordering: info_form_id tie-breaker
# ---------------------------------------------------------------------------


def test_candidates_tied_on_all_rank_keys_order_by_info_form_id() -> None:
    """Candidates tied on rank/voice/quest/topic are ordered by info_form_id."""
    info_452, info_451, info_453 = 0x00000452, 0x00000451, 0x00000453
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _qust(QUEST_FID, QUEST_EDID),
            # Empty topic EDIDs: all three candidates tie on topic too.
            _dial(0x00000441, "", QUEST_FID),
            _dial(0x00000442, "", QUEST_FID),
            _dial(0x00000443, "", QUEST_FID),
            # Deliberately non-ascending info_form_id file order.
            _grup(0x00000441, 7, _info(info_452, NPC_FID, QUEST_FID)),
            _grup(0x00000442, 7, _info(info_451, NPC_FID, QUEST_FID)),
            _grup(0x00000443, 7, _info(info_453, NPC_FID, QUEST_FID)),
        ]
    )

    candidates, _ = collect_candidates(plugin)

    assert [c["info_form_id"] for c in candidates] == [info_451, info_452, info_453]


# ---------------------------------------------------------------------------
# T12: persisted BSA validation counts prove the hash audit
# ---------------------------------------------------------------------------


def test_t12_bsa_validation_counts_prove_hash_audit(tmp_path: Path) -> None:
    """T12: header count == parsed count == hash-validated count, zero mismatches."""
    candidate = _single_candidate()[0]
    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])

    path = _write_bsa(tmp_path, data)
    index = BsaVoiceIndex(path)

    assert index.header_file_count == 1
    assert index.header_file_count == index.parsed_file_names == index.hash_validated
    assert index.hash_mismatches == 0

    meta = _bsa_meta_for(path, index)
    assert meta["header_file_count"] == meta["parsed_file_names"] == meta["hash_validated"]
    assert meta["hash_mismatches"] == 0
    assert meta["indexed_voice_paths"] == 1
    assert meta["size_bytes"] == len(data)

    matched = match_and_classify([candidate], [index])
    assert matched == [candidate]
    stats = {"infos_total": 1, "exact_fuz_match": 1, "reported_count": 1}
    markdown = _render_markdown(stats, {"Skyrim - Voices_en0.bsa": meta}, matched)
    assert "hash_validated" in markdown
    assert "hash_mismatches" in markdown


# ---------------------------------------------------------------------------
# T13: empty topic_edid is contract-valid and must not block LOW
# ---------------------------------------------------------------------------


def test_t13_empty_topic_edid_with_all_gates_and_exact_fuz_may_classify_low(tmp_path: Path) -> None:
    """T13: candidate with empty topic_edid + all structural gates + exact FUZ -> LOW."""
    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _qust(QUEST_FID, QUEST_EDID),
            _dial(DIAL_FID, "", QUEST_FID),
            _grup(DIAL_FID, 7, _info(INFO_FID, NPC_FID, QUEST_FID)),
        ]
    )

    candidates, _ = collect_candidates(plugin)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["topic_edid"] == ""
    assert isinstance(candidate["topic_edid"], str)

    folder = _voice_folder(candidate["voice_type"])
    data = build_bsa([(folder, [candidate["basename"].lower() + ".fuz"])])
    index = BsaVoiceIndex(_write_bsa(tmp_path, data))

    matched = match_and_classify(candidates, [index])

    assert len(matched) == 1
    assert matched[0]["matched_full_fuz_path"] == candidate["expected_full_fuz_path"].lower()
    assert matched[0]["runtime_risk"] == "LOW"


def test_counters_follow_funnel_order() -> None:
    """Counters decrease strictly at every funnel stage via staged failures."""
    voiceless_npc = 0x00000202
    unknown_quest_form = 0x00000399

    def _info_without_anam(form_id: int) -> bytes:
        body = _sub(b"QSTI", _form(QUEST_FID)) + _sub(b"TRDT", b"\x00" * 12 + b"\x01") + _sub(b"NAM1", _form(1))
        return _record(b"INFO", form_id, body)

    plugin = b"".join(
        [
            _vtyp(VTYP_FID, "MaleNord"),
            _npc(NPC_FID, "TestNord", VTYP_FID),
            _npc(voiceless_npc, "VoicelessNord", 0),
            _tact(TALKING_ACTIVATOR_FID, "MagicActivator"),
            _qust(QUEST_FID, QUEST_EDID),
            # Stage 1: no ANAM (two INFOs).
            _dial(0x00000411, "DialNoAnam", QUEST_FID),
            _grup(0x00000411, 7, _info_without_anam(0x00000421)),
            _dial(0x00000412, "DialNoAnam2", QUEST_FID),
            _grup(0x00000412, 7, _info_without_anam(0x00000422)),
            # Stage 2: TACT speaker (two INFOs).
            _dial(0x00000413, "DialTact", QUEST_FID),
            _grup(0x00000413, 7, _info(0x00000423, TALKING_ACTIVATOR_FID, QUEST_FID)),
            _dial(0x00000414, "DialTact2", QUEST_FID),
            _grup(0x00000414, 7, _info(0x00000424, TALKING_ACTIVATOR_FID, QUEST_FID)),
            # Stage 3: VTCK local object id 0, no template (two INFOs).
            _dial(0x00000415, "DialVoiceless", QUEST_FID),
            _grup(0x00000415, 7, _info(0x00000425, voiceless_npc, QUEST_FID)),
            _dial(0x00000416, "DialVoiceless2", QUEST_FID),
            _grup(0x00000416, 7, _info(0x00000426, voiceless_npc, QUEST_FID)),
            # Stage 4: two TRDT responses (two INFOs).
            _dial(0x00000417, "DialDouble", QUEST_FID),
            _grup(
                0x00000417,
                7,
                _info(0x00000427, NPC_FID, QUEST_FID, trdt_count=2)
                + _info(0x00000428, NPC_FID, QUEST_FID, trdt_count=2),
            ),
            # Stage 5: one CTDA condition (two INFOs).
            _dial(0x00000418, "DialCtda", QUEST_FID),
            _grup(
                0x00000418,
                7,
                _info(0x00000429, NPC_FID, QUEST_FID, ctda_count=1)
                + _info(0x0000042A, NPC_FID, QUEST_FID, ctda_count=1),
            ),
            # Stage 6: two clean single-child candidates; one quest unresolvable.
            _dial(0x00000419, "DialClean", QUEST_FID),
            _grup(0x00000419, 7, _info(0x0000042B, NPC_FID, QUEST_FID)),
            _dial(0x0000041A, "DialUnknownQuest", unknown_quest_form),
            _grup(0x0000041A, 7, _info(0x0000042C, NPC_FID, QUEST_FID)),
            # Stage 7: one DIAL with two clean children (cardinality reject).
            _dial(0x0000041B, "DialShared", QUEST_FID),
            _grup(
                0x0000041B,
                7,
                _info(0x0000042D, NPC_FID, QUEST_FID) + _info(0x0000042E, NPC_FID, QUEST_FID),
            ),
        ]
    )

    candidates, stats = collect_candidates(plugin)

    ordered = (
        "infos_total",
        "explicit_anam",
        "npc_speaker",
        "voice_resolved",
        "single_response",
        "zero_ctda",
        "single_child_dial",
        "quest_resolved",
    )
    values = [stats[name] for name in ordered]
    assert values == [14, 12, 10, 8, 6, 4, 2, 1]
    from itertools import pairwise

    assert all(left > right for left, right in pairwise(values))
    assert len(candidates) == 1
    assert candidates[0]["info_form_id"] == 0x0000042B
