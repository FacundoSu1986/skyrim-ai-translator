# Fuentes de verdad y resolución de drift

> **Estado:** política vigente para interpretar documentación y runtime.
>
> **Alcance:** agentes, mantenedores y revisores.

## Precedencia de instrucciones para agentes

`AGENTS.md` es la fuente canónica de instrucciones del repositorio.
`.github/coding_conventions.md` detalla esas reglas. Configuraciones de bots,
comentarios de PR, reports o specs no sustituyen los invariantes declarados ahí.

## Precedencia para describir comportamiento

1. **Código ejecutable actual y tests que ejercitan el comportamiento.**
2. Decisiones arquitectónicas vigentes y explícitas.
3. Referencia técnica verificada.
4. Guías de desarrollo y README.
5. Reportes, spikes, specs, auditorías y conversaciones históricas.

Un test solo demuestra el comportamiento que realmente ejercita. Tampoco una
fecha o SHA en un documento convierte una afirmación no comprobada en verdad.

## Regla anti-drift para agentes

Si un README, reporte, spike, spec o comentario contradice código/tests actuales:

1. registrar la discrepancia como `DOCUMENTATION_DRIFT`;
2. trazar el caller productivo y las superficies hermanas;
3. usar código + tests como autoridad provisional de comportamiento;
4. determinar si existe una decisión arquitectónica explícita que cambie la
   interpretación;
5. corregir la documentación por separado cuando el contrato quede demostrado.

**No modificar producción únicamente para hacerla coincidir con documentación
derivada u obsoleta.**

## Mapa de fuentes principales

| Tema | Fuente principal |
|---|---|
| API y jobs/WebSocket | `api.py` + `tests/test_api.py` |
| CLI | `main.py` + `tests/test_main.py` |
| modelo de entrada | `src/models.py` |
| strings Skyrim | `src/parser.py` |
| plugins ESP | `src/esp_parser.py` |
| traducción LLM/glosario | `src/translator.py` |
| traducción gratuita | `src/free_translator.py` |
| DSD | `src/dsd_exporter.py` + tests DSD |
| TTS | `src/tts_generator.py` |
| identidad/assets de voz | `src/voice_assets.py`, `src/voice_mapper.py` + tests |
| invariantes estructurales | `tests/test_architecture_invariants.py` |
| aislamiento de red de tests | `tests/conftest.py`, `tests/test_network_isolation.py` |
| CI | `.github/workflows/ci.yml` |
| frontend | `frontend/src/` + scripts de `frontend/package.json` |

## Cuándo actualizar este documento

Solo cuando cambie la precedencia, el mapa de ownership o la política anti-drift.
No usarlo como changelog ni como inventario de features.
