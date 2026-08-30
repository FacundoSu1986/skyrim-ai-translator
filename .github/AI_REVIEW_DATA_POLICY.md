# Política de Datos y Gobernanza de Revisores IA (AI Review Data Policy)

Este documento establece la política de gobernanza y privacidad de datos aplicable a los flujos automatizados de revisión de código basados en modelos de lenguaje (LLMs), específicamente **Qodo Merge / PR-Agent**, integrados en los workflows de GitHub Actions de Skyrim AI Translation Agent (`skyrim-ai-translator`).

---

## 1. Alcance y Contexto del Repositorio

* **Naturaleza pública:** Skyrim AI Translation Agent es actualmente un repositorio de código abierto y público.
* **Transmisión de contenido:** Las herramientas de revisión automatizada (Qodo / PR-Agent) envían a proveedores externos de LLM el contenido necesario para analizar los Pull Requests, incluyendo diffs de código, títulos, descripciones y fragmentos contextuales del repositorio.
* **Autorización acotada:** Se autoriza el procesamiento por terceros exclusivamente sobre el código, documentación y metadatos que **ya son públicos** en este repositorio y que pertenecen a **PRs internos**.

---

## 2. Proveedores Externos y Endpoints

* **Enrutamiento vía OpenRouter:** Los workflows están configurados para consultar modelos externos a través de OpenRouter (e.g., NVIDIA Nemotron, MiniMax).
* **Políticas de retención y registro (Logging):**
  * Algunos endpoints gratuitos (como los modelos NVIDIA Nemotron o variantes comunitarias) pueden registrar prompts y respuestas para fines de seguridad, moderación y mejora de producto según sus respectivos términos de servicio.
  * Cada proveedor upstream en OpenRouter mantiene políticas de retención y privacidad diferenciadas.
* **Revisión obligatoria por cambio de modelo:** Cualquier cambio o adición en `CONFIG.MODEL` o `CONFIG.FALLBACK_MODELS` exige revisar previamente los términos de gobernanza y retención de datos del proveedor correspondiente.

---

## 3. Prohibición de Secretos, Datos Sensibles y PII

* **Prohibición estricta de secretos en el repositorio:** Ningún secreto, API key, token de autenticación, credencial o información personal identificable (PII) debe commitearse al repositorio ni incluirse en el contenido de un Pull Request.
* **Manejo en caso de detección:** Si un diff contiene inadvertidamente información sensible o credenciales, la prioridad inmediata es la revocación/rotación del secreto y la remoción del historial. Las herramientas de revisión automatizada no deben utilizarse sobre ramas o PRs que contengan credenciales expuestas sin sanear.

---

## 4. Control de Ejecución en Forks y Seguridad

* **Bloqueo en PRs de Forks:** Los workflows de revisión automatizada (Qodo / PR-Agent) están restringidos a Pull Requests y comentarios provenientes de ramas internas del repositorio.
* **Mitigación de riesgos de supply-chain:** Los PRs originados desde forks externos no ejecutan automáticamente estos workflows para prevenir la exfiltración de secrets (`OPENROUTER_API_KEY`, `GITHUB_TOKEN`) o ejecuciones maliciosas.

---

## 5. Transición a Repositorio Privado o Manejo de Información Confidencial

* **Desautorización automática:** Si el repositorio pasa a ser privado o si en el futuro se procesan datos confidenciales o no públicos, la configuración de revisores basada en modelos gratuitos de OpenRouter queda **automáticamente NO AUTORIZADA**.
* **Bloqueo fail-closed en workflows:** Los workflows de revisión deben mantener condiciones explícitas a nivel de job (`github.event.repository.private == false`) para fallar de forma cerrada e impedir su ejecución si la visibilidad del repositorio cambia a privada.
* **Requisitos acumulativos para uso sobre datos privados:** Antes de habilitar revisores automáticos sobre datos privados o confidenciales, deben cumplirse **simultáneamente** las siguientes condiciones:
  1. **Zero Data Retention (ZDR) verificable:** Enrutamiento exclusivo hacia endpoints con garantía contractual y técnica de retención cero (`zdr=true`). La configuración `data_collection=deny` restringe el entrenamiento y recolección general del proveedor, pero **no sustituye ni equivale a una garantía estricta de Zero Data Retention (ZDR)**.
  2. **Política de recolección restrictiva:** Habilitación explícita de `data_collection=deny`.
  3. **Endpoints empresariales aprobados:** Uso de contratos o acuerdos de procesamiento de datos (DPA) directos con proveedores que garanticen confidencialidad y no persistencia.
  4. **Reevaluación formal de gobernanza:** Aprobación explícita y auditoría documentada en este archivo antes de activar los workflows.

---

## 6. Inventario Auditado de Modelos Aprobados

<!-- approved-models:start -->
| Modelo Exacto | Proveedor Upstream | Fecha de Revisión | Alcance Autorizado | Retención / Términos |
| :--- | :--- | :--- | :--- | :--- |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede almacenar logs según ToS de OpenRouter/NVIDIA; prohibido para datos privados. |
| `openrouter/minimax/minimax-m3:free` | MiniMax / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; sujeta a términos estándar de MiniMax/OpenRouter; prohibido para datos privados. |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede registrar telemetría; prohibido para datos privados. |
<!-- approved-models:end -->
