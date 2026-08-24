# Third-Party Notices and Open Source Software Inventory

This document contains licensing and copyright notices for third-party software components, libraries, external tools, and service integrations utilized by or interoperated with **Skyrim AI Translator**.

---

## Table of Contents

1. [Architectural Overview and Licensing Philosophy](#1-architectural-overview-and-licensing-philosophy)
2. [Category 1: Distributed Runtime & Build Dependencies](#2-category-1-distributed-runtime--build-dependencies)
   - [2.1 Backend Python Dependencies](#21-backend-python-dependencies)
   - [2.2 Frontend JavaScript / TypeScript Dependencies](#22-frontend-javascript--typescript-dependencies)
3. [Category 2: External Interoperated Tools](#3-category-2-external-interoperated-tools)
   - [3.1 Dynamic String Distributor (DSD)](#31-dynamic-string-distributor-dsd)
   - [3.2 Mod Organizer 2 (MO2)](#32-mod-organizer-2-mo2)
4. [Category 3: User-Installed Proprietary & External Audio Tools](#4-category-3-user-installed-proprietary--external-audio-tools)
   - [4.1 Explicit Contract Policy](#41-explicit-contract-policy)
   - [4.2 Toolchain Inventory](#42-toolchain-inventory)
5. [Category 4: Cloud Endpoints and Remote Services](#5-category-4-cloud-endpoints-and-remote-services)
6. [License Texts](#6-license-texts)
   - [MIT License](#mit-license)
   - [BSD 3-Clause License](#bsd-3-clause-license)
   - [Apache License 2.0](#apache-license-20)
   - [GNU Lesser General Public License v3.0 (LGPL-3.0)](#gnu-lesser-general-public-license-v30-lgpl-30)

---

## 1. Architectural Overview and Licensing Philosophy

**Skyrim AI Translator** is licensed under the [MIT License](LICENSE). The project maintains a strict clean-room boundary between:
- Its own MIT-licensed codebase.
- Permissive and copyleft runtime libraries consumed via package managers (PyPI, npm).
- Independent external applications communicating exclusively through loose file-based protocols (JSON, directory structures).
- Proprietary vendor-supplied binaries which are **never** bundled, redistributed, or shipped.

---

## 2. Category 1: Distributed Runtime & Build Dependencies

These components are distributed or fetched as standard package manager dependencies during build and runtime.

### 2.1 Backend Python Dependencies

| Package | Version Range | License | Author / Copyright Holder | Role / Usage |
|---|---|---|---|---|
| **FastAPI** | `>=0.110.0` | MIT | Sebastián Ramírez (`@tiangolo`) | High-performance async web framework for REST API and WebSocket orchestration. |
| **uvicorn** | `>=0.28.0` | BSD 3-Clause | Encode OSS Ltd. | ASGI web server hosting the FastAPI application. |
| **websockets** | `>=12.0` | BSD 3-Clause | Aymeric Augustin | Real-time bidirectional streaming communication for translation progress and event logs. |
| **python-multipart** | `>=0.0.9` | Apache-2.0 | Andrew Chen Wang | Streaming multipart/form-data parser for file upload handling in FastAPI. |
| **pydantic** | `>=2.6.0` | MIT | Samuel Colvin & Pydantic Contributors | Data parsing, schema validation, and typed domain settings. |
| **edge-tts** | `>=7.0.0,<8.0.0` | LGPL-3.0-or-later | Rany (`@rany2`) | Python client for text-to-speech generation via Microsoft Edge Speech service. Pinning `7.x` provides stable async streaming and voice listing APIs. |
| **httpx** | `>=0.27.0` | BSD 3-Clause | Encode OSS Ltd. | Async HTTP client for outbound network communication. |

### 2.2 Frontend JavaScript / TypeScript Dependencies

| Package | Version Range | License | Author / Copyright Holder | Role / Usage |
|---|---|---|---|---|
| **React** | `^19.2.8` | MIT | Meta Platforms, Inc. & React Contributors | Declarative UI library powering the frontend Single Page Application (SPA). |
| **react-dom** | `^19.2.8` | MIT | Meta Platforms, Inc. & React Contributors | DOM rendering bindings for React components. |
| **Vite** | `^8.2.0` | MIT | Evan You & Vite Contributors | Modern frontend build tooling, bundler, and development server. |

---

## 3. Category 2: External Interoperated Tools

The following tools are independent software projects distributed under copyleft or separate licenses. Skyrim AI Translator interoperates with these tools through loose, non-linking interfaces.

### 3.1 Dynamic String Distributor (DSD)
- **License**: GNU General Public License v3.0 (GPL-3.0)
- **Project URL**: [Dynamic String Distributor (Nexus Mods / SKSE plugin)](https://www.nexusmods.com/skyrimspecialedition/mods/100000)
- **Interoperability Mode**: Standard JSON Export
- **Licensing Boundary**: Skyrim AI Translator generates standalone JSON translation dictionaries conforming to DSD 1.4.3 specifications (`0x<LOCAL_ID>|<DefiningPlugin>`). Skyrim AI Translator does not link against DSD binaries, execute DSD code in-process, or embed DSD headers. File-level data exchange does not create a derivative work or trigger GPL-3.0 copyleft obligations on the translator's MIT codebase.

### 3.2 Mod Organizer 2 (MO2)
- **License**: GNU General Public License v3.0 (GPL-3.0)
- **Project URL**: [Mod Organizer 2 on GitHub](https://github.com/ModOrganizer2/modorganizer)
- **Interoperability Mode**: Filesystem Directory Inspection & Injection / Process Invocation
- **Licensing Boundary**: Skyrim AI Translator discovers local MO2 installation directories via standard filesystem paths and injects generated translation assets (`Sound/Voice/`, DSD JSON files) directly into designated mod directories. Interoperation occurs entirely across OS filesystem and subprocess boundaries. No dynamic/static linking or shared memory execution exists.

---

## 4. Category 3: User-Installed Proprietary & External Audio Tools

The Skyrim audio pipeline requires specialized tools for viseme generation and audio compression.

### 4.1 Explicit Contract Policy

All tools listed in this category adhere strictly to the following 5-point contract:

```text
1. USER_INSTALLED       -> The end user must obtain and install these tools independently.
2. LOCALLY_DISCOVERED   -> Discovered dynamically on host machine filesystem / registry.
3. EXECUTED LOCALLY     -> Executed as standalone external subprocesses on the user's host.
4. NEVER BUNDLED        -> NEVER included in the repository, releases, wheels, or packages.
5. NEVER REDISTRIBUTED  -> Zero redistribution of vendor or proprietary binaries.
```

### 4.2 Toolchain Inventory

| Tool / File | Copyright / Vendor | Proprietary Nature / License | Purpose |
|---|---|---|---|
| **`CreationKit.exe`** | Bethesda Softworks LLC / ZeniMax Media Inc. | Proprietary EULA | Official Skyrim Creation Kit editor for dialogue and asset compilation. |
| **`LipGenerator.exe`** | Bethesda Softworks LLC / Fonix Corporation | Proprietary Binary | Dialogue viseme generator executable invoked to produce `.lip` sync data. |
| **`LIPFuzer.exe`** | Third-party / Community Utility | Freeware / Community Tool | Legacy utility for fusing `.wav`/`.xwm` and `.lip` into `.fuz` archives. |
| **`xwmaencode.exe`** | Microsoft Corporation | Microsoft DirectX / Windows SDK EULA | Audio encoder converting uncompressed PCM `.wav` into compressed `.xwm` format. |
| **`FonixData.cdf`** | Fonix Corporation / Innoetics | Proprietary Acoustic Model Data | Phoneme/acoustic recognition model data required by `LipGenerator.exe`. |

---

## 5. Category 4: Cloud Endpoints and Remote Services

Skyrim AI Translator supports optional network-backed translation and voice services.

| Service / Endpoint | Service Provider | Interfacing Mechanism | Licensing & Terms Notice |
|---|---|---|---|
| **Microsoft Edge Speech (Read Aloud)** | Microsoft Corporation | `edge-tts` async WebSocket protocol | Consumed via the open-source `edge-tts` client. Uses Microsoft Edge public TTS endpoints. Subject to Microsoft's service policies. |
| **Google Translate Web Endpoint (`client=gtx`)** | Google LLC | HTTP GET via `free_translator.py` | Public neural translation endpoint used with glossary placeholder protection. Subject to Google Terms of Service and rate limits. |
| **OpenAI / DeepSeek / Compatible LLMs** | Respective API Providers | HTTP REST API / User API Key | Standard authenticated cloud API consumption governed by individual provider developer agreements. |

---

## 6. License Texts

### MIT License

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD 3-Clause License

```text
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Apache License 2.0

```text
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### GNU Lesser General Public License v3.0 (LGPL-3.0)

`edge-tts` is licensed under the GNU Lesser General Public License v3.0 (LGPL-3.0-or-later).
Under the terms of LGPL-3.0:
- The library is consumed as an unmodified, dynamically imported Python module.
- Users are entitled to inspect, modify, and replace the `edge-tts` component in their Python environment.
- Skyrim AI Translator does not restrict users from modifying or upgrading `edge-tts`.
- Complete source code of `edge-tts` is accessible at [https://github.com/rany2/edge-tts](https://github.com/rany2/edge-tts).
