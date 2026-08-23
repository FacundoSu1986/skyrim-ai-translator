# Convenciones de código — Skyrim AI Translation Agent

Punto de entrada para agentes: [`AGENTS.md`](../AGENTS.md). Este archivo detalla
invariantes y patrones técnicos; la precedencia documental se define en
[`docs/documentation/source_of_truth.md`](../docs/documentation/source_of_truth.md).

Stack: **Python 3.10+**, **FastAPI**, **React 19 + Vite**, **Edge-TTS**,
**Dynamic String Distributor (DSD)** e integración con **Mod Organizer 2**.

## 1. Jerarquía de prioridad

| Prioridad | Dominio | Ejemplos |
|---|---|---|
| **P0** | Seguridad y secretos | API keys, path traversal, egress, datos de usuario |
| **P1** | Integridad de datos y lore | glosario único, identidad de records/voz, exports |
| **P2** | Correctitud async/SRE | event loop, límites de concurrencia, timeouts |
| **P3** | Tests y contratos | pytest, anclas estructurales, hermeticidad |
| **P4** | Mantenibilidad | typing, separación de responsabilidades, frontend |

## 2. Backend Python / FastAPI

### 2.1 Concurrencia

- Prohibido `time.sleep()` dentro de `async def`; usar `asyncio.sleep()`.
- I/O bloqueante inevitable se ejecuta con `asyncio.to_thread`.
- Llamadas externas y TTS deben tener límites explícitos de concurrencia cuando
  puedan multiplicarse por entrada.
- No introducir paralelismo ilimitado mediante `asyncio.gather` sobre entradas
  no acotadas sin un semáforo o mecanismo equivalente.

**Gate:** `tests/test_architecture_invariants.py` enumera código productivo y
falla si aparece `time.sleep()` en contexto async.

### 2.2 Traducción y glosario

- `SKYRIM_GLOSSARY` de `src/translator.py` es la única fuente de verdad de lore
  localizada mantenida por el proyecto.
- `src/free_translator.py` consume ese símbolo por import; no mantiene una copia.
- Ambos pipelines deben conservar placeholders/formato y respetar el idioma
  objetivo. Una corrección en uno obliga a revisar el hermano.
- No agregar términos que requieran flexión contextual como si fueran nombres
  canónicos invariantes.

**Gate:** ancla AST de dueño único del glosario.

### 2.3 Modelos y transformaciones

- `StringEntry` es mutable a nivel de Python. La regla real es que los pipelines
  de transformación no muten las instancias recibidas.
- `translate_entries` crea el resultado con `dataclasses.replace`.
- Cambiar campos de `StringEntry` obliga a revisar parser/ESP, DSD, TTS, API,
  CLI y tests que serialicen o consuman esos campos.

**Gate:** el AST de `translate_entries` no permite stores directos sobre
`entry.<atributo>` y exige el reemplazo de `translated_text`.

### 2.4 Red, privacidad y secretos

- Toda nueva salida de red requiere revisión explícita de destino, timeout,
  credenciales, sanitización de errores, términos del proveedor y estrategia de
  test.
- API keys, tokens y headers de autorización no se loguean.
- No devolver excepciones crudas si pueden contener URLs con query strings,
  credenciales o payloads sensibles.
- Los tests son default-deny para red externa. Tests de integración real:
  `@pytest.mark.network` + opt-in `RUN_NETWORK_TESTS=1`.

**Gate:** el inventario de llamadas productivas directas a
`urllib.request.urlopen` se congela por módulo y cantidad.

### 2.5 Rutas y filesystem

- Normalizar con `Path.resolve()` antes de autorizar un destino.
- La autorización debe comprobar pertenencia semántica al root permitido; no
  usar `str(path).startswith(str(root))`.
- Crear directorios solo debajo de roots ya validados.
- Una operación de escritura/copia sobre MO2 debe fallar cerrada ante un path
  ambiguo o fuera del root.

## 3. Frontend React / Vite

- Componentes bajo `frontend/src/`; evitar lógica de dominio duplicada respecto
  del backend.
- Cerrar WebSockets al desmontar/reiniciar flujos.
- Mantener accesibilidad semántica y `aria-*` cuando aplique.
- Cambios frontend deben pasar `npm run lint` y `npm run build`.

## 4. Testing

- Pytest; tests con estructura AAA.
- Preferir propiedades/inventarios completos frente a un caso manual cuando el
  riesgo es “apareció un nuevo camino”.
- Un ancla AST debe incluir tests del propio detector para aliases o formas
  equivalentes relevantes.
- Tests de estado global (`jobs`) deben restaurar/limpiar estado.
- No depender de servicios externos para una suite unitaria verde.

## 5. Documentación y drift

El orden para describir el runtime es:

1. código ejecutable actual + tests relevantes;
2. decisiones arquitectónicas vigentes explícitas;
3. referencia técnica verificada;
4. guías de desarrollo/usuario;
5. reportes, spikes, specs y comentarios históricos.

Si una guía contradice runtime, registrar `DOCUMENTATION_DRIFT`, trazar callers y
corregir la documentación una vez demostrado el contrato. No cambiar producción
para satisfacer texto obsoleto.

## 6. CI actual

`.github/workflows/ci.yml` ejecuta:

- backend: Python 3.11 + `pytest --verbose`;
- frontend: Node 22 + `npm ci`, `npm run lint`, `npm run build`.

Las acciones de GitHub deben permanecer ancladas a SHA inmutable.
