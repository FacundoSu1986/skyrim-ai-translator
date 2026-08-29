# Voice runtime control - vanilla candidates

Structurally deterministic vanilla candidates prepared for manual runtime validation with `player.placeatme <ANAM BaseFormID>` + `say <DIAL FormID>` (all identity fields below come from the read-only finder run; no Skyrim.esm re-consultation needed).

Reading this evidence:

- `ANAM` is the NPC **base FormID**. `player.placeatme` spawns a new actor whose runtime reference FormID is created at runtime; never fabricate a reference FormID.
- `say` is a reference command: it must be executed on the spawned reference selected in the console, not on the base FormID.
- The `quest_edid` prefix gate is only a preferred/early quest-prefix heuristic; runtime quest availability was not proven.
- A LOW-risk candidate is a risk heuristic, not a runtime-proven control. No candidate below is "working", "runtime-proven", or "verified in-game" yet.

Funnel: `{"exact_fuz_match": 90, "explicit_anam": 223, "infos_total": 31465, "npc_speaker": 223, "quest_resolved": 90, "reported_count": 25, "runtime_low_risk": 1, "single_child_dial": 90, "single_response": 152, "voice_resolved": 223, "zero_ctda": 107}`
BSA metadata: `{"Skyrim - Voices_en0.bsa": {"hash_mismatches": 0, "hash_validated": 75408, "header_file_count": 75408, "indexed_voice_paths": 75408, "name_table_bytes": 2709902, "parsed_file_names": 75408, "size_bytes": 1807969854}, "Skyrim - Voices_es0.bsa": {"hash_mismatches": 0, "hash_validated": 74716, "header_file_count": 74716, "indexed_voice_paths": 74716, "name_table_bytes": 2685442, "parsed_file_names": 74716, "size_bytes": 1879699949}}`

| # | NPC (EDID) | Speaker | ANAM | VoiceType | Quest | Topic | DIAL | INFO | Resp | CTDA | Child INFO | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `DA01AzuraVoice` | NPC_ | `0x00028AE9` | FemaleUniqueAzura | DA01 | `` | `0x000A2C24` | `0x000A2C3F` | 1 | 0 | 1 | MEDIUM |
| 2 | `Nelacar` | NPC_ | `0x0001E7D5` | MaleElfHaughty | DA01 | `` | `0x000A2C23` | `0x000A2C45` | 1 | 0 | 1 | LOW |
| 3 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800F6` | `0x00080109` | 1 | 0 | 1 | HIGH |
| 4 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800F8` | `0x00080107` | 1 | 0 | 1 | HIGH |
| 5 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800F9` | `0x00080104` | 1 | 0 | 1 | HIGH |
| 6 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FA` | `0x00080102` | 1 | 0 | 1 | HIGH |
| 7 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FB` | `0x0008010A` | 1 | 0 | 1 | HIGH |
| 8 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FC` | `0x00080105` | 1 | 0 | 1 | HIGH |
| 9 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FD` | `0x00080106` | 1 | 0 | 1 | HIGH |
| 10 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FE` | `0x00080103` | 1 | 0 | 1 | HIGH |
| 11 | `EncDragonPriest` | NPC_ | `0x00023A93` | CrDragonPriestVoice | MG07 | `` | `0x000800FF` | `0x0008010B` | 1 | 0 | 1 | HIGH |
| 12 | `MQ304Alduin` | NPC_ | `0x0004E9BC` | CrUniqueAlduin | MQ305 | `` | `0x000ED356` | `0x000ED359` | 1 | 0 | 1 | HIGH |
| 13 | `MS14Helgi` | NPC_ | `0x000274A5` | FemaleChild | MS14 | `` | `0x0003664E` | `0x0003664F` | 1 | 0 | 1 | HIGH |
| 14 | `MS06Potema` | NPC_ | `0x00026C52` | FemaleCommander | MS06Start | `` | `0x0009D9C3` | `0x0009D9D7` | 1 | 0 | 1 | MEDIUM |
| 15 | `MS06Potema` | NPC_ | `0x00026C52` | FemaleCommander | MS06Start | `` | `0x0009D9C7` | `0x0009D9D9` | 1 | 0 | 1 | MEDIUM |
| 16 | `MS06Potema` | NPC_ | `0x00026C52` | FemaleCommander | MS06Start | `` | `0x0009D9D0` | `0x0009D9E4` | 1 | 0 | 1 | MEDIUM |
| 17 | `dunAnsilvundLuahAlSkaven` | NPC_ | `0x0002333A` | FemaleCondescending | dunAnsilvundQST | `` | `0x00093BBB` | `0x00093BC0` | 1 | 0 | 1 | HIGH |
| 18 | `dunAnsilvundLuahAlSkaven` | NPC_ | `0x0002333A` | FemaleCondescending | dunAnsilvundQST | `` | `0x00093BBC` | `0x00093BCB` | 1 | 0 | 1 | HIGH |
| 19 | `dunAnsilvundLuahAlSkaven` | NPC_ | `0x0002333A` | FemaleCondescending | dunAnsilvundQST | `` | `0x00093BBD` | `0x00093BC8` | 1 | 0 | 1 | HIGH |
| 20 | `dunAnsilvundLuahAlSkaven` | NPC_ | `0x0002333A` | FemaleCondescending | dunAnsilvundQST | `` | `0x000B6469` | `0x000B646A` | 1 | 0 | 1 | HIGH |
| 21 | `Eola` | NPC_ | `0x0001990F` | FemaleSultry | DA11HallScene | `` | `0x0007D92C` | `0x0007D935` | 1 | 0 | 1 | HIGH |
| 22 | `Eola` | NPC_ | `0x0001990F` | FemaleSultry | DA11HallScene | `` | `0x0007D92E` | `0x0007D93F` | 1 | 0 | 1 | HIGH |
| 23 | `Eola` | NPC_ | `0x0001990F` | FemaleSultry | DA11HallScene | `` | `0x00099CF2` | `0x00099CF8` | 1 | 0 | 1 | HIGH |
| 24 | `DA02Boethiah` | NPC_ | `0x0004D91B` | FemaleUniqueBoethiah | DA02 | `` | `0x0004D88C` | `0x0004D8C8` | 1 | 0 | 1 | HIGH |
| 25 | `DA02Boethiah` | NPC_ | `0x0004D91B` | FemaleUniqueBoethiah | DA02 | `` | `0x00081172` | `0x0008117A` | 2 | 0 | 1 | HIGH |

## Manual runtime reproduction procedure

Per candidate: spawn the NPC with its base FormID, then select/click the spawned reference in the console and verify it, and only then run `say` on that selected reference. The runtime reference FormID is created at runtime and is intentionally not listed here.

```text
# DA01AzuraVoice (FemaleUniqueAzura) - DA01 /  [MEDIUM]
player.placeatme 00028AE9 1

# In the console, select/click the newly spawned DA01AzuraVoice.
# Verify its BaseID is 00028AE9.
# Only with that NPC reference selected:

say 000A2C24
# INFO 0x000A2C3F | FUZ sound\voice\skyrim.esm\femaleuniqueazura\da01__000a2c3f_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# Nelacar (MaleElfHaughty) - DA01 /  [LOW]
player.placeatme 0001E7D5 1

# In the console, select/click the newly spawned Nelacar.
# Verify its BaseID is 0001E7D5.
# Only with that NPC reference selected:

say 000A2C23
# INFO 0x000A2C45 | FUZ sound\voice\skyrim.esm\maleelfhaughty\da01__000a2c45_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800F6
# INFO 0x00080109 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080109_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800F8
# INFO 0x00080107 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080107_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800F9
# INFO 0x00080104 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080104_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FA
# INFO 0x00080102 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080102_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FB
# INFO 0x0008010A | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__0008010a_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FC
# INFO 0x00080105 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080105_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FD
# INFO 0x00080106 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080106_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FE
# INFO 0x00080103 | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__00080103_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# EncDragonPriest (CrDragonPriestVoice) - MG07 /  [HIGH]
player.placeatme 00023A93 1

# In the console, select/click the newly spawned EncDragonPriest.
# Verify its BaseID is 00023A93.
# Only with that NPC reference selected:

say 000800FF
# INFO 0x0008010B | FUZ sound\voice\skyrim.esm\crdragonpriestvoice\mg07__0008010b_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# MQ304Alduin (CrUniqueAlduin) - MQ305 /  [HIGH]
player.placeatme 0004E9BC 1

# In the console, select/click the newly spawned MQ304Alduin.
# Verify its BaseID is 0004E9BC.
# Only with that NPC reference selected:

say 000ED356
# INFO 0x000ED359 | FUZ sound\voice\skyrim.esm\cruniquealduin\mq305__000ed359_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# MS14Helgi (FemaleChild) - MS14 /  [HIGH]
player.placeatme 000274A5 1

# In the console, select/click the newly spawned MS14Helgi.
# Verify its BaseID is 000274A5.
# Only with that NPC reference selected:

say 0003664E
# INFO 0x0003664F | FUZ sound\voice\skyrim.esm\femalechild\ms14__0003664f_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# MS06Potema (FemaleCommander) - MS06Start /  [MEDIUM]
player.placeatme 00026C52 1

# In the console, select/click the newly spawned MS06Potema.
# Verify its BaseID is 00026C52.
# Only with that NPC reference selected:

say 0009D9C3
# INFO 0x0009D9D7 | FUZ sound\voice\skyrim.esm\femalecommander\ms06start__0009d9d7_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# MS06Potema (FemaleCommander) - MS06Start /  [MEDIUM]
player.placeatme 00026C52 1

# In the console, select/click the newly spawned MS06Potema.
# Verify its BaseID is 00026C52.
# Only with that NPC reference selected:

say 0009D9C7
# INFO 0x0009D9D9 | FUZ sound\voice\skyrim.esm\femalecommander\ms06start__0009d9d9_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# MS06Potema (FemaleCommander) - MS06Start /  [MEDIUM]
player.placeatme 00026C52 1

# In the console, select/click the newly spawned MS06Potema.
# Verify its BaseID is 00026C52.
# Only with that NPC reference selected:

say 0009D9D0
# INFO 0x0009D9E4 | FUZ sound\voice\skyrim.esm\femalecommander\ms06start__0009d9e4_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# dunAnsilvundLuahAlSkaven (FemaleCondescending) - dunAnsilvundQST /  [HIGH]
player.placeatme 0002333A 1

# In the console, select/click the newly spawned dunAnsilvundLuahAlSkaven.
# Verify its BaseID is 0002333A.
# Only with that NPC reference selected:

say 00093BBB
# INFO 0x00093BC0 | FUZ sound\voice\skyrim.esm\femalecondescending\dunansilvundqst__00093bc0_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# dunAnsilvundLuahAlSkaven (FemaleCondescending) - dunAnsilvundQST /  [HIGH]
player.placeatme 0002333A 1

# In the console, select/click the newly spawned dunAnsilvundLuahAlSkaven.
# Verify its BaseID is 0002333A.
# Only with that NPC reference selected:

say 00093BBC
# INFO 0x00093BCB | FUZ sound\voice\skyrim.esm\femalecondescending\dunansilvundqst__00093bcb_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# dunAnsilvundLuahAlSkaven (FemaleCondescending) - dunAnsilvundQST /  [HIGH]
player.placeatme 0002333A 1

# In the console, select/click the newly spawned dunAnsilvundLuahAlSkaven.
# Verify its BaseID is 0002333A.
# Only with that NPC reference selected:

say 00093BBD
# INFO 0x00093BC8 | FUZ sound\voice\skyrim.esm\femalecondescending\dunansilvundqst__00093bc8_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# dunAnsilvundLuahAlSkaven (FemaleCondescending) - dunAnsilvundQST /  [HIGH]
player.placeatme 0002333A 1

# In the console, select/click the newly spawned dunAnsilvundLuahAlSkaven.
# Verify its BaseID is 0002333A.
# Only with that NPC reference selected:

say 000B6469
# INFO 0x000B646A | FUZ sound\voice\skyrim.esm\femalecondescending\dunansilvundqst__000b646a_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# Eola (FemaleSultry) - DA11HallScene /  [HIGH]
player.placeatme 0001990F 1

# In the console, select/click the newly spawned Eola.
# Verify its BaseID is 0001990F.
# Only with that NPC reference selected:

say 0007D92C
# INFO 0x0007D935 | FUZ sound\voice\skyrim.esm\femalesultry\da11hallscene__0007d935_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# Eola (FemaleSultry) - DA11HallScene /  [HIGH]
player.placeatme 0001990F 1

# In the console, select/click the newly spawned Eola.
# Verify its BaseID is 0001990F.
# Only with that NPC reference selected:

say 0007D92E
# INFO 0x0007D93F | FUZ sound\voice\skyrim.esm\femalesultry\da11hallscene__0007d93f_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# Eola (FemaleSultry) - DA11HallScene /  [HIGH]
player.placeatme 0001990F 1

# In the console, select/click the newly spawned Eola.
# Verify its BaseID is 0001990F.
# Only with that NPC reference selected:

say 00099CF2
# INFO 0x00099CF8 | FUZ sound\voice\skyrim.esm\femalesultry\da11hallscene__00099cf8_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# DA02Boethiah (FemaleUniqueBoethiah) - DA02 /  [HIGH]
player.placeatme 0004D91B 1

# In the console, select/click the newly spawned DA02Boethiah.
# Verify its BaseID is 0004D91B.
# Only with that NPC reference selected:

say 0004D88C
# INFO 0x0004D8C8 | FUZ sound\voice\skyrim.esm\femaleuniqueboethiah\da02__0004d8c8_1.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

# DA02Boethiah (FemaleUniqueBoethiah) - DA02 /  [HIGH]
player.placeatme 0004D91B 1

# In the console, select/click the newly spawned DA02Boethiah.
# Verify its BaseID is 0004D91B.
# Only with that NPC reference selected:

say 00081172
# INFO 0x0008117A | FUZ sound\voice\skyrim.esm\femaleuniqueboethiah\da02__0008117a_2.fuz | matching BSAs: Skyrim - Voices_en0.bsa, Skyrim - Voices_es0.bsa

```
