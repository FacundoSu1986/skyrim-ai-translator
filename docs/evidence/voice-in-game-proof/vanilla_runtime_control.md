# Vanilla Runtime Control Validation — Nelacar

status: VANILLA_RUNTIME_CONTROL_PASS
date: 2026-08-29

## Classification

- STRUCTURAL PROOF: derived by the finder / PR #30. NOT re-derived at runtime by
  this validation (no ESM parsing performed here; values taken as established by
  the finder's structural analysis).
- RUNTIME OBSERVATION: performed by a human operator at a running game session.
  The agent (no display / no audio capture / cannot drive the in-game console)
  did NOT observe the screen or audio and did NOT infer HEARD from the command
  having executed. Observed results are operator-reported.

## Environment

- Skyrim version: 1.6.1170.0 (verified from SkyrimSE.exe VersionInfo)
- executable: G:\SteamLibrary\steamapps\common\Skyrim Special Edition\SkyrimSE.exe
  launched via MO2. NOT SkyrimSELauncher.exe.
- MO2 instance: G:\Modding\MO2\SkyrimSE
- MO2 profile: Default
  - enabled mods (modlist.txt): only vanilla DLCs + Creation Club resources
    (Dawnguard, Dragonborn, HearthFires, _ResourcePack, ccBGSSSE001-Fish,
    ccBGSSSE025-AdvDSGS, ccBGSSSE037-Curios, ccQDRSSE001-SurvivalMode)
  - no voice-replacement mod enabled
- custom voice override absent: PASS
  - operator-confirmed clean launch
  - agent file-scan found NO loose FUZ `da01__000a2c45_1.fuz` anywhere in
    MO2\mods, MO2\overwrite, MO2\profiles, MO2\downloads, or
    Skyrim\Data\Sound\Voice\Skyrim.esm\MaleElfHaughty\
  - control A therefore uses exclusively the vanilla BSA asset

## Identity (STRUCTURAL PROOF — finder / PR #30)

- NPC EDID: Nelacar
- Base FormID (ANAM): 0001E7D5
- DIAL FormID: 000A2C23
- INFO FormID: 000A2C45
- VoiceType: MaleElfHaughty
- expected vanilla FUZ:
  sound\voice\skyrim.esm\maleelfhaughty\da01__000a2c45_1.fuz
- finder structural flags:
  speaker_record_type = NPC_
  child_info_count = 1
  ctda_count = 0
  single TRDT
  response_number = 1
  exact vanilla FUZ match = true

## Runtime Run 1 (RUNTIME OBSERVATION — operator)

- procedure: `player.placeatme 0001E7D5 1` -> click the spawned Nelacar
  (console shows BaseID 0001E7D5; NOT `prid 0001E7D5`) -> `say 000A2C23`
- selected BaseID verified: YES (0001E7D5)
- audio: HEARD (vanilla)
- lips: NOT REPORTED (UNCERTAIN) — not used as proof of audio
- subtitle: NOT REPORTED (UNCERTAIN) — not used as proof of audio
- console errors: PRESENT (exact text pending — see Notes)

## Runtime Run 2 (RUNTIME OBSERVATION — operator, repeatable)

- procedure: new spawned Nelacar -> select runtime reference -> verify BaseID
  0001E7D5 -> `say 000A2C23`
- selected BaseID verified: YES (0001E7D5)
- audio: HEARD (vanilla)
- lips: NOT REPORTED (UNCERTAIN) — not used as proof of audio
- subtitle: NOT REPORTED (UNCERTAIN) — not used as proof of audio
- console errors: PRESENT (exact text pending — see Notes)

## Conclusion

VANILLA_RUNTIME_CONTROL_PASS

- Nelacar reference (BaseID 0001E7D5) + DIAL 000A2C23 + vanilla BSA asset
  -> runtime playback works: vanilla audio audible in two independent,
  controlled runs.
- This does NOT prove: custom FUZ generation, Spanish audio, LIP correctness,
  or production integration.

## Notes / pending

- Operator reported console errors present during the runs. Their presence
  does not negate the audible vanilla audio observation that drives this gate.
- CONSOLE_MESSAGE_EXACT_TEXT_UNAVAILABLE
  classification: UNKNOWN
  (exact console text was not captured by the operator; it is not known and is
  NOT invented in this record.)
- Agent did NOT launch Skyrim, did NOT modify Skyrim.esm or any BSA, did NOT
  generate WAV/LIP/XWM/FUZ, did NOT enable any voice mod, and did NOT alter
  toolchain state.
- Original record: no PR opened; evidence existed only on branch
  spike/voice-vanilla-runtime-control (forked from origin/main a4888b8...).
- Preservation: docs-only branch docs/voice-vanilla-runtime-evidence restored
  this file from commit 49ea2a3fc2163ea67789fda16f058b04104ce36c on top of
  current origin/main f9f279e6da3ec3b759e664911ad15bde33e2c80c.
