# Design Specification: Dynamic Master Resolver for Skyrim ESP Parser

**Date:** 2026-08-15
**Author:** Staff Software Engineer (Bethesda Binary Parsers & Skyrim SE/AE)
**Target:** Dynamic Master Resolver Feature
**Status:** Implemented & Verified (Ready for Final Review)

---

## 1. Context & Motivation

In Skyrim SE/AE localization, dialogue lines (`INFO` records) identify the speaker via the `ANAM` subrecord (a 4-byte FormID). To assign the correct neural voice for text-to-speech synthesis (TTS), the system must traverse the record relationship chain:

$$\text{INFO (ANAM)} \xrightarrow{\text{FormID}} \text{NPC\_ (VTCK / TPLT)} \xrightarrow{\text{FormID}} \text{VTYP (EDID)} \to \text{VoiceType String}$$

Previously, `esp_parser.py` relied on a static hardcoded table `VANILLA_VOICE_TYPES` and defaulted unresolved dialogue lines to `"MaleNord"`. This approach:
1. Failed for any NPC or VoiceType defined in external masters (e.g., `Skyrim.esm`, `Update.esm`, `Dawnguard.esm`, `Dragonborn.esm`, or third-party masters).
2. Fabricated false VoiceType data (`"MaleNord"`) when references were missing, polluting metadata and TTS assignments.
3. Completely ignored `TES4` master declarations (`MAST` subrecords) and Bethesda FormID master-index semantics.
4. Ignored template inheritance (`TPLT`).

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
   Emits `logger.warning("FormID 0x%08X has invalid master index %d (declared masters count: %d)", form_id, mod_index, len(masters))`.
   Returns `None` (unresolved). **Never** falls back to local plugin.

### 2.3 Origin Record Resolution (WinningOverride Deferred)

When resolving a `RecordKey(plugin, object_id)`:
1. **Origin Plugin Resolution (Supported):** The record is resolved directly against its owning origin plugin (`RecordKey.plugin`), or in the local plugin if `plugin == current_plugin`.
2. **Effective Load-Order WinningOverride (Not Supported Yet):** In Creation Engine, true winning override resolution requires knowledge of the active global load order (e.g. `plugins.txt` or Mod Organizer 2 VFS order). The order of `MAST` declarations in a plugin's `TES4` header **does not** equal the runtime load order. Therefore, the parser strictly avoids arbitrary heuristics (such as `reversed(MAST)` or filesystem iteration order) and queries the record from its origin plugin.

### 2.4 Template Actor Inheritance (`TPLT`)

When an `NPC_` record lacks a direct `VTCK` (VoiceType FormID), the resolver inspects `TPLT` (Template NPC FormID):
- Recursively traverses `NPC_ -> TPLT -> NPC_ -> VTCK`.
- Protected by `visited: set[RecordKey]` cycle detection and maximum recursion depth (10 levels).
- If neither `VTCK` nor a valid template chain resolves, returns `voice_type = None` cleanly.
- **Note on Bethesda Template Flags:** The resolver traverses `TPLT` relationships directly without fully parsing `ACBS`/`DNAM` inheritance bitmasks ("Use Traits" `0x00000001`). This is documented as a conservative limitation.

---

## 3. Component Design

### 3.1 `MasterIndexData` (Read-Only Index)

Indexed per master file, storing only metadata required for VoiceType, Template, and Actor resolution:

```python
@dataclass
class MasterIndexData:
    plugin_name: str
    masters: list[str]                         # Declared MAST list in this master's TES4
    npc_to_vtck: dict[RecordKey, int]          # RecordKey(NPC) -> raw uint32 VTCK FormID
    npc_to_tplt: dict[RecordKey, int]          # RecordKey(NPC) -> raw uint32 TPLT FormID
    npc_to_name: dict[RecordKey, str]          # RecordKey(NPC) -> FULL or EDID string
    vtyp_to_edid: dict[RecordKey, str]         # RecordKey(VTYP) -> EDID string (e.g. "FemaleCommander")
```

### 3.2 `MasterResolver` & Read-Only Cache

```python
class MasterResolver:
    def __init__(self, search_paths: Sequence[Path | str] | None = None):
        self.search_paths: list[Path] = [Path(p) for p in (search_paths or []) if Path(p).is_dir()]
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
    master_search_paths: Sequence[Path | str] | None = None,
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

## 4. Supported vs. Not Supported Scope

### Supported
- `TES4.MAST` header parsing and relative index resolution.
- Canonical `RecordKey(plugin, object_id)` across plugins.
- Origin-record resolution across master files.
- Transitive master references (`Mod -> Update.esm -> Skyrim.esm`).
- `TPLT` template actor inheritance traversal.
- Cycle and pathological depth protection (`visited` set + `max_depth = 10`).
- Instrumented in-memory read-only master caching.

### Not Supported (Deferred)
- Effective MO2 / plugin load order.
- WinningOverride across arbitrary load order.
- ESL / Light plugin (`0xFE...`) FormID resolution.
- Complete Bethesda template inheritance flags (`ACBS`/`DNAM` bitmasks).
- Localized plugin strings (`.STRINGS` / `.DLSTRINGS` / `.ILSTRINGS`).
- Automatic runtime master discovery (MO2 VFS / registry scanning).

---

## 5. Test Suite Inventory

1. **Test 1 (Local Chain):** `INFO` $\to$ local `NPC_` $\to$ local `VTCK` $\to$ local `VTYP` $\to$ resolves VoiceType correctly.
2. **Test 2 (Skyrim.esm Master):** `INFO` in `MyMod.esp` referencing `NPC_` defined *only* in `Skyrim.esm` fixture $\to$ resolves `"MaleCommander"`.
3. **Test 3 (Transitive Master):** `MyMod.esp` $\to$ `Update.esm` (NPC) $\to$ `Skyrim.esm` (VTYP) relative index mapping.
4. **Test 4 (Third-Party Master):** Multi-master `MyMod.esp` referencing `NPC_` in `CustomMaster.esm` via `master_search_paths`.
5. **Test 5 (Master Collision Isolation):** `MasterA.esm` and `MasterB.esm` both having local `object_id = 0x001234` with different VoiceTypes $\to$ verifies zero cross-contamination.
6. **Test 6 (Missing Master Safe Fallback):** `MyMod.esp` references missing master $\to$ `voice_type is None`, warnings logged, no exceptions.
7. **Test 7 (Invalid Master Index):** FormID with out-of-range master index $\to$ returns `None`, never treated as local.
8. **Test 8 (Master Immutability):** Verifies master file SHA256 hash before and after parsing to ensure 0 byte modifications.
9. **Test 9 (Master Cache Performance):** Verifies single read/parse when 500 dialogue records reference the same master via runtime instrumentation.
10. **Test 10 (ESL / Light Detection):** Verifies `0xFE...` FormIDs are detected and safely return `None` with an explicit warning.
11. **Test 11 (Origin-Record Resolution & No MAST-Order Override):** Verifies that FormID references resolve to their origin plugin, and that `MAST` declaration order is NOT used as an arbitrary override heuristic.
12. **Test 12 (Local TPLT Inheritance):** Verifies `NPC_ (Instance)` $\to$ `TPLT` $\to$ `NPC_ (Template)` $\to$ `VTCK` $\to$ `VTYP`.
13. **Test 13 (Master TPLT Inheritance):** Verifies `NPC_` in mod $\to$ `TPLT` in `MasterA.esm` $\to$ `VTCK` in `Skyrim.esm`.
14. **Test 14 (TPLT Cycle Protection):** Verifies cyclic template references (`NPC A <-> NPC B`) terminate safely with `voice_type is None`.
