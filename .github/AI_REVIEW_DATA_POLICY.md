# Pol?tica de Datos y Gobernanza de Revisores IA (AI Review Data Policy)

Este documento establece la pol?tica de gobernanza y privacidad de datos aplicable a los flujos automatizados de revisi?n de c?digo basados en modelos de lenguaje (LLMs), espec?ficamente **Qodo Merge / PR-Agent**, integrados en los workflows de GitHub Actions de Skyrim AI Translation Agent (`skyrim-ai-translator`).

---

## 1. Alcance y Contexto del Repositorio

* **Naturaleza p?blica:** Skyrim AI Translation Agent es actualmente un repositorio de c?digo abierto y p?blico.
* **Transmisi?n de contenido:** Las herramientas de revisi?n automatizada (Qodo / PR-Agent) env?an a proveedores externos de LLM el contenido necesario para analizar los Pull Requests, incluyendo diffs de c?digo, t?tulos, descripciones y fragmentos contextuales del repositorio.
* **Autorizaci?n acotada:** Se autoriza el procesamiento por terceros exclusivamente sobre el c?digo, documentaci?n y metadatos que **ya son p?blicos** en este repositorio y que pertenecen a **PRs internos**.
* **Limitaci?n estricta de alcance:** Esta autorizaci?n aplica ?nica y exclusivamente bajo la clasificaci?n `PUBLIC_DATA_ONLY`.

---

## 2. Proveedores Externos, Enrutamiento y Limitaciones T?cnicas

* **Enrutamiento v?a OpenRouter:** Los workflows consultan modelos a trav?s de OpenRouter (e.g., NVIDIA Nemotron, MiniMax) mediante LiteLLM integrado en PR-Agent v0.43.0.
* **Pol?ticas de retenci?n y registro (Logging):**
  * Los endpoints comunitarios y gratuitos (como NVIDIA Nemotron y MiniMax) pueden registrar prompts y respuestas para fines de moderaci?n, seguridad y telemetr?a seg?n los t?rminos de servicio de OpenRouter y de cada proveedor upstream.
* **Limitaciones de Provider Routing:**
  * PR-Agent v0.43.0 no provee un mecanismo para fijar est?ticamente par?metros de `provider` de OpenRouter (tales como `provider_only` o `allow_fallbacks`) diferenciados por cada modelo en cadenas heterog?neas (NVIDIA + MiniMax).
  * Por consiguiente, el enrutamiento upstream espec?fico no est? t?cnicamente congelado por el workflow en tiempo de ejecuci?n. Esto es aceptable ?nica y exclusivamente porque el alcance se encuentra restringido a datos ya p?blicos (`PUBLIC_DATA_ONLY`).
* **Revisi?n obligatoria por cambio de modelo:** Cualquier cambio o adici?n en `CONFIG.MODEL` o `CONFIG.FALLBACK_MODELS` exige auditar previamente los t?rminos del proveedor upstream y registrar la aprobaci?n en este documento.

---

## 3. Prohibici?n de Secretos, Datos Sensibles y PII

* **Prohibici?n estricta de secretos en el repositorio:** Ning?n secreto, API key, token de autenticaci?n, credencial o informaci?n personal identificable (PII) debe commitearse al repositorio ni incluirse en el contenido de un Pull Request.
* **Manejo en caso de detecci?n:** Si un diff contiene inadvertidamente informaci?n sensible o credenciales, la prioridad inmediata es la revocaci?n/rotaci?n del secreto y la remoci?n del historial. Las herramientas de revisi?n automatizada no deben utilizarse sobre ramas o PRs que contengan credenciales expuestas sin sanear.

---

## 4. Control de Ejecuci?n en Forks y Seguridad

* **Bloqueo en PRs de Forks:** Los workflows de revisi?n automatizada (Qodo / PR-Agent) est?n restringidos a Pull Requests y comentarios provenientes de ramas internas del repositorio.
* **Mitigaci?n de riesgos de supply-chain:** Los PRs originados desde forks externos no ejecutan autom?ticamente estos workflows para prevenir la exfiltraci?n de secrets (`OPENROUTER_API_KEY`, `GITHUB_TOKEN`) o ejecuciones maliciosas.

---

## 5. Transici?n a Repositorio Privado o Manejo de Informaci?n Confidencial

* **Desautorizaci?n autom?tica:** Si el repositorio pasa a ser privado o si en el futuro se procesan datos confidenciales o no p?blicos, la configuraci?n de revisores basada en modelos gratuitos de OpenRouter queda **autom?ticamente NO AUTORIZADA**.
* **Bloqueo fail-closed en workflows:** Los workflows de revisi?n mantienen condiciones expl?citas a nivel de job (`github.event.repository.private == false`) para fallar de forma cerrada e impedir su ejecuci?n si la visibilidad del repositorio cambia a privada.
* **Requisitos acumulativos para uso sobre datos privados:** Antes de habilitar revisores autom?ticos sobre datos privados o confidenciales, deben cumplirse **simult?neamente** las siguientes condiciones:
  1. **Zero Data Retention (ZDR) verificable:** Enrutamiento exclusivo hacia endpoints con garant?a contractual y t?cnica de retenci?n cero (`zdr=true`). La configuraci?n `data_collection=deny` restringe el entrenamiento y recolecci?n general del proveedor, pero **no sustituye ni equivale a una garant?a estricta de Zero Data Retention (ZDR)**.
  2. **Transmisi?n verificada:** La herramienta de revisi?n debe soportar y transmitir expl?citamente los flags `zdr=true` y `data_collection=deny` en el payload de cada petici?n. **Se documenta expl?citamente que el workflow actual con PR-Agent v0.43.0 NO transmite ni garantiza estos par?metros a nivel de payload.**
  3. **Endpoints empresariales aprobados:** Uso de contratos o acuerdos de procesamiento de datos (DPA) directos con proveedores que garanticen confidencialidad y no persistencia.
  4. **Frontera de invariantes del repositorio:** Una configuraci?n realizada externamente en el panel de cuenta de OpenRouter no constituye un invariante verificable dentro del repositorio; por tanto, no autoriza por s? sola el procesamiento de datos privados.
  5. **Reevaluaci?n formal de gobernanza:** Aprobaci?n expl?cita y auditor?a documentada en este archivo antes de activar los workflows para entornos privados.

---

## 6. Inventario Auditado de Modelos Aprobados

<!-- approved-models:start -->
| Modelo Exacto | Proveedor Upstream | Fecha de Revisi?n | Alcance Autorizado | Retenci?n / T?rminos |
| :--- | :--- | :--- | :--- | :--- |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede almacenar logs seg?n ToS de OpenRouter/NVIDIA; prohibido para datos privados. |
| `openrouter/minimax/minimax-m3:free` | MiniMax / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; sujeta a t?rminos est?ndar de MiniMax/OpenRouter; prohibido para datos privados. |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede registrar telemetr?a; prohibido para datos privados. |
<!-- approved-models:end -->
