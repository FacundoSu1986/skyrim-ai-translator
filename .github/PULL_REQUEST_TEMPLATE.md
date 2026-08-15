## 📋 Qué cambia y por qué

<!-- Resumen conciso de los cambios y la motivación técnica detrás del PR. -->

## 🛡️ Verificación de Invariantes y Superficies

- [ ] **Glosario Único**: Si se agregaron o modificaron términos de Skyrim, ¿se actualizaron exclusivamente en `SKYRIM_GLOSSARY` (`src/translator.py`)?
- [ ] **Superficies Hermanas de Traducción**: Si se modificó la lógica de traducción o placeholders, ¿se verificó la coherencia entre el camino gratuito (`free_translator.py`) y el camino LLM (`translator.py`)?
- [ ] **Inmutabilidad**: ¿Las transformaciones de datos retornan nuevas instancias (`dataclasses.replace`) sin mutar `StringEntry` in-place?
- [ ] **Concurrencia**: ¿Las operaciones de I/O bloqueante están envueltas en `asyncio.to_thread` o semáforos sin bloquear el event loop de FastAPI?
- [ ] **Seguridad**: ¿Se verificó que ninguna API key, ruta no sanitizada o secreto se exponga en logs o respuestas?

## 🧪 Pruebas y Validación

- [ ] `pytest --verbose` ejecutado con **exit code 0**.
- [ ] Tests añadidos o actualizados con patrón AAA para cada nuevo endpoint, regla o caso borde.
- [ ] Si se tocó el frontend: `npm run build` ejecutado exitosamente en `frontend/`.
