# External Messenger Companion — Experimental Feature Design

**Status:** DESIGN / NOT IMPLEMENTED
**Scope:** future optional feature; outside the current offline translation MVP
**Date:** 2026-09-02

## 1. Intent

Explore an optional Skyrim companion NPC that can deliver externally sourced messages to the player while the game is running.

The intended experience is similar to an in-world messenger:

```text
authorized external sender
        ↓
external messaging transport
        ↓
local SkyAI sidecar
        ↓
bounded message queue
        ↓
Skyrim runtime bridge
        ↓
controlled companion NPC
        ↓
spoken and/or subtitled message
```

The companion may eventually follow the player or remain dormant until a message is pending.

This document records a product hypothesis. It does not claim that the runtime bridge, live asset reload, dialogue triggering, or external messaging integration has been proven.

## 2. Motivation

Long gameplay sessions can make external notifications easy to miss.

The proposed feature would provide an optional, immersive path for a trusted person to communicate with the player through an NPC inside Skyrim.

Example future interaction:

**External message:**
“La comida está lista.”

**In-game companion:**
“Tienes un mensaje: la comida está lista.”

The feature is not part of the core translation pipeline and must remain architecturally optional.

## 3. Architectural boundary

Keep network-facing functionality outside Skyrim whenever practical.

Preferred conceptual separation:

```text
External transport
        ↓
Python sidecar
        ↓
validated MessageEnvelope
        ↓
bounded local bridge
        ↓
Skyrim-specific adapter
        ↓
controlled NPC
```

The external transport must not directly control Skyrim, the operating system, an AI agent, or a shell.

The Skyrim-facing component should receive only a minimal validated message contract.

## 4. Initial transport

Telegram is the initial candidate for investigation because a simple bot-based ingress can be prototyped independently from the Skyrim runtime bridge.

This is not a commitment to Telegram as a permanent dependency.

Transport-specific behavior must remain behind an abstraction so that another authorized transport may be evaluated later.

WhatsApp and other providers are out of scope for the first proof.

## 5. Message contract

Future implementations should converge on a small value-like contract conceptually similar to:

**MessageEnvelope**

- `message_id`
- `sender_id`
- `text`
- `received_at`
- `priority`

The exact Python API is intentionally **NOT** specified by this design PR.

The transport must not be allowed to inject arbitrary Skyrim commands or executable instructions.

## 6. Security invariants

Any implementation must preserve all of the following:

1. External message content is **DATA ONLY**.

2. Message text must never become:

   - shell commands;
   - Python code;
   - Papyrus console commands;
   - Skyrim console commands;
   - prompts for an autonomous coding/system agent.

3. Explicit allow-list of authorized senders or transport identities.

4. Authentication credentials remain local secrets:

   - never committed;
   - never included in logs;
   - never embedded in generated mods.

5. Apply bounded:

   - message length;
   - queue length;
   - rate;
   - network timeout;
   - retry policy.

6. Fail closed when sender authentication cannot be established.

7. External messaging must have an explicit enable/disable control.

8. Skyrim master files and BSAs remain read-only.

9. No proprietary tool or runtime binary is bundled by this feature.

10. Network behavior must comply with the repository’s existing default-deny test policy.

## 7. Companion behavior hypothesis

A future controlled companion may:

- follow the player at a safe distance;
- remain non-hostile;
- avoid combat participation where practical;
- queue messages during unsuitable gameplay states;
- deliver pending messages after combat/dialogue/cinematic activity;
- optionally display a subtitle;
- optionally speak a generated voice asset.

Exact follower AI, packages, Creation Kit records, and runtime behavior are not proven by this document.

## 8. Reuse of existing voice work

The repository already contains experimental evidence for deterministic Skyrim voice assets and custom FUZ runtime playback.

That work may become reusable for companion speech.

However, this design does **NOT** claim that dynamically replacing/reloading arbitrary message audio during one running Skyrim session already works.

Runtime reload/caching behavior must be tested independently.

## 9. POC sequence

### POC-001 — Local companion delivery

No external messaging provider.

**Goal:**

```text
local sidecar
→ arbitrary bounded text
→ controlled Skyrim bridge
→ controlled companion
→ player receives message
```

**Primary gate:**

`LOCAL_COMPANION_MESSAGE_DELIVERY = PASS`

This POC must isolate the Skyrim bridge before introducing Internet/network variables.

### POC-002 — External text ingress

Connect exactly one authenticated transport to the already proven local queue.

**Initial candidate:** Telegram.

**Goal:**

```text
allow-listed sender
→ external text message
→ local validated MessageEnvelope
→ same POC-001 delivery path
```

**Gate:**

`EXTERNAL_MESSAGE_TO_COMPANION = PASS`

Transport-specific evidence may additionally record:

`TELEGRAM_TO_COMPANION_MESSAGE = PASS`

if Telegram is the transport actually tested.

### POC-003 — Optional reply

Investigate a deliberately narrow reply surface from Skyrim back to the authorized sender.

Examples may include explicit fixed responses such as:

- “Ya voy.”
- “Dame cinco minutos.”
- “Recibido.”

Do not permit arbitrary execution or reinterpret a reply as a command.

**Gate:**

`COMPANION_REPLY_TO_EXTERNAL_SENDER = PASS`

## 10. Runtime questions that remain open

Before production implementation, independently determine:

- how the Python sidecar signals Skyrim;
- whether SKSE is necessary;
- how a controlled Topic/INFO should be triggered;
- whether Skyrim caches companion voice assets;
- whether multiple rotating dialogue slots are necessary;
- whether message delivery can safely wait until combat/dialogue ends;
- what happens when multiple messages arrive;
- whether subtitles and generated speech can remain synchronized;
- how shutdown/restart preserves or discards queued messages.

Do not choose an implementation simply because a third-party project uses it.

## 11. Explicit non-goals

The initial feature does **NOT** include:

- WhatsApp integration;
- voice-note ingestion;
- arbitrary vanilla dialogue interception;
- arbitrary NPC voice replacement;
- voice cloning;
- autonomous NPC intelligence;
- autonomous operating-system commands;
- BSA mutation;
- virtual BSA/VFS injection;
- reverse engineering of Skyrim audio internals;
- bundling proprietary Bethesda or Microsoft tools.

## 12. Relationship to the current MVP

The current offline translator remains the priority.

This feature is an optional future capability and must not force:

- SKSE into the core translator;
- network access into offline workflows;
- runtime hooks into deterministic voice generation;
- external-account configuration onto users who only want offline translation.

Preferred dependency direction:

```text
core translation/voice contracts
             ↑
             |
optional companion feature
```

Never:

```text
core translator
      ↓
mandatory external messenger/runtime dependency
```

## 13. First implementation decision

**Do NOT start with Telegram.**

Start with POC-001.

The first runtime experiment should prove only:

```text
local bounded message
        ↓
controlled NPC
        ↓
message visibly/audibly delivered in Skyrim
```

Only after this passes should external transport integration begin.

## 14. Success criterion for this design

This design is complete when it gives a future implementation agent enough boundaries to create POC-001 without assuming:

- Telegram is already integrated;
- runtime dynamic audio reload is proven;
- SKSE is definitely required;
- arbitrary NPC interception is required;
- external messages may execute commands.
