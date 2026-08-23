# Documentación de skyrim-ai-translator

> **Estado:** portal de navegación documental.
>
> **Audiencia:** desarrolladores, revisores, agentes y mantenedores.
>
> **Política anti-drift:** [`documentation/source_of_truth.md`](documentation/source_of_truth.md).

## Desarrollar y extender

- [Guía de desarrollo](development/README.md)
- [Instrucciones para agentes](../AGENTS.md)
- [Convenciones de código](../.github/coding_conventions.md)
- [Suite de tests](../tests/)

## Comprender el producto

- [README del proyecto](../README.md)
- Código productivo: `src/`, `api.py`, `main.py`
- Frontend: `frontend/`

## Evidencia, spikes y reportes

- [`skyrim_voice_asset_spike.md`](skyrim_voice_asset_spike.md): evidencia técnica
  fechada sobre assets de voz.
- [`reports/`](reports/): reportes de tareas y auditorías.
- [`superpowers/specs/`](superpowers/specs/): especificaciones/planes.

Estos documentos pueden explicar **por qué** se tomó una decisión o qué se
investigó, pero no superan al runtime y tests actuales como fuente de
comportamiento.

## Cómo resolver contradicciones

Aplicar [`documentation/source_of_truth.md`](documentation/source_of_truth.md).
Una contradicción documental no autoriza a modificar producción para “hacer
coincidir” el código con un reporte, spike, spec o README antiguo.
