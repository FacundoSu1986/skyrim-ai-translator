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

## 5. Message contract and delivery semantics

Future implementations should converge on a small value-like contract conceptually similar to:

**MessageEnvelope**

- `message_id`: transport/account-scoped unique message identifier.
- `sender_id`: normalized, transport-authenticated sender identity.
- `text`: bounded, plain-text human message content (data only).
- `received_at`: UTC timestamp of receipt by the local sidecar.
- `expires_at`: optional UTC timestamp after which the message must not be delivered.
- `priority`: optional bounded prioritization tag (default: normal).
- `correlation_id`: optional identifier linking a reply or state acknowledgement to the originating message.

The exact Python API is intentionally **NOT** specified by this design PR. These represent architectural contract boundaries for future implementation.

### Delivery semantics and invariants

Future POCs and runtime implementations must enforce the following delivery semantics:

1. **Uniqueness Scope:**
   `message_id` MUST be unique within the scope of one configured transport and account identity.

2. **Deduplication:**
   A duplicate `message_id` received from the same transport identity MUST NOT produce a second in-game delivery or duplicate companion dialogue prompt. The local sidecar must detect duplicate receipts and discard them with an observable deduplication log event.

3. **Ordering:**
   Delivery ordering MUST be FIFO (First-In, First-Out) within one authenticated sender/transport queue unless an explicit, bounded priority policy is defined and configured.

4. **Expiration:**
   Expired messages (`now > expires_at`) MUST NOT be delivered silently to the player in-game. When expired while queued or in transit, the message must be dropped or rejected with an observable state transition and audit log.

5. **Lifecycle Acknowledgements:**
   The messaging lifecycle MUST explicitly distinguish between:
   - `accepted-by-sidecar`: message validated, authenticated, and staged in the local queue;
   - `delivered-in-game`: message rendered as subtitle and/or spoken audibly by the companion NPC to the player in Skyrim.
   These two states must never be conflated.

6. **Reply Correlation:**
   Any outbound companion reply (such as POC-003 fixed canned responses) MUST explicitly reference the originating `message_id` / `correlation_id`. Uncorrelated replies are invalid.


## 6. Security invariants

Any implementation must preserve all of the following:

1. External message content is **DATA ONLY**.

2. Message text must never become:

   - shell commands;
   - Python code;
   - Papyrus console commands;
   - Skyrim console commands;
   - prompts for an autonomous coding/system agent.

3. **Authenticated Sender Identity (`sender_id`):**
   - `sender_id` MUST come exclusively from transport-authenticated metadata (e.g. verified platform account ID bound to the configured transport connection).
   - `sender_id` MUST be normalized (case and format) before evaluation against an explicit allow-list.
   - `sender_id` MUST NEVER be extracted from message body text, unauthenticated headers, or user-controlled payload fields.
   - Any message lacking transport-level proof of identity or failing allow-list matching MUST be rejected immediately (fail closed) with an observable audit record.

4. **Authentication Credentials and Local Secrets:**
   - Secrets (such as bot tokens or API keys) MUST never be committed to Git, never printed in plaintext in logs or crash traces (mandatory redaction), and never embedded into generated mod plugins or archives.
   - Storage MUST use local, protected mechanisms: OS credential stores or user-profile-isolated configuration files with strict access controls (e.g. POSIX `0600` or Windows ACLs restricted exclusively to the active user profile). World-readable files or storage accessible by unrelated local processes are forbidden.
   - Implementations must support manual rotation and revocation.
   - If credentials are missing, invalid, or revoked, external messaging MUST fail closed: the transport remains shut down and no messages are accepted.
   - Note: No specific storage backend or library is mandated at this design stage; any chosen mechanism must satisfy these access-control and redaction invariants.

5. **Verifiable Bounds and Degradation:**
   All ingestion and queue boundaries MUST be finite, configurable, and independently verifiable:
   - **Message length:** MUST have a finite upper bound (e.g. configurable byte/character ceiling). Oversized messages MUST be rejected outright with an observable rejection signal; they must not be partially ingested or truncated silently.
   - **Queue capacity:** MUST have a finite upper bound. When full, ingestion MUST NOT block the sidecar or game indefinitely; excess messages MUST be rejected (or dropped under an explicit bounded policy) with an observable drop metric/signal.
   - **Ingress rate:** MUST have finite rate limiting per sender and globally to prevent spam or resource exhaustion.
   - **Network timeouts:** All network operations MUST have finite timeouts.
   - **Retry policy:** Retries MUST have a finite maximum attempt count and exponential backoff; retry exhaustion MUST yield an observable terminal failure state.
   - **Expired messages:** Messages that exceed their expiration window while queued MUST be discarded with an observable notification.

6. Fail closed when sender authentication cannot be established.

7. **Feature Enablement and Lifecycle:**
   - External messaging MUST default to **disabled** (`enabled = false`).
   - Requiring explicit user opt-in before opening network ports, connecting to messaging providers, or accepting incoming messages.
   - When the feature is disabled or revoked by the user, active transport connections MUST terminate immediately, and any un-delivered pending messages in the queue MUST be cleared/purged immediately; pending messages MUST NOT linger or be delivered upon subsequent re-enablement.

8. **Queue Retention and Storage Policy:**
   - In-memory queueing is the default architectural posture: if the application, sidecar, or game shuts down or restarts, queued in-flight messages are dropped (fail-closed) and an observable restart log is emitted.
   - If persistent queueing is ever evaluated in future work, it MUST use encrypted-at-rest storage with user-restricted ACLs, enforce mandatory per-message expiration, and ensure guaranteed deletion immediately after delivery or revocation.

9. Skyrim master files and BSAs remain read-only.

10. No proprietary tool or runtime binary is bundled by this feature.

11. Network behavior must comply with the repository’s existing default-deny test policy.

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

No external messaging provider. Isolates the Skyrim runtime bridge before introducing Internet or network variables.

**Goal:**

```text
local sidecar
→ arbitrary bounded text
→ controlled Skyrim bridge
→ controlled companion
→ player receives message
```

**Reproducible Evaluation Gate:**

`LOCAL_COMPANION_MESSAGE_DELIVERY`

- **Input:** Synthetic local test message payload injected via local test harness (no external network).
- **Execution Environment:** Running Skyrim SE/AE test session with a controlled test companion NPC loaded, alongside the SkyAI local test harness.
- **Observable Output:** Companion NPC actively delivers the message to the player (in-game subtitle display and/or audible voice playback matching the input text) within bounded timeout.
- **Rejection / Error Cases:** Oversized input, empty text, or malformed payloads are rejected fail-closed without crashing the game engine or leaving the companion in an unrecoverable state.
- **Evidence Artifact:** Automated run log capturing injection, transmission, and in-game delivery event timestamps, accompanied by recorded game output or visual/audio log verification.
- **Authorization Criteria (PASS):** Text delivered in-game matches synthetic input exactly, companion NPC state machine returns to clean idle, zero game crashes across repeated test cycles.

### POC-002 — External text ingress

Connect exactly one authenticated transport to the already proven local delivery path.

**Initial candidate:** Telegram bot.

**Goal:**

```text
allow-listed sender
→ external text message
→ local validated MessageEnvelope
→ same POC-001 delivery path
```

**Reproducible Evaluation Gate:**

`EXTERNAL_MESSAGE_TO_COMPANION` (and `TELEGRAM_TO_COMPANION_MESSAGE` if Telegram is used)

- **Input:** Text message transmitted across the external transport from both authorized and unauthorized accounts.
- **Execution Environment:** Local sidecar configured with valid transport credentials and explicit sender allow-list, bridging into the proven POC-001 local delivery pipeline.
- **Observable Output:** Authorized messages produce a validated `MessageEnvelope`, pass allow-list inspection, and trigger in-game companion delivery.
- **Rejection / Error Cases:**
  - Messages from unauthorized/unauthenticated accounts are rejected with observable security log.
  - Messages with forged sender metadata or invalid payload structure are dropped fail-closed.
  - Network disconnection or transport failure enters an observable degraded state without crashing the local sidecar or Skyrim bridge.
- **Evidence Artifact:** Sidecar audit log documenting ingress timestamp, sender normalization, authentication pass/fail decision, deduplication check, and local queue staging.
- **Authorization Criteria (PASS):** 100% of allow-listed test messages are delivered to companion; 0% of unauthorized or forged messages reach the local delivery queue; zero credentials exposed in logs.

### POC-003 — Optional reply

Investigate a deliberately narrow reply surface from Skyrim back to the authorized sender.

Examples may include explicit fixed responses such as:

- “Ya voy.”
- “Dame cinco minutos.”
- “Recibido.”

Do not permit arbitrary execution or reinterpret a reply as a command.

**Reproducible Evaluation Gate:**

`COMPANION_REPLY_TO_EXTERNAL_SENDER`

- **Input:** Player activates a pre-configured fixed response dialogue topic with the companion NPC in Skyrim.
- **Execution Environment:** Running Skyrim session with active messenger companion, connected to the local sidecar outbound transport.
- **Observable Output:** An outbound notification containing the selected canned text and the originating `correlation_id` is dispatched to the authorized external sender.
- **Rejection / Error Cases:** Uncorrelated replies or replies triggered when transport is offline fail gracefully without blocking the player's dialogue menu or freezing the game.
- **Evidence Artifact:** External transport dispatch log verifying recipient identity, `correlation_id` match to original message, and canned payload content.
- **Authorization Criteria (PASS):** Originating sender receives expected canned response; no arbitrary freeform text or executable commands can be injected via the reply mechanism.

## 10. Runtime questions that remain open

Before production implementation, independently determine:

- how the Python sidecar signals Skyrim (e.g. file polling, local named pipe, local socket, or Papyrus polling);
- whether SKSE is strictly necessary or whether a vanilla/Papyrus bridge is viable;
- how a controlled Topic/INFO should be triggered dynamically;
- whether Skyrim caches companion voice assets;
- whether multiple rotating dialogue slots are necessary;
- whether message delivery can safely wait until combat, dialogue, or cutscenes end;
- what happens when multiple messages arrive concurrently (queue overflow and ordering);
- whether subtitles and generated speech can remain synchronized in real time;
- message queue retention policy and restart behavior (handling un-delivered messages on crash or reload).

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

This document completes the **DESIGN and INVESTIGATION boundary**, not the runtime implementation contract.

It is considered complete when it defines architectural constraints, security invariants, delivery semantics, and reproducible evaluation gates without claiming that the underlying runtime mechanics are already solved.

Specifically, POC-001 is responsible for investigating, proving, and documenting the minimal local bridge contract (transport mechanism, signaling, dialogue triggering, timeout, and restart behavior) before any external network ingress or production implementation is attempted.

A future implementation agent MUST NOT assume:

- Telegram or any external transport is already integrated;
- runtime dynamic audio reload is proven;
- SKSE is definitely required;
- arbitrary NPC interception is required;
- external messages may execute commands;
- the runtime bridge implementation is already specified.
