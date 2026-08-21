# Skyrim Voice Asset Pipeline Spike Report (PR #8 Phase 2)

## 1. Overview & Verification Summary
- **Objective**: Prove the deterministic transformation from raw Skyrim plugin `INFO` binary dialogue records to exact Creation Kit voice file basenames, Skyrim relative directory paths, and structurally valid `.fuz` container bytes.
- **Base Commit**: `12e8d10e7eaaef74efbea16b20b4e3c89ce7182c` (PR #7 verified merge)
- **Phase 2 Status**: **`SPIKE_STRUCTURAL_PROOF`**
- **Test Suite**: **240 passed** (all 136 baseline tests + 104 new hermetic tests: 12 in `tests/test_esp_and_voice.py` and 92 in `tests/test_voice_assets.py`).

> [!IMPORTANT]
> **Proven Contract Scope**: The Phase 2 structural proof is strictly conditional on one `VoiceType` already being resolved.
> Current proven contract:
> $$\text{INFO Identity} + \text{Resolved Single VoiceType} \longrightarrow \text{Deterministic Skyrim Voice Asset Path / FUZ Container}$$

---

## 2. Deterministic Transformation Pipeline

```text
Plugin Binary (.esp / .esm)
      ↓
Pass 1 Indexing: QUST(EDID), DIAL(EDID, QNAM), VTYP(EDID), NPC_(VTCK, TPLT)
      ↓
Pass 2 Subrecord & Hierarchy Traversal:
   INFO record inside Topic Children GRUP (grp_type == 7, label == DIAL FormID)
   INFO.ANAM
       ↓
   NPC_
       ↓
   VTCK / TPLT
       ↓
   VTYP.EDID -> voice_type
   DIAL FormID -> DIAL.EDID -> topic_edid (or "" if empty)
   DIAL.QNAM / INFO.QSTI -> QUST.EDID -> quest_edid
   TRDT byte 12 -> string_index (raw response number)
      ↓
StringEntry (dataclass):
   form_id, text, is_dialog=True, actor, voice_type, defining_plugin,
   local_object_id, record_type='INFO', subrecord_type='NAM1',
   string_index, editor_id, quest_edid, topic_edid
      ↓
Pure Identity Resolution (`src/voice_assets.py`):
   `build_voice_basename(...)` -> <Quest_truncated>_<Topic_truncated>_<fid8>_<response>
   `build_voice_relative_path(...)` -> Sound/Voice/<defining_plugin>/<voice_type>/<basename>.fuz
      ↓
Binary FUZ Packer (`pack_fuz`):
   Header (b"FUZE", uint32 version=1, uint32 lip_size) + lip_bytes + xwm_bytes
```

---

## 3. Golden Basename & Path Examples

### Case 1: Standard Dialogue Line (`TG00`)
- **Inputs**:
  - `defining_plugin`: `Skyrim.esm`
  - `voice_type`: `MaleNord`
  - `quest_edid`: `TG00`
  - `topic_edid`: `TG00Brynjolf`
  - `local_object_id`: `0x0136C9`
  - `string_index`: `1`
- **Basename**: `TG00_TG00Brynjolf_000136C9_1`
- **Relative Path**: `Sound/Voice/Skyrim.esm/MaleNord/TG00_TG00Brynjolf_000136C9_1.fuz`

### Case 2: Long Name Truncation ($> 25$ chars, Quest $> 10$)
- **Inputs**:
  - `defining_plugin`: `Skyrim.esm`
  - `voice_type`: `FemaleNord`
  - `quest_edid`: `DialogueWhiterun` (16 chars)
  - `topic_edid`: `DialogueWhiterunCarlottaIntro` (29 chars)
  - `local_object_id`: `0x06497C`
  - `string_index`: `1`
- **Basename**: `DialogueWh_DialogueWhiteru_0006497C_1`
- **Relative Path**: `Sound/Voice/Skyrim.esm/FemaleNord/DialogueWh_DialogueWhiteru_0006497C_1.fuz`

### Case 3: Empty Topic (`topic_edid == ""`)
- **Inputs**:
  - `defining_plugin`: `Skyrim.esm`
  - `voice_type`: `FemaleNord`
  - `quest_edid`: `DialogueWhiterunTemple`
  - `topic_edid`: `""`
  - `local_object_id`: `0x0D88D0`
  - `string_index`: `1`
- **Basename**: `DialogueWhiterunTemple__000D88D0_1`
- **Relative Path**: `Sound/Voice/Skyrim.esm/FemaleNord/DialogueWhiterunTemple__000D88D0_1.fuz`

### Case 4: Multi-Response Non-Collision
- **Response 1**: `Sound/Voice/MultiResponse.esp/MaleNord/QuestA_TopicA_00ABCDEF_1.fuz`
- **Response 2**: `Sound/Voice/MultiResponse.esp/MaleNord/QuestA_TopicA_00ABCDEF_2.fuz`
- **Collision Guard**: `path1 != path2` verified.

---

## 4. FUZ Binary Container Verification

The clean-room Python encoder `pack_fuz` and decoder `unpack_fuz` provide structural encapsulation:
- **Magic Header**: Validates 4-byte ASCII `b"FUZE"` (`0x46555A45`).
- **Version**: Validates 4-byte unsigned LE container version `1`.
- **LIP Header**: Validates declared LIP byte count against payload length.
- **Payload Splitting**: Bit-for-bit extraction of LIP stream and separates trailing bytes as raw audio payload.
- **Scope Boundary**: Does **NOT** parse or validate inner XWM codec/container bitstream semantics.
- **Fail-Fast Error Handling**: Rejects zero-length inputs, truncated buffers, and invalid header magic/version.

---

## 5. Main Pipeline Mismatch & Future Integration

- **Current State in `api.py` / `tts_generator.py`**:
  The existing staging pipeline constructs a single job-level directory root based on `target_plugin_filename` and emits flat staging paths (`<output_dir>/<VoiceType>/<form_id>_<index>.mp3`).
- **Phase 2 Invariant**: `api.py`, `tts_generator.py`, and WebSocket contracts were intentionally **not** modified during this structural spike.
- **Integration Requirement**: Production integration must dynamically derive the relative voice root per `StringEntry` using `entry.defining_plugin` rather than a single job-level target plugin name.

---

## 6. Voice Resolution Follow-Up

The parser currently resolves `voice_type` strictly when an explicit `INFO.ANAM` speaker subrecord references an `NPC_` with a resolvable `VTCK` or `TPLT`. Future work must address:
1. **Generic INFO Without ANAM**: Dialogue spoken by multiple NPCs without explicit speaker subrecords.
2. **Condition-Derived VoiceTypes**: Evaluation of `CTDA` condition functions (such as `GetIsID` or `GetIsVoiceType`).
3. **Quest & Scene Aliases**: Resolution of dynamic actor aliases defined in `QUST` or `SCEN` records.
4. **One-to-Many VoiceType Fan-Out**: A single generic `INFO` dialogue line mapping to multiple VoiceTypes and distinct voice directory assets.

---

## 7. External Tools Probe Results & Explicit Limitations

### External Tools Probe
A read-only search for audio toolchain dependencies across system PATH and workspace returned:
- `ffmpeg`: **NOT FOUND**
- `LipGenerator.exe`: **NOT FOUND** (Bethesda Creation Kit proprietary asset)
- `FonixData.cdf`: **NOT FOUND** (Fonix acoustic model proprietary data)
- `xWMAEncode.exe`: **NOT FOUND** (Microsoft DirectX SDK proprietary utility)

### Explicit Limitations
- **No In-Game Runtime Execution**: Pipeline verified structurally through parser and container specifications; not loaded in a live Skyrim game engine session.
- **No Real Audio Encoding**: Transcoding (WAV $\rightarrow$ LIP $\rightarrow$ XWM) requires user-supplied external tools and was not executed.
- **Generic / Multi-VoiceType Resolution Incomplete**: Handled in future follow-up per Section 6.
- **Localized `.STRINGS` Support**: Binary `.STRINGS`/`.DLSTRINGS`/`.ILSTRINGS` decompression remains outside this spike.
- **ESL / FormID Space**: Light plugins (0xFE high-byte) are currently unsupported.
- **WebSocket / API Integration Deferred**: `api.py` remains on PR #7 contract.

---

## 8. Target Gate

**`SPIKE_STRUCTURAL_PROOF`**
