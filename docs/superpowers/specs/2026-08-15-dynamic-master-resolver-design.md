# Design Specification: Dynamic Master Resolver for Skyrim ESP Parser

**Date:** 2026-08-15
**Author:** Staff Software Engineer (Bethesda Binary Parsers & Skyrim SE/AE)
**Target:** Dynamic Master Resolver Feature
**Status:** Approved for Implementation

---

## 1. Context & Motivation

In Skyrim SE/AE localization, dialogue lines (`INFO` records) identify the speaker via the `ANAM` subrecord (a 4-byte FormID). To assign the correct neural voice for text-to-speech synthesis (TTS), the system must traverse the record relationship chain:

$$\text{INFO (ANAM)} \xrightarrow{\text{FormID}} \text{NPC\_ (VTCK)} \xrightarrow{\text{FormID}} \text{VTYP (EDID)} \to \text{VoiceType String}$$

Previously, `esp_parser.py` relied on a static hardcoded table `VANILLA_VOICE_TYPES` and defaulted unresolved dialogue lines to `"MaleNord"`. This approach:
1. Failed for any NPC or VoiceType defined in external masters (e.g., `Skyrim.esm`, `Update.esm`, `Dawnguard.esm`, `Dragonborn.esm`, or third-party masters).
2. Fabricated false VoiceType data (`"MaleNord"`) when references were missing, polluting metadata and TTS assignments.
3. Completely ignored `TES4` master declarations (`MAST` subrecords) and Bethesda FormID master-index semantics.

---

## 2. Core Architecture

### 2.1 Canonical Record Identity (`RecordKey`)

Bethesda plugin FormIDs are 32-bit integers whose high byte (`bits 24..31`) represents the 0-based index into the plugin's `TES4.MAST` list. Comparing raw 32-bit FormIDs across plugins is invalid because the master index is relative to each file.

We introduce a lightweight, immutable record identifier:

```python
@dataclass(frozen=True, slots=True)
class RecordKey:
    plugin: str    # Normalized lowercase plugin filename, e.g. "skyrim.esm"
    object_id: int # 24-bit integer local object ID (form_id & 0x00FFFFFF)
```

### 2.2 Master Index Resolution Rules

For any raw 32-bit `form_id` in a file with `masters: list[str]` and filename `current_plugin`:
- `mod_index = (form_id >> 24) & 0xFF`
- `object_id = form_id & 0x00FFFFFF`

**Rules:**
1. **Masters (`0 <= mod_index < len(masters)`):**
   $$\text{Owner} = \text{masters}[\text{mod\_index}], \quad \text{Key} = \text{RecordKey}(\text{normalize}(\text{owner}), \text{object\_id})$$
2. **Current Plugin (`mod_index == len(masters)`):**
   $$\text{Owner} = \text{current\_plugin}, \quad \text{Key} = \text{RecordKey}(\text{normalize}(\text{current\_plugin}), \text{object\_id})$$
3. **ESL / Light Plugins (`mod_index == 0xFE`):**
   Explicitly detected and unsupported for master resolution in this version.
   Emits `logger.warning("ESL/light plugin FormID 0x%08X master resolution: not supported yet", form_id)`.
   Returns `None` (unresolved).
4. **Invalid / Out-of-Bounds (`mod_index > len(masters)` and `mod_index != 0xFE`):**
   Emits `logger.warning("FormID 0x%08X has invalid master index %d (masters count: %d)", form_id, mod_index, len(masters))`.
   Returns `None` (unresolved). **Never** falls back to local plugin.

---

## 3. Component Design

### 3.1 `MasterIndexData` (Read-Only Index)

Indexed per master file, storing only metadata required for VoiceType and Actor name resolution:

```python
@dataclass
class MasterIndexData:
    masters: list[str]                         # Declared MAST list in this master's TES4
    npc_to_vtck: dict[RecordKey, int]          # RecordKey(NPC) -> raw uint32 VTCK FormID
    npc_to_name: dict[RecordKey, str]          # RecordKey(NPC) -> FULL or EDID string
    vtyp_to_edid: dict[RecordKey, str]         # RecordKey(VTYP) -> EDID string (e.g. "FemaleCommander")
```

### 3.2 `MasterResolver` & Read-Only Cache

```python
class MasterResolver:
    def __init__(self, search_paths: Sequence[Path] | None = None):
        self.search_paths: list[Path] = [p for p in (search_paths or []) if p.is_dir()]
        self._cache: dict[Path, MasterIndexData] = {}

    def get_or_load_master(self, master_name: str, origin_dir: Path) -> MasterIndexData | None:
        ...
```

- **File Discovery:** Searches `[origin_dir] + self.search_paths` case-insensitively.
- **Read-Only Guarantee:** Files are opened strictly with `"rb"`. No master bytes are written or modified.
- **Cache Efficiency:** Master files are parsed at most once per `MasterResolver` instance.

### 3.3 Public API

```python
def parse_esp_file(
    filepath: str | Path,
    master_search_paths: Sequence[Path] | None = None,
) -> List[StringEntry]:
```

- `filepath`: Path to the target `.esp`/`.esm`/`.esl` plugin.
- `master_search_paths`: Optional sequence of directories where master dependencies can be found.
- The parser remains completely decoupled from environment detection (MO2 / Steam / Skyrim registry).

### 3.4 Fallback & Failure Contract

- If an `INFO` record has no speaker, or the speaker's master is missing, or `NPC_` / `VTCK` / `VTYP` cannot be resolved:
  - `entry.voice_type = None`
  - A descriptive `logger.warning` is emitted.
  - No fake voice types (e.g. `"MaleNord"`) are invented.
- The hardcoded table `VANILLA_VOICE_TYPES` is completely removed.

---

## 4. Test Strategy

1. **Test A (Local Chain):** `INFO` $\to$ local `NPC_` $\to$ local `VTCK` $\to$ local `VTYP` $\to$ resolves VoiceType correctly.
2. **Test B (Skyrim.esm Master):** `INFO` in `MyMod.esp` referencing `NPC_` defined *only* in `Skyrim.esm` fixture $\to$ resolves `"FemaleEvenToned"`.
3. **Test C (Third-Party Master):** Multi-master `MyMod.esp` referencing `NPC_` in `OtherMaster.esm` $\to$ resolves correct VoiceType.
4. **Test D (Master Collision Isolation):** `MasterA.esm` and `MasterB.esm` both having local `object_id = 0x001234` with different VoiceTypes $\to$ verifies no collision or cross-contamination.
5. **Test E (Missing Master Safe Fallback):** `MyMod.esp` references missing master $\to$ `voice_type is None`, warnings logged, no exceptions.
6. **Test F (Invalid Master Index):** FormID with out-of-range master index $\to$ returns `None`, never treated as local.
7. **Test G (Master Immutability):** Verifies master file SHA256 hash before and after parsing to ensure 0 byte modifications.
8. **Test H (Master Cache Performance):** Verifies single read/parse when 500 dialogue records reference the same master.
9. **Test I (ESL / Light Detection):** Verifies `0xFE...` FormIDs are detected and safely return `None` with an explicit warning.
