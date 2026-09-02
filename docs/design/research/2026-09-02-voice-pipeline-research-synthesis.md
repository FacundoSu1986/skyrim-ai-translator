# Voice Pipeline Research Synthesis

**Status:** RESEARCH SYNTHESIS / CONTINUATION CHECKPOINT  
**Captured:** 2026-09-02  
**Scope:** Skyrim voice asset pipeline, generalization, offline architecture and bounded runtime research  
**Authority:** non-canonical research summary; runtime/tests/evidence take precedence  

---

## 1. Purpose

This document preserves the technically useful conclusions from multiple independent brainstorming and review passes so future work does not depend on conversational context.

It deliberately separates:
- established evidence;
- retained architectural ideas;
- hypotheses requiring experiments;
- deferred directions;
- rejected assumptions;
- the currently recommended next increment.

This document is not a runtime proof and does not authorize implementation claims beyond the referenced evidence.

---

## 2. Established foundation

### 2.1 Deterministic voice asset identity

The repository has structural evidence for the mapping:

```text
INFO identity + resolved VoiceType
        ↓
deterministic basename
        ↓
Sound/Voice/<defining_plugin>/<VoiceType>/<basename>.fuz
```

The path must be based on the plugin that defines the INFO, not merely a job-level target plugin.

Raw full FormID must not be treated as globally unique identity.

The useful persistent identity is based on:
- defining plugin + local 24-bit object ID + TRDT response number

with VoiceType differentiating emitted assets where one INFO can be spoken by multiple VoiceTypes.

### 2.2 FUZ container

The repository already owns deterministic clean Python helpers for:

```text
LIP + XWM
    ↓
FUZE v1 container
```

and corresponding unpack/round-trip validation.

Do not reopen the question of basic FUZ container layout unless new contradictory runtime evidence appears.

### 2.3 Verified custom runtime control

The Nelacar control established, in one environment with unambiguous process attribution:

```text
Spanish synthetic speech
         ↓
        WAV
         ↓
LipGenerator -Language:Spanish
         ↓
        LIP
         ↓
     xWMAEncode
         ↓
    genuine XWM
         ↓
repository pack_fuz()
         ↓
exact loose Skyrim voice path through MO2
         ↓
  Skyrim SE 1.6.1170
         ↓
custom Spanish audio heard + user-observed synchronized lips
```

The runtime audio/lipsync outcome is human-observed.

Do not upgrade it to machine audiovisual verification.

Do not claim multiple unambiguous custom runs if the evidence still records only one verified-environment run.

### 2.4 Proven tool boundary

The successful experimental toolchain uses operator-installed tools.

They remain:
- detected;
- invoked;
- hashed/versioned where useful;
- never bundled;
- never copied into repository.

The repository may wrap execution but must not redistribute proprietary binaries or data.

### 2.5 Genuine XWM requirement

A production FUZ audio payload must use a valid XWM bitstream/container.

Renaming another audio format to `.xwm` is invalid.

Do not assume a generic multimedia encoder supports valid Skyrim XWM output without independent proof.

The currently proven path remains the user-installed XWMA encoder used in runtime evidence.

---

## 3. Main architectural insight retained from brainstorming

There are two distinct products/problems and they must not be conflated.

### Lane A — Offline/static translation

```text
ESP/ESM
   ↓
INFO / dialogue metadata
   ↓
VoiceType resolution
   ↓
translation
   ↓
  TTS
   ↓
  WAV
   ↓
  LIP
   ↓
  XWM
   ↓
  FUZ
   ↓
Skyrim voice paths
   ↓
MO2 / generated voice pack
```

This remains the primary MVP direction.

### Lane B — Runtime/live delivery

Conceptually:

```text
runtime event or external message
               ↓
     bounded local sidecar
               ↓
     text / translation / TTS
               ↓
     runtime Skyrim bridge
               ↓
controlled NPC or dialogue carrier
```

This is a separate future research lane.

It must not make:
- SKSE mandatory for the offline translator;
- networking mandatory for offline translation;
- runtime hooks part of deterministic asset generation.

See the independent External Messenger Companion specification (`docs/design/specs/2026-09-02-external-messenger-companion-design.md`) for that optional lane.

---

## 4. Retained idea: controlled dialogue carrier

A strong experimental technique is to stop using arbitrary vanilla dialogue when investigating basic runtime delivery.

Instead control:
- NPC;
- VoiceType;
- Quest;
- Topic;
- INFO;
- audio path;
- trigger;

and change one relevant variable at a time.

This sharply reduces ambiguity between:
- asset generation;
- filename identity;
- VoiceType;
- INFO ownership;
- dialogue resolution;
- MO2 staging;
- Skyrim runtime behavior.

A controlled carrier proving generated speech does NOT prove arbitrary replacement of every vanilla INFO.

Those claims must remain separate.

---

## 5. Retained invariant: one canonical transcript

The translated text used for speech generation and lip generation should come from the same canonical value:

```text
translated_text
      │
      ├── TTS
      └── lip generation
```

Avoid architecture in which TTS and lip generation silently consume different textual representations.

Future planning objects should retain the exact text used to generate both artifacts.

---

## 6. Highest-value next experiment

If no newer evidence supersedes this checkpoint, the recommended next experimental task is:

`VOICE_GENERALIZATION_AB_SPIKE`

using a controlled second actor / second VoiceType.

Preferred target:
- controlled Argonian actor;
- VoiceType = `FemaleArgonian`.

Create two controlled Topics/INFO entries under the same environment.

### A-control

```text
Topic A
   ↓
INFO A
   ↓
WAV + LIP loose
```

Suggested clearly identifiable phrase:
> "Saludos a mis amigos Romel y Josue, prueba número uno."

### B-control

```text
Topic B
   ↓
INFO B
   ↓
LIP + genuine XWM
   ↓
  FUZ
```

Suggested phrase:
> "Saludos a mis amigos Romel y Josue, prueba número dos."

Hold constant:
- actor;
- VoiceType;
- plugin;
- game build;
- MO2 profile;
- runtime session where practical;
- TTS family;
- delivery trigger.

Change primarily the packaging mode.

Observe audio and lipsync independently.

### Gates

- `CONTROLLED_SECOND_ACTOR` = PASS/FAIL
- `WAV_LOOSE_AUDIO_PROOF` = PASS/FAIL
- `WAV_LOOSE_LIPSYNC_PROOF` = PASS/FAIL
- `FUZ_SECOND_VOICETYPE_AUDIO_PROOF` = PASS/FAIL
- `FUZ_SECOND_VOICETYPE_LIPSYNC_PROOF` = PASS/FAIL

Do not define:
- `ARBITRARY_VANILLA_INFO_OVERRIDE` = PASS

from this experiment.

---

## 7. A/B decision matrix

| WAV + LIP | FUZ | Interpretation |
|---|---|---|
| PASS | PASS | Both packaging modes work in the tested environment |
| FAIL | PASS | Keep FUZ as the proven/recommended production route |
| PASS | FAIL | Investigate FUZ/XWM/path/staging specific failure |
| FAIL | FAIL | Investigate controlled dialogue/plugin/VoiceType/runtime delivery before changing the asset pipeline |

This matrix is deliberately scoped to the tested environment.

Loose WAV/LIP behavior must not be generalized across Skyrim versions/configurations until proven.

---

## 8. Exit condition for basic format research

If a controlled second VoiceType produces successful FUZ audio and lipsync:

```text
MaleElfHaughty / Nelacar PASS
FemaleArgonian / controlled actor PASS
```

then stop repeatedly testing basic FUZ packaging.

That is sufficient evidence to proceed to productization unless a new contradiction appears.

---

## 9. First productization target after the spike

The recommended first production increment is a pure immutable planning contract conceptually equivalent to:

```python
@dataclass(frozen=True, slots=True)
class VoiceAssetPlan:
    defining_plugin: str
    local_object_id: int
    response_number: int
    voice_type: str
    quest_edid: str
    topic_edid: str
    translated_text: str
    tts_voice: str
    basename: str
    relative_fuz_path: Path
```

The exact API must be derived from current code/tests at implementation time.

Responsibilities:
```text
StringEntry / dialogue metadata + selected translated text / TTS voice
                         ↓
                      validate
                         ↓
              deterministic VoiceAssetPlan
```

It must initially remain free of:
- subprocess;
- filesystem writes;
- TTS execution;
- LipGenerator execution;
- XWM encoding;
- MO2;
- Creation Kit;
- network calls.

---

## 10. Productization sequence retained

After the pure planner, prefer atomic increments:

### A. VoiceAssetPlan
Pure identity and validation.

### B. TTS → normalized WAV
Convert the existing TTS output into a stable PCM input contract.

### C. Lip generator adapter
External-tool adapter with:
- user-installed executable discovery;
- explicit arguments;
- isolated working directory;
- timeout;
- exit-code handling;
- expected-output validation;
- cleanup;
- no bundling.

The isolated CWD is important because the proven LipGenerator execution creates a temporary `tmp16khz.wav`.

### D. XWM encoder adapter
Equivalent bounded adapter for the proven user-installed encoder.

### E. FUZ assembly and staging
```text
LIP + XWM
    ↓
pack_fuz()
    ↓
validated FUZ
    ↓
atomic deterministic staging
```

### F. Orchestration
Connect:
```text
VoiceAssetPlan
      ↓
     TTS
      ↓
     WAV
      ↓
     LIP
      ↓
     XWM
      ↓
     FUZ
```
without collapsing all responsibilities into one object.

---

## 11. Retained idea: manifest and incremental regeneration

A future generated voice pack should have an explicit manifest/cache model.

Useful inputs include hashes or stable identities for:
- source text
- translated text
- TTS configuration
- VoiceType
- dialogue identity
- WAV
- LIP
- XWM
- FUZ

This can support:
- deterministic regeneration;
- skipping unchanged dialogue;
- reproducible debugging;
- differential updates;
- invalidation when translation/TTS configuration changes.

Do not introduce this before the basic production pipeline requires it.

---

## 12. Hard semantic problem after asset productization

The most important unresolved domain problem is not FUZ generation.

It is:
```text
INFO
  ↓
who can actually speak this line?
  ↓
VoiceType(s)
```

The currently simple path is approximately:
```text
INFO.ANAM → NPC_ → VTCK / template → VTYP
```

Generic dialogue may require reasoning over:
- CTDA conditions;
- actor identity conditions;
- VoiceType conditions;
- quest aliases;
- scenes;
- templates;
- runtime-dependent actor selection.

A single INFO may require multiple voice assets.

Therefore the likely production unit is:
```text
INFO response × VoiceType
```
rather than one asset per INFO.

Do not recreate a fake "winning override" model based only on master order.

---

## 13. Runtime/live lane retained for later

Several brainstorm ideas support the feasibility of a future runtime lane, but they are not required for the offline MVP.

Potential future research categories include:
- controlled dialogue carrier
- local sidecar
- minimal Skyrim runtime bridge
- message slots / reload behavior
- runtime asset caching
- dynamic speech triggering

The first runtime experiment should remain local and bounded.

External messaging belongs after local delivery is proven.

Refer to `docs/design/specs/2026-09-02-external-messenger-companion-design.md` for the separate companion/messaging design.

---

## 14. Explicitly deferred or rejected assumptions

The following ideas must NOT enter the current MVP merely because they appeared during brainstorming:

### Generic runtime hooking
Do not start with engine-level audio hooks, virtual archives, arbitrary sound-descriptor interception or streaming injection.

These increase complexity before the static pipeline is productized.

### Dynamic BSA mutation
Do not mutate or rewrite Skyrim BSAs at runtime.

Masters and BSAs remain read-only.

### Alternative XWM encoders
Do not replace the proven XWM path with an encoder that has not independently demonstrated valid Skyrim-compatible XWM output.

### Alternative lip-generation stacks
Alternative/open implementations may be investigated later but must not replace the proven operator-installed path until they have independent in-game evidence and their license/redistribution boundary has been reviewed.

### Voice cloning
Not required for the translation MVP.

It adds substantial:
- legal;
- consent;
- model;
- dataset;
- compute;
- maintenance;
questions.

Do not make cloning a prerequisite.

### Large TTS backend matrix
Do not prematurely integrate multiple hosted/local TTS providers.

Use an interchangeable architecture only when product requirements justify another backend.

### Copying third-party architectures
Public technical information can motivate hypotheses.

Do not copy third-party:
- source code;
- documentation;
- assets;
- package layouts;
- proprietary resources;
- architectural implementation merely because another mod uses it.

Derive contracts independently and validate them against our own evidence.

---

## 15. Claims explicitly NOT established

At this checkpoint, do not claim any of the following unless newer evidence exists:
- arbitrary vanilla INFO replacement works universally
- all VoiceTypes have been proven
- loose WAV + LIP works universally on Skyrim SE
- dynamic replacement of one voice asset can be repeated indefinitely inside one Skyrim process
- Skyrim runtime caching behavior is understood
- generic Quest/Scene/Alias/CTDA VoiceType resolution is solved
- multi-VoiceType fan-out is implemented
- production Edge-TTS → WAV → LIP → XWM → FUZ orchestration is complete
- runtime SKSE bridge is required
- runtime SKSE bridge is implemented
- external messaging is implemented
- voice cloning is required
- alternative lip/XWM implementations are runtime-proven

---

## 16. Evidence vs hypothesis discipline

Use these labels consistently:

- **PROVEN**: Supported by repository tests or explicit runtime evidence.
- **STRUCTURALLY PROVEN**: Binary/path/parser contract demonstrated without necessarily proving live game behavior.
- **HUMAN-OBSERVED RUNTIME**: Operator reports visible/audible game behavior but no machine audiovisual analysis exists.
- **HYPOTHESIS**: Technically plausible but needs an experiment.
- **DEFERRED**: Potentially useful but outside the current increment.
- **REJECTED FOR CURRENT SCOPE**: Not justified for the MVP, disproven, unnecessarily risky or dependent on unsupported assumptions.

Never convert HYPOTHESIS into PROVEN by repetition in documentation.

---

## 17. Recommended continuation checkpoint

A future maintainer/session should start here:

1. Fetch current `origin/main`.
2. List all open PRs.
3. Read:
   - `docs/skyrim_voice_asset_spike.md`;
   - `docs/evidence/voice-in-game-proof/custom_nelacar_runtime_control.md`;
   - any newer voice runtime evidence;
   - this research synthesis.
4. Treat newer runtime/test evidence as authoritative over this file.
5. Check whether `VOICE_GENERALIZATION_AB_SPIKE` has already been executed.
6. If it has NOT been superseded, execute that controlled second-VoiceType experiment.
7. If second-VoiceType FUZ audio+lipsync is PASS, stop basic packaging spikes and begin the pure `VoiceAssetPlan` increment.
8. Do not start runtime hooks, external messaging, voice cloning or generic VoiceType resolution in parallel unless separately scoped and proven non-colliding.

---

## 18. Current directional roadmap

```text
CURRENT VERIFIED FOUNDATION
           │
           ▼
VOICE_GENERALIZATION_AB_SPIKE
           │
           ├── second VoiceType FUZ FAIL
           │         ↓
           │   classify failure
           │
           └── second VoiceType FUZ PASS
                     ↓
         close basic format research
                     ↓
               VoiceAssetPlan
                     ↓
             TTS → WAV contract
                     ↓
           LipGenerator adapter
                     ↓
                XWM adapter
                     ↓
            FUZ assembly/staging
                     ↓
                orchestration
                     ↓
               manifest/cache
                     ↓
       generic INFO × VoiceType resolver
                     ↓
                  OFFLINE MVP
                     ↓
             optional runtime R&D
```

---

## 19. Why this document exists

This file intentionally captures decisions that otherwise existed only in conversational brainstorming.

Its purpose is continuity, not authority.

When a future discussion becomes too large, the project should be resumable from repository artifacts rather than relying on hidden or ephemeral conversational context.
