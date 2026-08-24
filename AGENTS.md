# AGENTS.md — guía canónica para agentes

Fuente canónica de instrucciones para agentes de desarrollo y revisión en
`skyrim-ai-translator`. Las convenciones detalladas viven en
[.github/coding_conventions.md](.github/coding_conventions.md).

Para descubrir documentación por audiencia y resolver contradicciones, leer
[docs/README.md](docs/README.md) y
[docs/documentation/source_of_truth.md](docs/documentation/source_of_truth.md).
Los documentos de `docs/reports/`, spikes y specs son evidencia o intención; no
reemplazan el comportamiento del código y tests actuales.

## Dominio

Localización de mods de Skyrim SE/AE: extracción binaria de plugins `.esp`/`.esm`,
ingesta de volcados JSON, traducción contextual con glosario de lore, staging de
voz neural, exportación oficial DSD e integración con Mod Organizer 2.

### Componentes Principales y Límites de Alcance:
1. **Parser de Skyrim (`src/parser.py` y `src/esp_parser.py`)**:
   - `src/parser.py`: Ingesta y validación de esquemas JSON con volcados de cadenas estructuradas (`StringEntry`).
   - `src/esp_parser.py`: Extracción binaria directa de registros translatables implementados (`INFO` para respuestas de diálogo con resolución de actores y temas, `QUST` para nombres y objetivos de misiones, además de `DIAL`, `BOOK`, `MESG`, `NPC_`, `WEAP`, `ARMO`, `SPEL`, `ACTI`, `ALCH`, `PERK`, `MGEF`, `FACT`, `RACE`, `MISC`, `FLOR`, `LCTN`) desde plugins `.esp`/`.esm`. Travesía de maestros en modo sólo lectura vía `MasterResolver` (`INFO.ANAM` -> `NPC_.VTCK/TPLT` -> `VTYP.EDID`).
   - *Limitaciones*: Parseo directo de tablas binarias `.strings`, `.dlstrings`, `.ilstrings` no soportado aún (plugins con `FLAG_LOCALIZED` se omiten para evitar interpretar StringIDs como texto). Referencias FormID de plugins ligeros ESL (`0xFE`) no soportadas aún.
2. **Motor de Traducción Contextual (`src/translator.py` y `src/free_translator.py`)**:
   - **Glosario Único de Lore**: `SKYRIM_GLOSSARY` es la **única fuente de verdad** para nombres propios, ciudades, facciones y lugares canónicos en español.
   - **Doble Pipeline Coherente**:
     - *Camino Gratuito (`free_translator.py`)*: Traducción neuronal con protección estricta de placeholders contra el glosario.
     - *Camino LLM (`translator.py`)*: Inyección dinámica de `SKYRIM_GLOSSARY` en el system prompt para APIs compatibles con OpenAI (OpenAI, DeepSeek, Ollama, Groq).
3. **Pipeline de Voz y Voice Assets (`src/tts_generator.py`, `src/voice_mapper.py`, `src/voice_assets.py`)**:
   - `src/voice_mapper.py`: Mapeo heurístico y por tabla de Skyrim `VoiceType` (`MaleNord`, `FemaleCommander`, etc.) a voces de Edge-TTS.
   - `src/tts_generator.py`: Generación asíncrona de archivos `.mp3` estructurados para staging en `Sound/Voice/[plugin]/[voice_type]/`.
   - `src/voice_assets.py` (Spike / Prueba Estructural): Lógica pura para nombres base deterministas según Creation Kit (`<Quest>_<Topic>_<fid8>_<response>`), rutas relativas seguras contra *path traversal* en Windows, y empaquetado/desempaquetado de contenedores `.fuz` (`FUZE` v1 con LIP y audio payload). *Prueba estructural condicionada a VoiceType resuelto; transcodificación a LIP/XWM in-game requiere herramientas externas propietarias fuera de runtime.*
4. **Exportador a Dynamic String Distributor (`src/dsd_exporter.py`)**:
   - Generación de diccionarios JSON para *Dynamic String Distributor (DSD) 1.4.3* de SKSE (`0x<LOCAL_ID>|<DefiningPlugin>`, tipos soportados, índice obligatorio para `INFO NAM1` y `QUST NNAM`).
   - Validación contractual fail-fast preflight y durante export; no se fabrica metadata para entradas JSON legadas sin origen de plugin.
5. **Backend API, WebSockets y MO2 (`api.py`)**:
   - Servidor FastAPI ejecutado con `uvicorn api:app --port 8000`.
   - WebSockets para streaming de logs y progreso en tiempo real.
   - Ciclo de vida de `jobs` (`pending`, `processing`, `completed`, `error`).
   - Endpoint `/api/health` reportando métricas del sistema y `active_jobs` (exclusivamente `pending` y `processing`).
   - Auto-detección de rutas MO2, escaneo de mods e inyección directa protegida por `asyncio.Lock` y sanitización estricta de nombres de archivo contra *path traversal*.
6. **Arnés de Demostración Interno (`main.py`)**:
   - Demo asíncrona interna para desarrollo y verificación de los pasos del pipeline; no es un CLI para usuarios finales.
7. **Frontend Web (`frontend/`)**:
   - SPA moderna en React 19 + Vite.

## Flujo de trabajo

- Una rama + un PR por cambio. No commitear directo a `main`.
- Antes de modificar una superficie, trazar sus callers y sus superficies
  hermanas.
- Backend:
  - instalar: `pip install -r requirements.txt`
  - tests: `pytest --verbose`
- Frontend:
  - instalar: `cd frontend && npm ci`
  - lint: `npm run lint`
  - build: `npm run build`
- Los tests nuevos deben ser herméticos. La suite bloquea red saliente por
  defecto; una integración de red real debe marcarse `@pytest.mark.network` y
  habilitarse explícitamente con `RUN_NETWORK_TESTS=1`.

## Regla estructural: enumerar, no muestrear

Una regla crítica escrita solo en documentación se degrada. Cuando un invariante
pueda descubrirse estáticamente, preferir un **ancla que enumere la superficie
completa** y compare por igualdad exacta. Agregar un nuevo camino debe romper CI
hasta que se decida si participa del contrato o es una exención deliberada.

Ejemplos vigentes en `tests/test_architecture_invariants.py`:

- dueño único de `SKYRIM_GLOSSARY`;
- inventario exacto de egress HTTP directo vía `urllib.request.urlopen`;
- ausencia de `time.sleep()` dentro de código `async`;
- `translate_entries` no muta `StringEntry` in-place y crea el resultado con
  `dataclasses.replace`.

El detector debe probarse contra aliases/imports razonables. Un ancla que solo
reconoce la grafía usada hoy produce una falsa sensación de cobertura.

## Superficies hermanas que deben revisarse juntas

1. **Traducción:** `src/translator.py` y `src/free_translator.py` comparten
   invariantes de lore, placeholders, idioma objetivo, concurrencia y manejo de
   errores.
2. **Entrada Skyrim:** `src/parser.py` y `src/esp_parser.py` producen
   `StringEntry`; un cambio de metadatos debe seguir siendo consumible por DSD,
   TTS y API.
3. **Voz:** `src/voice_mapper.py`, `src/tts_generator.py` y
   `src/voice_assets.py` forman una cadena. Cambiar identidad, naming o
   resolución de voz exige revisar las tres.
4. **API/CLI:** `api.py` y `main.py` son dos superficies de entrada al mismo
   motor. No asumir que cubrir una cubre la otra.

## Contratos vigentes

### Glosario de lore

`SKYRIM_GLOSSARY` se define únicamente en `src/translator.py`. Otros pipelines
lo importan. No crear una segunda tabla de traducciones canónicas.

### Transformación de `StringEntry`

`StringEntry` no es un dataclass `frozen`; la inmutabilidad es un **contrato del
pipeline**, no una garantía del runtime. Las transformaciones de traducción no
mutan la entrada: producen una nueva instancia con `dataclasses.replace`.

### Async

No bloquear el event loop. `time.sleep()` está prohibido dentro de `async def`.
I/O síncrono inevitable debe salir del loop con `asyncio.to_thread`; concurrencia
hacia servicios externos debe estar acotada.

### Red y secretos

Toda nueva salida de red es una nueva superficie de seguridad y privacidad:
revisar destino, credenciales, logs, timeout, manejo de errores, términos del
proveedor y aislamiento de tests. El inventario de `urllib.request.urlopen`
está congelado por AST; no actualizarlo mecánicamente para poner CI en verde.

API keys y tokens no se escriben en logs ni respuestas de error.

### Rutas y archivos

Toda ruta de usuario/MO2 se resuelve con `pathlib.Path` y se valida contra el
destino permitido antes de leer, copiar o escribir. No confiar en strings de
ruta ni en prefijos textuales.

## Antes de cambiar arquitectura o documentación

Leer [docs/development/README.md](docs/development/README.md). Si documentación
y runtime contradicen, aplicar
[docs/documentation/source_of_truth.md](docs/documentation/source_of_truth.md):
no modificar producción solo para hacerla coincidir con un README, reporte,
spec o comentario histórico.
