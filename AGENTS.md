# AGENTS.md — Guía de Arquitectura e Invariantes para Agentes

Fuente canónica de contexto técnico e invariantes para agentes de desarrollo y revisores de código en este repositorio (`skyrim-ai-translator`).
El detalle de convenciones y buenas prácticas se encuentra en [.github/coding_conventions.md](.github/coding_conventions.md).

---

## 🏛️ Dominio y Arquitectura

Sistema integral para la **localización, traducción contextual y síntesis de voz (TTS)** de mods para **The Elder Scrolls V: Skyrim (SE / AE)**.

### Componentes Principales:
1. **Parser Universal de Skyrim (`src/parser.py` y `src/esp_parser.py`)**:
   - Lectura de tablas de localización `.strings`, `.dlstrings`, `.ilstrings`.
   - Extracción binaria de registros `INFO` (diálogos) y `QUST` (misiones) directamente desde plugins `.esp`.
2. **Motor de Traducción Contextual (`src/translator.py` y `src/free_translator.py`)**:
   - **Glosario Único de Lore**: `SKYRIM_GLOSSARY` es la **única fuente de verdad** para nombres propios, ciudades, facciones y lugares canónicos en español.
   - **Doble Pipeline Coherente**:
     - *Camino Gratuito (`free_translator.py`)*: Traducción neuronal con protección estricta de placeholders contra el glosario.
     - *Camino LLM (`translator.py`)*: Inyección dinámica de `SKYRIM_GLOSSARY` en el system prompt para APIs compatibles con OpenAI (OpenAI, DeepSeek, Ollama, Groq).
3. **Generador de Voces Neuronales (`src/tts_generator.py` y `src/voice_mapper.py`)**:
   - Mapeo heurístico y por tabla de Skyrim `VoiceType` (`MaleNord`, `FemaleCommander`, etc.) a voces de Edge-TTS.
   - Generación asíncrona de archivos `.mp3` estructurados en `sound/voice/[plugin.esp]/[voice_type]/`.
4. **Exportador y Distribución (`src/dsd_exporter.py`)**:
   - Generación de JSONs para *Dynamic String Distributor (DSD)* de SKSE.
5. **Backend API y WebSockets (`api.py`)**:
   - Servidor FastAPI con WebSockets para streaming de logs y progreso.
   - Ciclo de vida de `jobs` (`pending`, `processing`, `completed`, `failed`).
   - Endpoint `/api/health` reportando métricas del sistema y `active_jobs` (exclusivamente `pending` y `processing`).
6. **Frontend Web (`frontend/`)**:
   - SPA moderna en React 19 + Vite.

---

## 🛡️ Invariantes Críticas

1. **Glosario Centralizado**: Nunca hardcodear una segunda copia de traducciones de lore. Todo cambio o nuevo término debe agregarse a `SKYRIM_GLOSSARY` en `src/translator.py`.
2. **Inmutabilidad en Modelos**: `StringEntry` (`src/models.py`) debe tratarse como inmutable. Funciones de transformación como `translate_entries` nunca mutan in-place; retornan nuevas instancias con `dataclasses.replace`.
3. **Concurrencia Asíncrona**: Prohibido bloquear el event loop de FastAPI con llamadas I/O síncronas. Usar `asyncio.to_thread` o semáforos controlados (`concurrency_limit`).
4. **Seguridad y Secretos**:
   - Las API keys nunca se loguean ni se devuelven en payloads de error.
   - Sanitizar siempre rutas de archivos de Mod Organizer 2 para prevenir Path Traversal al inyectar o leer archivos.
5. **Calidad y Tests**:
   - Toda nueva funcionalidad o corrección debe incluir pruebas unitarias en `pytest` siguiendo el patrón Arrange-Act-Assert (AAA).
