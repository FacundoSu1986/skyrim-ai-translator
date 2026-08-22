# Avisos de terceros

`skyrim-ai-translator` se distribuye bajo la licencia MIT (ver [LICENSE](LICENSE)).
Este archivo recoge el software y los recursos de terceros que el proyecto
incorpora o invoca, junto con sus licencias. Los avisos de la LGPL-3.0 y de la
SIL OFL 1.1 se reproducen aquí porque ambas lo exigen para su redistribución.

El análisis de compatibilidad que respalda esta tabla está en
[docs/legal/COMPLIANCE-REVIEW.md](docs/legal/COMPLIANCE-REVIEW.md).

---

## Dependencias de Python (ejecución)

| Paquete | Licencia | Proyecto |
|---------|----------|----------|
| fastapi | MIT | https://github.com/fastapi/fastapi |
| uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| websockets | BSD-3-Clause | https://github.com/python-websockets/websockets |
| python-multipart | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pydantic | MIT | https://github.com/pydantic/pydantic |
| **edge-tts** | **LGPL-3.0** | https://github.com/rany2/edge-tts |
| httpx | BSD-3-Clause | https://github.com/encode/httpx |

### Aviso específico sobre edge-tts (LGPL-3.0)

Este proyecto usa `edge-tts` como biblioteca, sin modificarla, y la importa
dinámicamente en `src/tts_generator.py`.

Conforme a la LGPL-3.0:

- `edge-tts` es propiedad de sus autores (rany2 y colaboradores) y se distribuye
  bajo la GNU Lesser General Public License versión 3, cuyo texto está
  disponible en https://www.gnu.org/licenses/lgpl-3.0.html
- No se ha modificado su código fuente.
- Cualquier usuario puede sustituir la versión instalada de `edge-tts` por otra
  versión compatible de la biblioteca sin necesidad de recompilar este proyecto:
  basta con instalar la versión deseada con `pip`.
- El código fuente de `edge-tts` está disponible en su repositorio público.

**Nota de compatibilidad de licencias.** `requirements.txt` exige
`edge-tts>=7.0.0`. Las versiones anteriores a la 7.0.0 se publicaron bajo
GPL-3.0, incompatible con la distribución de este proyecto bajo MIT. Ese límite
inferior es una restricción de licencia, no de funcionalidad, y no debe bajarse.

## Dependencias de Python (desarrollo)

| Paquete | Licencia |
|---------|----------|
| pytest | MIT |
| pytest-asyncio | Apache-2.0 |
| pytest-cov | MIT |

## Dependencias de JavaScript

| Paquete | Licencia | Proyecto |
|---------|----------|----------|
| react, react-dom | MIT | https://github.com/facebook/react |
| vite | MIT | https://github.com/vitejs/vite |
| @vitejs/plugin-react | MIT | https://github.com/vitejs/vite-plugin-react |
| oxlint | MIT | https://github.com/oxc-project/oxc |
| @types/react, @types/react-dom | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |

## Tipografías

Las tres familias se auto-hospedan en `frontend/src/assets/fonts/` y se
distribuyen bajo la **SIL Open Font License 1.1**. El texto completo de la
licencia, con los avisos de copyright de cada familia, acompaña a los archivos
en [`frontend/src/assets/fonts/OFL.txt`](frontend/src/assets/fonts/OFL.txt).

| Familia | Copyright | Proyecto |
|---------|-----------|----------|
| Cinzel | © 2012 Natanael Gama, con nombre reservado «Cinzel» | https://github.com/NDISCOVER/Cinzel |
| Cinzel Decorative | © 2012 Natanael Gama, con nombre reservado «Cinzel» | https://github.com/NDISCOVER/Cinzel |
| Inter | © 2020 The Inter Project Authors | https://github.com/rsms/inter |

---

## Servicios externos invocados en tiempo de ejecución

Estos servicios **no se incorporan** al proyecto: se invocan por red durante la
ejecución. Su uso se rige por las condiciones de cada titular, y la
responsabilidad recae en quien despliega la herramienta.

| Servicio | Uso en el proyecto | Situación |
|----------|--------------------|-----------|
| Servicio de voz de Microsoft Edge (vía `edge-tts`) | Generación del doblaje neural | Servicio no expuesto como API pública. Ver hallazgo H-03 |
| Endpoint web de Google Translate | Modo de traducción «gratuito» | Endpoint interno, uso fuera de los ToS de Google. Ver hallazgo H-02 |
| OpenAI / DeepSeek / OpenRouter / Ollama | Modo de traducción por LLM | APIs públicas; la clave la aporta el usuario. Ver hallazgo H-04 |

---

## Interoperabilidad con el ecosistema de modding

El proyecto lee y escribe formatos de terceros con fines de interoperabilidad.
**No incorpora, redistribuye ni deriva código de ninguno de ellos**, y ninguno
impone condiciones de licencia a este repositorio.

| Proyecto | Relación | Licencia propia |
|----------|----------|-----------------|
| Mod Organizer 2 | Se escribe en su estructura de carpetas | GPL-3.0 (sin enlace de código) |
| Dynamic String Distributor | Se genera el JSON que consume | Licencia del propio plugin |
| SKSE | Compatibilidad indirecta vía DSD | Licencia propia de SKSE |
| The Elder Scrolls V: Skyrim (formatos `.esp`, `.strings`, `.fuz`) | Lectura y escritura de formatos, mediante reimplementación *clean-room* | Ver hallazgos H-05 y H-07 |

## Marcas registradas

«The Elder Scrolls», «Skyrim», «Bethesda» y «Creation Kit» son marcas
registradas de ZeniMax Media Inc. y Bethesda Softworks LLC. Se usan aquí de
forma nominativa, únicamente para identificar el juego con el que la herramienta
es compatible.

**Este proyecto no está afiliado, patrocinado ni respaldado por Bethesda
Softworks LLC ni por ZeniMax Media Inc.**
