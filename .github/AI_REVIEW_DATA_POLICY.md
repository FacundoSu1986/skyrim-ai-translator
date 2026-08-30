# Política de Datos y Gobernanza de Revisores IA (AI Review Data Policy)

Este documento establece la política de gobernanza y privacidad de datos aplicable a los flujos automatizados de revisión de código basados en modelos de lenguaje (LLMs), específicamente **Qodo Merge / PR-Agent**, integrados en los workflows de GitHub Actions de Skyrim AI Translation Agent (`skyrim-ai-translator`).

---

## 1. Alcance y Contexto del Repositorio

* **Naturaleza pública:** Skyrim AI Translation Agent es actualmente un repositorio de código abierto y público.
* **Transmisión de contenido:** Las herramientas de revisión automatizada (Qodo / PR-Agent) envían a proveedores externos de LLM el contenido necesario para analizar los Pull Requests, incluyendo diffs de código, títulos, descripciones y fragmentos contextuales del repositorio.
* **Autorización acotada:** Se autoriza el procesamiento por terceros exclusivamente sobre el código, documentación y metadatos que **ya son públicos** en este repositorio y que pertenecen a **PRs internos**.
* **Limitación estricta de alcance:** Esta autorización aplica única y exclusivamente bajo la clasificación `PUBLIC_DATA_ONLY`.

---

## 2. Proveedores Externos, Enrutamiento y Limitaciones Técnicas

* **Enrutamiento vía OpenRouter:** Los workflows consultan modelos a través de OpenRouter (e.g., NVIDIA Nemotron, MiniMax) mediante LiteLLM integrado en PR-Agent v0.43.0.
* **Políticas de retención y registro (Logging):**
  * Los endpoints comunitarios y gratuitos (como NVIDIA Nemotron y MiniMax) pueden registrar prompts y respuestas para fines de moderación, seguridad y telemetría según los términos de servicio de OpenRouter y de cada proveedor upstream.
* **Limitaciones de Provider Routing:**
  * PR-Agent v0.43.0 no provee un mecanismo para fijar estáticamente parámetros de `provider` de OpenRouter (tales como `provider_only` o `allow_fallbacks`) diferenciados por cada modelo en cadenas heterogéneas (NVIDIA + MiniMax).
  * Por consiguiente, el enrutamiento upstream específico no está técnicamente congelado por el workflow en tiempo de ejecución. Esto es aceptable única y exclusivamente porque el alcance se encuentra restringido a datos ya públicos (`PUBLIC_DATA_ONLY`).
* **Revisión obligatoria por cambio de modelo:** Cualquier cambio o adición en `CONFIG.MODEL` o `CONFIG.FALLBACK_MODELS` exige auditar previamente los términos del proveedor upstream y registrar la aprobación en este documento.

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
* **Bloqueo fail-closed en workflows:** Los workflows de revisión mantienen condiciones explícitas a nivel de job (`github.event.repository.private == false`) para fallar de forma cerrada e impedir su ejecución si la visibilidad del repositorio cambia a privada.
* **Requisitos acumulativos para uso sobre datos privados:** Antes de habilitar revisores automáticos sobre datos privados o confidenciales, deben cumplirse **simultáneamente** las siguientes condiciones:
  1. **Zero Data Retention (ZDR) verificable:** Enrutamiento exclusivo hacia endpoints con garantía contractual y técnica de retención cero (`zdr=true`). La configuración `data_collection=deny` restringe el entrenamiento y recolección general del proveedor, pero **no sustituye ni equivale a una garantía estricta de Zero Data Retention (ZDR)**.
  2. **Transmisión verificada:** La herramienta de revisión debe soportar y transmitir explícitamente los flags `zdr=true` y `data_collection=deny` en el payload de cada petición. **Se documenta explícitamente que el workflow actual con PR-Agent v0.43.0 NO transmite ni garantiza estos parámetros a nivel de payload.**
  3. **Endpoints empresariales aprobados:** Uso de contratos o acuerdos de procesamiento de datos (DPA) directos con proveedores que garanticen confidencialidad y no persistencia.
  4. **Frontera de invariantes del repositorio:** Una configuración realizada externamente en el panel de cuenta de OpenRouter no constituye un invariante verificable dentro del repositorio; por tanto, no autoriza por sí sola el procesamiento de datos privados.
  5. **Reevaluación formal de gobernanza:** Aprobación explícita y auditoría documentada en este archivo antes de activar los workflows para entornos privados.

---

## 6. Inventario Auditado de Modelos Aprobados

<!-- approved-models:start -->
| Modelo Exacto | Proveedor Upstream | Fecha de Revisión | Alcance Autorizado | Retención / Términos |
| :--- | :--- | :--- | :--- | :--- |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede almacenar logs según ToS de OpenRouter/NVIDIA; prohibido para datos privados. |
| `openrouter/minimax/minimax-m3:free` | MiniMax / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; sujeta a términos estándar de MiniMax/OpenRouter; prohibido para datos privados. |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA / OpenRouter | 2026-08-30 | `PUBLIC_DATA_ONLY` | Endpoint gratuito; puede registrar telemetría; prohibido para datos privados. |
<!-- approved-models:end -->

---

## 7. Riesgo Residual de Cadena de Suministro (Supply Chain)

* **Fijación de la Action:** El workflow fija la GitHub Action mediante el commit SHA `4ebd5c5333c6ef21509e7304d27969eb825e6f22` (`Codium-ai/pr-agent` v0.43.0).
* **Dependencia Docker upstream:** El archivo `action.yaml` upstream ejecuta `Dockerfile.github_action_dockerhub`, el cual referencia la imagen base `FROM pragent/pr-agent:github_action`.
* **Mutabilidad de tag:** Debido a que la etiqueta `github_action` en Docker Hub es mutable y no está fijada por digest criptográfico (`sha256:...`), el pinning de la Action no constituye una inmovilización transitiva completa de la imagen de ejecución.
* **Tratamiento del riesgo:** Se acepta temporalmente como un riesgo conocido del ecosistema upstream en este entorno público. El eventual endurecimiento (por ejemplo, fijación por digest SHA256 o vendorizado/fork local de la Action) queda reservado para un cambio de infraestructura dedicado.
