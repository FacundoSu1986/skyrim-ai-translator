# Legal and Technical Compliance Review

**Document Version**: 1.0.0  
**Target Repository**: `skyrim-ai-translator`  
**License**: MIT License  
**Scope**: Dependencies, External Interoperation, Audio Toolchains, and Cloud Endpoints

---

## 1. Executive Summary & Compliance Classification Matrix

This document provides a structured compliance review of software licenses, external interoperability mechanisms, proprietary toolchain dependencies, and cloud service endpoints across the **Skyrim AI Translator** architecture.

### 1.1 Rating Taxonomy

To maintain factual precision and avoid dogmatic or absolute legal assertions, findings are categorized using the following standardized ratings:

- **`VERIFIED`**: Confirmed by direct examination of upstream license text, architectural boundaries, or explicit open-source terms.
- **`PLAUSIBLE`**: Supported by mainstream software engineering practices and standard copyright/licensing interpretations, though lacking formal judicial precedent.
- **`NOT VERIFIED`**: Insufficient factual or architectural evidence to make a definitive assessment.
- **`CONTRACTUAL RISK`**: Potential exposure under third-party terms of service (ToS), API fair-use policies, or non-commercial usage restrictions.
- **`LICENSE RISK`**: Potential ambiguity or incompatibility regarding software copyleft, redistribution, or relicensing conditions.
- **`REQUIRES LEGAL REVIEW`**: Matters involving jurisdiction-specific intellectual property, EULA enforcement, or proprietary cloud service integration requiring professional legal counsel.

### 1.2 Summary Matrix

| Component / Subsystem | Category | Primary License / Basis | Compliance Rating | Key Architectural & Legal Assessment |
|---|---|---|---|---|
| **Python Core (FastAPI, Pydantic, Uvicorn, Websockets, HTTPX, etc.)** | Distributed Runtime | MIT / BSD 3-Clause / Apache 2.0 | **`VERIFIED`** | Permissive open-source licenses; compatible with top-level MIT license; standard attribution provided. |
| **Frontend SPA (React, Vite, Lucide-React)** | Distributed Runtime | MIT / ISC | **`VERIFIED`** | Permissive open-source licenses; clean client-side separation; standard attribution provided. |
| **`edge-tts` (Python Library)** | Distributed Runtime | LGPL-3.0-or-later | **`VERIFIED`** | Clean module boundary; dynamically imported via standard Python package management; allows user replacement. |
| **Microsoft Read Aloud Endpoint (used by `edge-tts`)** | Cloud Service | Microsoft Services Agreement / Edge ToS | **`CONTRACTUAL RISK`** / **`REQUIRES LEGAL REVIEW`** | Source license is open; underlying WebSocket endpoint is undocumented/non-SLA. High traffic may risk throttling or ToS challenge. |
| **Google Translate Web Endpoint (`client=gtx`)** | Cloud Service | Google Terms of Service | **`CONTRACTUAL RISK`** / **`REQUIRES LEGAL REVIEW`** | Free web translator lacks commercial SLA; subject to IP rate limits and ToS considerations under Google developer policies. |
| **LLM Cloud APIs (OpenAI, DeepSeek, Groq, etc.)** | Cloud Service | Commercial Developer API Agreements | **`VERIFIED`** / **`PLAUSIBLE`** | Standard authorized API usage with user-supplied API keys and provider-specific terms. |
| **Dynamic String Distributor (DSD) Interoperation** | External Tool | GNU GPL-3.0 | **`VERIFIED`** | Loose coupling via standard JSON export; no compiled code linkage; does not trigger GPL copyleft contamination. |
| **Mod Organizer 2 (MO2) Interoperation** | External Tool | GNU GPL-3.0 | **`VERIFIED`** | Filesystem inspection and directory injection across OS boundaries; independent process execution; no copyleft contagion. |
| **Creation Kit & Audio Tools (`CreationKit.exe`, `LipGenerator.exe`, `FonixData.cdf`, `xwmaencode.exe`)** | Proprietary Toolchain | Bethesda EULA / Fonix / Microsoft SDK | **`VERIFIED`** (Repo Architecture) / **`REQUIRES LEGAL REVIEW`** (User Runtime) | Strictly user-installed and locally discovered; zero bundling or redistribution; execution on host is user's responsibility. |

---

## 2. Distinction: Source Code Licenses vs. Cloud Service Authorization

A critical compliance principle applied in this review is the distinction between **software copyright licenses** (which govern code distribution, compilation, and modification) and **cloud service authorizations** (which govern access to remote servers, APIs, and online endpoints).

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        COMPLIANCE BOUNDARY                             │
├───────────────────────────────────┬────────────────────────────────────┤
│       SOURCE CODE LICENSE         │     CLOUD SERVICE AUTHORIZATION    │
│  (Copyright / Code Distribution)  │      (Terms of Service / SLAs)     │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Governed by open-source license │ • Governed by service terms & EULAs│
│ • Grants rights to run, inspect,  │ • Governs remote network access,   │
│   modify, and redistribute code   │   server load, authentication, SLA │
│ • Example: edge-tts (LGPL-3.0)    │ • Example: MS Read Aloud endpoint  │
│   -> Code is verified FOSS        │   -> Remote endpoint ToS risk      │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 2.1 Edge-TTS and Microsoft Speech Services

- **Source Code License Rating**: **`VERIFIED`**
  - The `edge-tts` client library is authored by Rany (`@rany2`) and licensed under the GNU Lesser General Public License v3.0 (`LGPL-3.0-or-later`).
  - Skyrim AI Translator interacts with `edge-tts` exclusively through public Python module imports (`import edge_tts`).
  - No static linking occurs; the library is isolated within the user's Python virtual environment. Users retain full rights to update or replace the library as guaranteed by LGPL-3.0 Section 4.

- **Cloud Endpoint Authorization Rating**: **`CONTRACTUAL RISK`** / **`REQUIRES LEGAL REVIEW`**
  - `edge-tts` communicates with Microsoft's speech synthesis endpoints originally provisioned for Microsoft Edge browser features (e.g. Read Aloud).
  - While public and unauthenticated with traditional API keys, this endpoint does not carry a formal commercial Service Level Agreement (SLA) or explicit third-party developer grant from Microsoft Corporation.
  - *Risk Assessment*: Microsoft could introduce protocol changes, captcha validation, IP-based rate limiting, or assert terms-of-service restrictions against excessive non-browser automated usage. The project mitigates this by providing modular abstractions (`tts_class` parameter injection) enabling drop-in replacement with official Azure Speech SDK or local TTS engines.

### 2.2 Google GTX Translation Endpoint (`free_translator.py`)

- **Source Code Implementation Rating**: **`VERIFIED`**
  - The HTTP orchestration logic in `src/free_translator.py` is original MIT-licensed code developed for this repository.

- **Cloud Service Authorization Rating**: **`CONTRACTUAL RISK`** / **`REQUIRES LEGAL REVIEW`**
  - The endpoint `https://translate.googleapis.com/translate_a/single?client=gtx` is an undocumented public endpoint historically utilized by browser extensions.
  - It is not an officially provisioned Google Cloud Translation API subscription.
  - *Risk Assessment*: Users relying on this mode may encounter HTTP 429 (Too Many Requests), temporary IP blocks, or service discontinuation by Google. The project makes this mode optional and provides authenticated LLM translation providers (OpenAI, DeepSeek, local Ollama) as supported alternatives.

---

## 3. Copyleft Boundary Analysis: DSD and MO2 Interoperation

The repository interacts with two major GPL-3.0 licensed community tools: **Dynamic String Distributor (DSD)** and **Mod Organizer 2 (MO2)**.

### 3.1 Dynamic String Distributor (DSD 1.4.3)

- **Interaction Mechanism**: File-format JSON serialization (`src/dsd_exporter.py`).
- **Data Exchange**: The exporter generates standalone JSON files conforming to the public specification:
  ```json
  [
    {
      "form_id": "0x000136C9|Skyrim.esm",
      "type": "INFO NAM1",
      "index": 1,
      "string": "Texto traducido"
    }
  ]
  ```
- **Legal Assessment**: **`VERIFIED`** (No Copyleft Contamination)
  - Under Section 0 and Section 5 of the GNU General Public License v3.0, generating data in a format consumed by a GPL program does not make the generator a derivative work of the consumer.
  - Skyrim AI Translator does not compile against DSD headers (`.h`/`.hpp`), does not dynamically load DSD DLLs (`.dll`), and does not share address-space memory with DSD.
  - Standard industry interpretation and Free Software Foundation (FSF) licensing principles establish that outputting standard data formats (such as JSON) maintains complete licensing independence.

### 3.2 Mod Organizer 2 (MO2)

- **Interaction Mechanism**: Filesystem discovery and file placement (`Sound/Voice/`, DSD JSON).
- **Data Exchange**: The backend identifies MO2 installation directories through standard filesystem scanning and places output assets into the appropriate mod folder.
- **Legal Assessment**: **`VERIFIED`** (No Copyleft Contamination)
  - Interacting with an application via the operating system's filesystem hierarchy is an external inter-process boundary.
  - No code from MO2 is copied, embedded, statically linked, or dynamically linked into Skyrim AI Translator.
  - Therefore, the GPL-3.0 license of MO2 does not extend to or contaminate the MIT license of Skyrim AI Translator.

---

## 4. Proprietary Audio Toolchain and User-Installed Assets

Generating fully functional voice assets for Skyrim (`.fuz` containers with synchronized lip animations) requires specialized proprietary binaries.

### 4.1 The 5-Point Contract

Skyrim AI Translator implements an explicit, non-negotiable architectural contract regarding all proprietary external utilities:

```text
┌────────────────────────────────────────────────────────────────────────┐
│               PROPRIETARY ASSET INTEGRATION CONTRACT                   │
├──────────────────────┬─────────────────────────────────────────────────┤
│ 1. USER_INSTALLED    │ Acquired and installed solely by the user.       │
│ 2. LOCALLY_DISCOVERED│ Dynamically located on the host machine.        │
│ 3. EXECUTED LOCALLY  │ Executed as external OS subprocesses.           │
│ 4. NEVER BUNDLED     │ Zero bundling in git repository or releases.   │
│ 5. NEVER REDISTRIBUTED Zero redistribution of vendor binaries or data. │
└──────────────────────┴─────────────────────────────────────────────────┘
```

### 4.2 Detailed Component Assessment

| Binary / Asset | Origin / Rights Holder | Architectural Handling | Compliance Rating |
|---|---|---|---|
| **`CreationKit.exe`** | Bethesda Softworks / ZeniMax Media | Not bundled. Discovered in user's game/CK installation directory. | **`VERIFIED`** |
| **`LipGenerator.exe`** | Bethesda Softworks / Fonix Corporation | Not bundled. Invoked as standalone child process for `.lip` generation. | **`VERIFIED`** |
| **`FonixData.cdf`** | Fonix Corporation / Innoetics | Not bundled. Proprietary acoustic model data loaded by `LipGenerator.exe`. | **`VERIFIED`** |
| **`xwmaencode.exe`** | Microsoft Corporation (DirectX SDK) | Not bundled. Discovered locally for xWMA audio compression. | **`VERIFIED`** |
| **`LIPFuzer.exe`** | Community Freeware | Not bundled. Clean-room alternative implemented in `src/voice_assets.py`. | **`VERIFIED`** |

### 4.3 Clean-Room Implementation of `.fuz` Container

To minimize dependency on legacy external fuzing tools, the repository includes a clean-room implementation of the `.fuz` container in `src/voice_assets.py` (`pack_fuz` / `unpack_fuz`):
- Operates strictly on container byte specifications (`b"FUZE"` header, 32-bit integer offsets).
- Does not decompile, reverse-engineer, or incorporate proprietary code.
- Verified hermetically through unit tests (`tests/test_voice_assets.py`).

---

## 5. Dependency Management: `edge-tts` 7.x Policy

### 5.1 Version Pinning Rationale

In `requirements.txt`, the `edge-tts` dependency is pinned as:
```text
edge-tts>=7.0.0,<8.0.0
```

### 5.2 Technical and Licensing Evaluation

1. **API Stability**: The 7.x series of `edge-tts` introduces modernized asynchronous streaming primitives, enhanced error categorization, and updated voice metadata endpoints compatible with recent upstream service changes.
2. **Major Version Boundary**: The `<8.0.0` upper bound protects against breaking changes in future major releases while allowing security and bugfix updates in the 7.x line.
3. **LGPL Compliance**: Version 7.x maintains the LGPL-3.0-or-later license, preserving complete compatibility with the project's dependency architecture.

---

## 6. Recommendations and Risk Mitigation Strategy

To maintain exemplary compliance posture, the following practices are recommended:

1. **Maintain Clean-Room Boundaries**: Continue isolating external tool invocations behind subprocess wrappers and standard filesystem inputs/outputs.
2. **Preserve User Choice in Cloud Services**: Offer offline/local alternatives (e.g. local LLMs via Ollama, local TTS engines via Piper/Coqui) alongside cloud-backed endpoints.
3. **Continuous Dependency Audits**: Maintain automated dependency scanning in CI pipelines to monitor upstream license changes and CVE advisories.
4. **Transparent User Documentation**: Clearly communicate in user-facing guides that game data files, Creation Kit utilities, and third-party mod assets are subject to their respective creators' licenses and terms.

---

## 7. Legal Disclaimer

*The information contained in this document is provided for technical documentation and compliance tracking purposes only and does not constitute formal legal advice. Software licenses and terms of service are subject to change by their respective rights holders. Maintainers and contributors should consult qualified legal counsel for binding legal assessments.*
