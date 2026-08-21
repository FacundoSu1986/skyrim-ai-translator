# Skyrim Voice Asset Pipeline Spike Report (PR #8 Phase 2)

## 1. Overview & Verification Summary
- **Objective**: Prove the complete deterministic transformation from raw Skyrim plugin `INFO` binary dialogue records to exact Creation Kit voice file basenames, Skyrim relative directory paths, and structurally valid `.fuz` container bytes.
- **Base Commit**: `12e8d10e7eaaef74efbea16b20b4e3c89ce7182c` (PR #7 verified merge)
- **Phase 2 Status**: **`SPIKE_STRUCTURAL_PROOF`**
- **Test Suite**: **190 passed** (all 136 baseline tests + 54 new hermetic tests).

---

## 2. Deterministic Transformation Pipeline

```
Plugin Binary (.esp / .esm)
      ↓
Pass 1 Indexing: QUST(EDID), DIAL(EDID, QNAM), VTYP(EDID), NPC_(ANAM, VTCK, TPLT)
      ↓
Pass 2 Subrecord & Hierarchy Traversal:
   INFO record inside Topic Children GRUP (grp_type == 5, label == DIAL FormID)
   ANAM -> NPC_ -> VTCK/TPLT -> VTYP.EDID -> voice_type
   DIAL FormID -> DIAL.EDID -> topic_edid (or "" if empty)
   DIAL.QNAM / INFO.QSTI -> QUST.EDID -> quest_edid
   TRDT byte 12 -> string_index (raw response number)
      ↓
StringEntry (immutable dataclass):
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

The clean-room Python encoder `pack_fuz` and decoder `unpack_fuz` were validated:
- **Magic**: `b"FUZE"` (`0x46555A45`)
- **Version**: `1` (4-byte unsigned LE)
- **LIP Byte Count**: `uint32` matching exact payload length
- **LIP Stream**: Direct bit-for-bit extraction
- **Audio Stream**: Direct bit-for-bit extraction of the trailing XWM payload
- **Validation**: Rejects zero-length inputs, truncated headers, corrupted versions, and trailing payload mismatches.

---

## 5. External Tools Probe Results

A read-only search for audio toolchain dependencies across system PATH and workspace returned:
- `ffmpeg`: **NOT FOUND**
- `LipGenerator.exe`: **NOT FOUND** (Proprietary Bethesda Creation Kit asset)
- `FonixData.cdf`: **NOT FOUND** (Proprietary Fonix acoustic model)
- `xWMAEncode.exe`: **NOT FOUND** (Proprietary Microsoft DirectX SDK utility)

*Policy Enforcement*: No proprietary binaries were bundled, downloaded, or hardcoded.

---

## 6. Target Gate

**`SPIKE_STRUCTURAL_PROOF`**
