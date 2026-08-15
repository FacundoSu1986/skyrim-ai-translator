# Convenciones de Código — Skyrim AI Translation Agent

Fuente detallada de convenciones técnicas e invariantes para el repositorio **skyrim-ai-translator**.

Stack: **Python 3.10+**, **FastAPI**, **React 19 + Vite**, **Edge-TTS**, **Dynamic String Distributor (DSD)**, integración con **Mod Organizer 2**.

---

## 1. Jerarquía de Prioridad

Si dos reglas o requerimientos colisionan, obedecer estrictamente este orden:

| Prioridad | Dominio | Ejemplos clave |
|-----------|---------|----------------|
| **P0** | Seguridad & Secretos | Protección de API keys, prevención de Path Traversal en MO2 / disco, sanitización de inputs. |
| **P1** | Integridad de Datos y Lore | Única fuente de verdad en `SKYRIM_GLOSSARY`, inmutabilidad de `StringEntry`. |
| **P2** | SRE & Concurrencia | No bloquear el event loop de FastAPI, semáforos en `translate_entries` y Edge-TTS. |
| **P3** | Calidad & Testing | Pruebas unitarias en `pytest` para todo cambio de backend, build exitoso en frontend. |
| **P4** | Mantenibilidad | Tipado explícito con `typing` / Pydantic, nombres descriptivos, código limpio sin duplicación. |

---

## 2. Invariantes del Backend (Python / FastAPI)

### 2.1 Concurrencia y Asyncio
- Todo I/O bloqueante (lectura de disco de archivos pesados, `urllib.request` síncrono, generación de archivos masivos) debe envolverse en `asyncio.to_thread`.
- Prohibido el uso de `time.sleep()` en corrutinas `async def`; usar siempre `asyncio.sleep()`.
- Controlar el paralelismo hacia servicios externos o síntesis de voz mediante `asyncio.Semaphore` explícitos.

### 2.2 Motor de Traducción y Glosario
- `SKYRIM_GLOSSARY` (`src/translator.py`) es la **única fuente de verdad** para nombres propios, ciudades, facciones y lugares de Skyrim.
- El pipeline gratuito (`free_translator.py`) y el pipeline de API LLM (`translator.py`) deben respetar este glosario de forma unificada y determinista.
- Evitar incorporar adjetivos aislados fijos al glosario directo si requieren flexión de género o número en español; reservar el glosario para términos canónicos y nombres propios.

### 2.3 Modelos y Tipado
- `StringEntry` (`src/models.py`) debe permanecer inmutable en transformaciones. Usar `dataclasses.replace` al generar una versión traducida.
- Modelos de petición en FastAPI deben definirse con `pydantic.BaseModel` con tipos estrictos y valores por defecto sensatos.

### 2.4 Seguridad y Manejo de Errores
- Las API keys (OpenAI / DeepSeek / etc.) se gestionan en memoria por solicitud o job y **nunca** se graban en logs, mensajes de WebSocket ni respuestas de error.
- Las rutas provistas por el usuario para Mod Organizer 2 o subida de archivos deben resolverse y validarse con `pathlib.Path` para evitar escapes de directorio.
- Devolver códigos de estado HTTP semánticos (404 para jobs inexistentes, 400 para payloads inválidos).

---

## 3. Invariantes del Frontend (React 19 + Vite)

- Estructura modular de componentes bajo `frontend/src/`.
- Uso de componentes accesibles con etiquetas semánticas y aria attributes donde aplique.
- Manejo limpio del ciclo de vida de WebSockets (cerrar conexiones activas al desmontar componentes o reiniciar jobs).

---

## 4. Testing y CI

- Suite de pruebas ejecutada con `pytest --verbose`.
- Tests estructurados siguiendo el patrón **AAA** (Arrange, Act, Assert).
- Los tests que verifiquen el estado global (`jobs` en `api.py`) deben limpiar o restaurar el estado para garantizar aislamiento entre pruebas.
- Acciones de GitHub Actions ancladas mediante su commit SHA inmutable.
