# Guía de desarrollo

Esta guía describe cómo modificar `skyrim-ai-translator` sin perder contratos
entre sus distintas superficies.

## Preparación

Backend:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# POSIX
source .venv/bin/activate

pip install -r requirements.txt
pytest --verbose
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

CI usa Python 3.11 para backend y Node 22 para frontend. El soporte declarado del
proyecto sigue siendo Python 3.10+; no asumir que una sintaxis más nueva está
permitida solo porque CI use 3.11.

## Mapa de cambio

| Si tocás | Revisá también | Riesgo principal |
|---|---|---|
| `src/translator.py` | `src/free_translator.py`, tests de traducción | drift de glosario/placeholders |
| `src/free_translator.py` | `src/translator.py`, egress/network tests | proveedor externo, coherencia entre pipelines |
| `src/models.py` | parsers, DSD, TTS, API/CLI | pérdida/interpretación de metadata |
| `src/parser.py` / `src/esp_parser.py` | DSD, voice assets, API | identidad de records |
| `src/voice_mapper.py` | `tts_generator.py`, `voice_assets.py` | naming/VoiceType incorrecto |
| `api.py` | `main.py`, tests de API/WebSocket | contrato divergente entre superficies |
| filesystem/MO2 | validación de paths + tests adversariales | escritura fuera del root |

La tabla es una guía de revisión, no un reemplazo de trazar callers reales.

## Anclas estructurales

`tests/test_architecture_invariants.py` contiene tests deliberadamente
“incómodos”: congelan superficies completas para que un nuevo camino obligue a
una decisión explícita.

### Glosario

Solo `src/translator.py` puede **definir** `SKYRIM_GLOSSARY`.
`free_translator.py` debe importarlo.

### Egress HTTP directo

Las llamadas productivas directas a `urllib.request.urlopen` se enumeran por
archivo y cantidad. Si aparece una nueva:

1. revisar por qué necesita red;
2. definir timeout y error handling;
3. comprobar que secretos/URLs sensibles no lleguen a logs;
4. añadir/mantener test hermético;
5. solo entonces actualizar el inventario AST.

No actualizar el dict esperado como trámite para poner CI en verde.

### Async

El árbol productivo no puede introducir `time.sleep()` dentro de `async def`.

### Transformación

`translate_entries` trata la entrada como value-like: no asigna
`entry.<campo> = ...`; genera el resultado con `dataclasses.replace`.

## Tests de red

La suite aplica default-deny a red saliente. Un test que realmente necesite una
integración externa debe:

```python
@pytest.mark.network
def test_integracion_real(): ...
```

y solo se ejecuta cuando `RUN_NETWORK_TESTS=1`.

Un unit test normal debe mockear el boundary externo.

## Documentación

Antes de corregir producción a partir de una afirmación documental, consultar
[`../documentation/source_of_truth.md`](../documentation/source_of_truth.md).
Si el texto quedó viejo, corregir el texto; no inventar un contrato nuevo.
