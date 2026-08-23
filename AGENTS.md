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

Localización de mods de Skyrim SE/AE: parsing de `.strings`/`.dlstrings`/
`.ilstrings` y plugins, traducción contextual, TTS, exportación DSD e integración
con Mod Organizer 2.

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
