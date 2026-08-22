# Revisión de cumplimiento legal y de licencias

**Proyecto:** `skyrim-ai-translator`
**Fecha de la revisión:** 22 de agosto de 2026
**Alcance:** licencias de dependencias, términos de servicio de los servicios
externos invocados en tiempo de ejecución, propiedad intelectual de terceros
(Bethesda / ZeniMax), protección de datos y las prácticas de seguridad con
consecuencia jurídica.

> **Esto no es asesoramiento jurídico.** Es una revisión técnica de cumplimiento
> hecha leyendo el código, los metadatos de licencia de cada dependencia y las
> condiciones publicadas de los servicios que el proyecto invoca. Las decisiones
> con exposición real —sobre todo H-03 y H-08— deberían contrastarse con un
> profesional antes de distribuir el proyecto de forma amplia o comercial.

---

## Resumen ejecutivo

| ID | Hallazgo | Severidad | Estado |
|----|----------|-----------|--------|
| [H-01](#h-01) | `edge-tts` sin acotar admitía resolver a una versión GPL-3.0 en un proyecto MIT | **Alta** | ✅ Corregido |
| [H-02](#h-02) | Uso programado del endpoint interno de Google Translate | **Media** | ⚠️ Mitigado, decisión pendiente |
| [H-03](#h-03) | Síntesis de voz mediante el servicio de Edge no expuesto como API pública | **Media** | ⚠️ Documentado, decisión pendiente |
| [H-04](#h-04) | Condiciones de los proveedores LLM (OpenAI, DeepSeek, OpenRouter) | Baja | ℹ️ Documentado |
| [H-05](#h-05) | Uso de las marcas «Skyrim» y «The Elder Scrolls» sin descargo | **Media** | ✅ Corregido |
| [H-06](#h-06) | Glosario derivado de la localización oficial en español | Baja | ℹ️ Documentado con límite |
| [H-07](#h-07) | Ingeniería inversa de los formatos `.esp` y `.fuz` | Baja | ✅ Sin objeción |
| [H-08](#h-08) | Redistribución de mods traducidos sin permiso del autor original | **Alta** | ⚠️ Riesgo del usuario final, advertido |
| [H-09](#h-09) | Google Fonts enlazado en caliente (transferencia de IP a un tercero) | **Media** | ✅ Corregido |
| [H-10](#h-10) | Claves de API de terceros en `localStorage` | Baja | ℹ️ Documentado |
| [H-11](#h-11) | La suite de tests llama al endpoint no oficial de Google en cada ejecución | Baja | ⚠️ Abierto |
| [H-12](#h-12) | La API acepta rutas arbitrarias del sistema de ficheros | Baja | ℹ️ Documentado |

**Veredicto general.** No se ha encontrado nada que impida publicar el proyecto
como software libre. El único incumplimiento *estricto* era H-01, un conflicto
de licencias que ya está resuelto. Lo que queda son tres zonas de riesgo que no
se resuelven escribiendo código, sino decidiendo: dos servicios que se usan por
vías no previstas por sus titulares (H-02, H-03) y la advertencia que el
proyecto debe trasladar a sus usuarios sobre los permisos de los mods ajenos
(H-08).

---

## Parte 1 — Licencias de las dependencias

### H-01 · `edge-tts` podía resolver a una versión GPL-3.0 {#h-01}

**Severidad: alta · Estado: corregido en este cambio**

`requirements.txt` declaraba `edge-tts>=6.1.12`, sin límite superior. Los
metadatos publicados en PyPI muestran un cambio de licencia a mitad de la vida
del paquete:

| Versión de `edge-tts` | Licencia declarada |
|-----------------------|--------------------|
| ≤ 6.1.19 | `GNU General Public License v3 (GPLv3)` |
| ≥ 7.0.0 | `GNU Lesser General Public License v3 (LGPLv3)` |

*(Comprobado descargando los wheels de 6.1.12 y 7.2.8 y leyendo su `METADATA`.)*

El problema es que `src/tts_generator.py` hace `import edge_tts` y llama a
`edge_tts.Communicate`: no es una invocación por subproceso, es enlace en el
mismo espacio de proceso. Bajo la interpretación habitual de la FSF, la obra
combinada resultante es un trabajo derivado. Distribuir el proyecto bajo MIT
mientras enlaza una biblioteca GPL-3.0 es incompatible: la GPL exige que el
conjunto se distribuya bajo GPL, y la MIT declarada estaría prometiendo a los
usuarios unos derechos (sublicenciar, integrar en software propietario) que no
se pueden conceder.

La LGPL-3.0 de las versiones 7.x sí es compatible con distribuir el proyecto
bajo MIT, siempre que se cumplan sus condiciones: usar la biblioteca sin
modificarla, dar aviso de que se usa, incluir su licencia y no impedir que el
usuario la sustituya por otra versión. `THIRD-PARTY-NOTICES.md` cubre el aviso.

**Corrección aplicada.** `requirements.txt` pasa a `edge-tts>=7.0.0,<8`, con un
comentario que explica que el límite inferior es una restricción de licencia y
no de funcionalidad, para que nadie lo baje al refactorizar.

**Si en el futuro se prefiere volver a una 6.x:** habría que relicenciar el
proyecto entero a GPL-3.0, o aislar `edge-tts` tras una frontera de proceso
(invocar el binario `edge-tts` por CLI en lugar de importarlo), que es la vía
que suele considerarse suficiente para evitar la obra derivada.

### Inventario de licencias

Backend (verificado leyendo el `METADATA` de cada wheel):

| Paquete | Licencia | Compatible con MIT |
|---------|----------|--------------------|
| `fastapi` | MIT | Sí |
| `uvicorn[standard]` | BSD-3-Clause | Sí |
| `websockets` | BSD-3-Clause | Sí |
| `python-multipart` | Apache-2.0 | Sí |
| `pydantic` | MIT | Sí |
| `edge-tts` (≥ 7.0.0) | LGPL-3.0 | Sí, con avisos (ver H-01) |
| `httpx` | BSD-3-Clause | Sí |
| `pytest`, `pytest-cov` | MIT | Sí (solo desarrollo) |
| `pytest-asyncio` | Apache-2.0 | Sí (solo desarrollo) |

Frontend: `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `oxlint` y los
tipos de `@types/react*` son todos MIT.

Tipografías: `Cinzel`, `Cinzel Decorative` e `Inter` se distribuyen bajo **SIL
Open Font License 1.1**, que permite explícitamente la redistribución y el
alojamiento propio, con dos condiciones que ahora se cumplen: incluir el texto
de la licencia y no vender las fuentes por separado. El texto completo, con los
avisos de copyright de cada familia, está en
`frontend/src/assets/fonts/OFL.txt`.

---

## Parte 2 — Términos de servicio de los servicios externos

### H-02 · Endpoint interno de Google Translate {#h-02}

**Severidad: media · Estado: mitigado; la decisión de fondo es del propietario**

`src/free_translator.py` llamaba a:

```
https://translate.googleapis.com/translate_a/single?client=gtx&...
```

con la cabecera `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)`.

Dos cuestiones distintas:

1. **El endpoint.** `translate_a/single` es la ruta interna que consume la web
   de Google Translate. No es una API pública: no tiene contrato, ni cuota
   documentada, ni condiciones de uso propias. Los Términos de Servicio de
   Google prohíben acceder a los Servicios «por un método distinto de la
   interfaz y las instrucciones que proporcionamos». El uso programado que hace
   el proyecto queda fuera de esos términos. La consecuencia práctica realista
   no es un litigio sino un corte de servicio (bloqueo por IP, `HTTP 429`), que
   es exactamente lo que ocurre hoy al ejecutar los tests (ver H-11).

2. **El `User-Agent` falsificado.** Declararse como Chrome sobre Windows era una
   afirmación falsa dirigida a que el servidor tratase al cliente como un
   navegador. Eso convierte un uso fuera de términos en una elusión deliberada
   de la distinción que el servicio hace entre navegador y automatización, lo
   cual agrava la posición sin aportar ninguna funcionalidad.

**Corrección aplicada.** El `User-Agent` pasa a identificar honestamente al
proyecto (`skyrim-ai-translator/1.0 (+URL del repositorio)`). El módulo lleva un
aviso legal en su docstring, y se emite un `logger.warning` **una sola vez por
proceso** para que quien despliegue la herramienta lo sepa sin llenar el log.

**Decisión pendiente (del propietario).** El camino conforme es sustituir este
endpoint por una API con contrato:

| Alternativa | Licencia / coste | Notas |
|-------------|------------------|-------|
| Google Cloud Translation API | De pago, con nivel gratuito | Misma calidad, con contrato y cuota |
| DeepL API | Nivel gratuito de 500 000 caracteres/mes | Suele dar mejor calidad ES |
| Camino LLM ya implementado | Según proveedor | Ya existe en `src/translator.py` |
| Modelo local (Ollama, NLLB, Opus-MT) | Gratis | Sin dependencia de terceros |

Se ha mantenido el comportamiento actual porque desactivar el modo «gratuito»
por defecto rompería el flujo que la interfaz ofrece hoy, y esa es una decisión
de producto, no de esta revisión.

### H-03 · Síntesis de voz a través del servicio de Microsoft Edge {#h-03}

**Severidad: media · Estado: documentado; la decisión de fondo es del propietario**

`edge-tts` se describe a sí mismo como un módulo que «permite usar el servicio
en línea de texto a voz de Microsoft Edge». Técnicamente habla con el endpoint
de *Read Aloud* del navegador Edge, autenticándose con el token de cliente de
confianza que Edge incorpora. Es la misma categoría de problema que H-02: un
servicio pensado para consumirse desde un producto concreto, consumido desde
fuera de él.

Las voces neuronales (`es-ES-AlvaroNeural`, `es-ES-ElviraNeural`, …) son las
mismas que Microsoft comercializa en Azure AI Speech. Las condiciones de Azure
para esas voces incluyen restricciones sobre el uso del audio generado
—atribución en ciertos escenarios, prohibición de emplearlo para entrenar o
mejorar otros modelos de voz— que no se aplican aquí porque el proyecto no pasa
por Azure en ningún momento.

Esto importa por el destino del audio: el proyecto no solo genera voz, la
**empaqueta en un mod** que después se comparte. Ahí el audio deja de ser
consumo personal y pasa a ser un artefacto distribuido.

**Recomendaciones, por orden de solidez:**

1. Ofrecer un backend TTS alternativo con licencia explícita para redistribuir
   el audio: **Piper** (MIT), **Coqui TTS** o **XTTS** (revisando sus términos
   por modelo), o **Azure AI Speech** con una suscripción real.
2. Si se mantiene `edge-tts`, dejar claro en la interfaz y en el README que el
   audio se genera por un canal no contractual y que redistribuirlo es
   responsabilidad de quien publica el mod.
3. No presentar la herramienta como apta para uso comercial mientras esta sea
   la única ruta de voz.

### H-04 · Proveedores de LLM {#h-04}

**Severidad: baja · Estado: documentado**

`src/translator.py` habla con cualquier API compatible con OpenAI. Aquí no hay
incumplimiento: son APIs públicas, con contrato, y la clave la aporta el propio
usuario. Tres matices que conviene que el usuario conozca:

- **Titularidad de la salida.** Las condiciones de OpenAI ceden al usuario los
  derechos sobre la salida; otros proveedores varían. Quien publique una
  traducción generada por LLM debería comprobar los términos del proveedor que
  usó.
- **Transferencia internacional.** DeepSeek procesa en servidores de China. Si
  el texto de origen contuviera datos personales, esa transferencia entraría en
  el ámbito del capítulo V del RGPD. Para texto de diálogos de un mod el
  supuesto es teórico, pero el proyecto no impide enviar cualquier cosa.
- **Uso para entrenamiento.** Varios proveedores usan por defecto las entradas
  de la API gratuita para entrenar. Es relevante si alguien tradujese contenido
  no publicado.

---

## Parte 3 — Propiedad intelectual de terceros

### H-05 · Marcas «Skyrim» y «The Elder Scrolls» {#h-05}

**Severidad: media · Estado: corregido en este cambio**

«The Elder Scrolls», «Skyrim» y «Bethesda» son marcas registradas de ZeniMax
Media Inc. y Bethesda Softworks LLC. El proyecto las usa en su nombre, en el
título de la web, en el README y en la interfaz.

Usar la marca de un tercero para **describir con qué es compatible tu producto**
es uso nominativo, admitido tanto en EE. UU. (*New Kal Kan / New Kids on the
Block*, y la doctrina posterior) como en la UE (art. 14.1.c del Reglamento
2017/1001 sobre la marca de la Unión Europea), siempre que se cumplan tres
condiciones:

1. Que no haya otro modo razonable de identificar el producto. Aquí no lo hay:
   la herramienta traduce mods de Skyrim.
2. Que se use solo lo imprescindible de la marca. El proyecto usa el nombre, no
   el logotipo, ni la tipografía oficial, ni el emblema del dragón.
3. Que no se sugiera patrocinio ni afiliación. **Este era el punto débil**: no
   había ningún descargo en ninguna superficie del producto.

**Corrección aplicada.** Se añade un descargo de afiliación en el README, en el
`<noscript>` del HTML inicial y en los datos estructurados JSON-LD
(`disambiguatingDescription`), de modo que la declaración sea visible para
personas, para buscadores y para quien lea el repositorio.

**Lo que conviene no hacer** a partir de aquí: registrar un dominio que combine
«skyrim» con «oficial», usar arte, capturas, tipografías o sonidos del juego
como material promocional, o presentar el proyecto de forma que parezca un
producto de Bethesda.

Nota sobre los recursos gráficos: `frontend/src/assets/skyrim-ui/` contiene un
medallón, un divisor rúnico y una esquina nórdica. Son ornamentos de estética
nórdica genérica, no reproducciones de arte del juego; las runas del Futhark
antiguo son patrimonio histórico, no material protegible. Aun así, **el
propietario debería confirmar la procedencia de `dragon-medallion.webp`**: si
proviene de un banco de imágenes o de un generador, la licencia de origen debe
constar en el repositorio. Es el único recurso cuyo origen esta revisión no ha
podido determinar leyendo el archivo (no conserva metadatos).

### H-06 · Glosario de la localización oficial en español {#h-06}

**Severidad: baja · Estado: documentado, con un límite recomendado**

`SKYRIM_GLOSSARY` en `src/translator.py` contiene 37 pares que reproducen la
localización oficial al español: *Whiterun → Carrera Blanca*, *Winterhold →
Hibernalia*, *Blackreach → Límite Sombrío*.

Palabra por palabra, estos términos no son protegibles: nombres y frases cortas
quedan fuera del derecho de autor tanto en EE. UU. (37 CFR 202.1(a)) como en la
UE por falta de originalidad suficiente. El riesgo no está en los términos sino
en **la compilación**: una selección y disposición sustanciales del trabajo de
localización ajeno podría alcanzar la protección de las bases de datos (derecho
*sui generis* de la Directiva 96/9/CE) si demostrase una inversión sustancial en
su obtención.

Con 37 entradas orientadas a la coherencia funcional, el riesgo es remoto.
Escalaría si el glosario creciese hasta convertirse en un volcado extenso de las
tablas de localización oficiales.

**Recomendación:** mantener el glosario acotado a los términos necesarios para
la coherencia del lore y no importar de forma masiva los `.strings` oficiales
del juego a este repositorio. Los términos deben derivarse del uso, no
extraerse en bloque de los archivos del juego.

### H-07 · Ingeniería inversa de `.esp` y `.fuz` {#h-07}

**Severidad: baja · Estado: sin objeción**

`src/esp_parser.py` interpreta el formato binario de los plugins de Bethesda y
`src/voice_assets.py` empaqueta contenedores FUZ.

Esto está bien planteado:

- La ingeniería inversa **con fines de interoperabilidad** está expresamente
  amparada en la UE (art. 6 de la Directiva 2009/24/CE, que además declara nula
  cualquier cláusula contractual que la excluya) y en EE. UU. por la excepción
  de interoperabilidad del 17 U.S.C. §1201(f) y la línea jurisprudencial
  *Sega v. Accolade* / *Sony v. Connectix*.
- Bethesda **fomenta activamente** el modding: distribuye el Creation Kit y
  mantiene una política de mods propia. El ecosistema entero (SKSE, xEdit, MO2,
  Dynamic String Distributor) opera sobre esa base desde hace más de una década.
- `src/voice_assets.py` documenta su implementación FUZ como *clean-room* y no
  incorpora código de Bethesda. Es la práctica correcta y conviene conservar esa
  nota, porque es lo que distingue una reimplementación lícita de una copia.

El proyecto **no** distribuye ningún archivo del juego, ni claves, ni elude
ninguna medida tecnológica de protección. No hay aquí nada que corregir.

### H-08 · Redistribución de mods traducidos {#h-08}

**Severidad: alta (para el usuario final) · Estado: advertencia añadida**

Este es el riesgo jurídico con más probabilidad real de materializarse, y no
recae sobre el repositorio sino sobre **quien lo usa**.

Una traducción es una obra derivada. Traducir el mod de otra persona y
publicarlo requiere autorización de su autor. En la práctica del modding esto
está regulado por las políticas de permisos de cada plataforma:

- **Nexus Mods** obliga a respetar el bloque de permisos de cada página de mod.
  Muchos autores marcan explícitamente si permiten traducciones y bajo qué
  condiciones. Subir una traducción no autorizada es causa de retirada y de
  sanción de la cuenta.
- Muchos autores exigen que la traducción sea un parche que dependa del mod
  original, no un repaquetado completo. El diseño del proyecto ayuda aquí: la
  salida DSD es un JSON de sustitución de cadenas, no una copia del `.esp`.
- El audio generado añade una capa más: si el mod original ya traía voces, la
  traducción no debe redistribuirlas.

La herramienta en sí es neutra —traducir para uso propio no plantea problema—,
pero facilita una acción que puede infringir derechos si se da el paso de
publicar.

**Corrección aplicada.** Se añade al README un aviso explícito de permisos, con
la regla operativa: *comprueba los permisos del mod original y pide autorización
al autor antes de publicar una traducción*.

---

## Parte 4 — Protección de datos

### H-09 · Google Fonts enlazado en caliente {#h-09}

**Severidad: media · Estado: corregido en este cambio**

`frontend/src/index.css` abría con:

```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel...');
```

Cada visita hacía que el navegador contactase con servidores de Google,
transmitiendo la dirección IP del visitante —dato personal según el art. 4.1 del
RGPD, conforme a *Breyer*, C-582/14— antes de que hubiera podido consentirlo.

El *Landgericht* de Múnich I lo declaró ilícito el 20 de enero de 2022
(Az. 3 O 17493/20), condenando al titular de un sitio a indemnizar por incrustar
Google Fonts de forma dinámica. La sentencia desencadenó una oleada de
reclamaciones en Alemania y sigue siendo la referencia europea.

**Corrección aplicada.** Las tres familias se auto-hospedan: los `.woff2` viven
en `frontend/src/assets/fonts/`, las declaraciones `@font-face` en
`frontend/src/fonts.css` y el texto de la OFL 1.1 acompaña a los archivos. Se ha
verificado sobre el bundle de producción que no queda ninguna petición a
`fonts.googleapis.com` ni a `fonts.gstatic.com`.

Efecto colateral positivo: se elimina una cadena de peticiones bloqueantes
(HTML → CSS → CSS de Google → woff2), lo que mejora el First Contentful Paint.

### H-10 · Claves de API en `localStorage` {#h-10}

**Severidad: baja · Estado: documentado**

`frontend/src/App.jsx` guarda la clave de API del usuario en
`localStorage` bajo `skyrim_ai_key`, junto con las rutas de MO2 y de Skyrim.

No es una infracción: es la clave del propio usuario, en su propio navegador, y
nunca se envía a un servidor del proyecto. Pero `localStorage` es accesible a
cualquier JavaScript del mismo origen, así que un XSS la expone. Para una
herramienta que corre en `localhost` el impacto es limitado; dejaría de serlo si
la interfaz se alojase en un dominio público.

**Recomendaciones:** no persistir la clave por defecto (ofrecer una casilla
«recordar»), o mantenerla solo en memoria durante la sesión. Y verificar —cosa
que esta revisión confirma que ya se cumple— que la clave nunca aparezca en
logs, en payloads de error ni en el nombre de los trabajos.

---

## Parte 5 — Prácticas con consecuencia legal

### H-11 · Los tests llaman al endpoint no oficial de Google {#h-11}

**Severidad: baja · Estado: abierto**

`tests/test_esp_and_voice.py::test_free_translator_glossary` y cuatro tests de
`tests/test_api.py` ejecutan traducciones reales contra
`translate.googleapis.com`. Consecuencias:

- Cada ejecución de CI genera tráfico no autorizado contra el servicio de un
  tercero, desde infraestructura de GitHub, multiplicado por cada push y cada PR.
- Los tests son intrínsecamente frágiles: **hoy fallan con `HTTP 429: Too Many
  Requests`**, y fallaban ya antes de los cambios de esta revisión.

**Recomendación:** simular la respuesta HTTP en esos cinco tests, como ya hace
`tests/test_translator.py` con el camino LLM y como hacen los dos tests de
conformidad añadidos aquí. La cobertura no se pierde —lo que se valida es la
protección del glosario, no la calidad de Google— y CI deja de depender de la
red. No se ha aplicado en esta revisión por ser una reescritura de tests ajena
al encargo; queda como tarea acotada y de bajo riesgo.

### H-12 · La API acepta rutas arbitrarias del sistema de ficheros {#h-12}

**Severidad: baja (en el diseño actual) · Estado: documentado**

`/api/mo2/mods`, `/api/mo2/start` y `/api/mo2/inject/{job_id}` reciben del
cliente `mo2_path` y `skyrim_data_path` y operan sobre ellas. La validación
existente es correcta para lo que cubre: `_sanitize_name()` impide que el nombre
del mod escape de su directorio, y las rutas se comprueban como directorios
existentes.

Lo que no hay —por diseño, ya que el usuario debe poder elegir su carpeta de
MO2— es una restricción sobre *qué* directorios del sistema son aceptables. En
el modelo previsto (servidor en `localhost`, un solo usuario) eso es razonable y
el CORS por defecto está bien acotado a orígenes locales.

Deja de serlo si alguien expone la API en `0.0.0.0` o tras un proxy: cualquier
cliente podría entonces enumerar directorios del anfitrión y escribir archivos
en ellos. Con `allow_credentials=True`, ampliar `CORS_ORIGINS` sin cuidado
agrava el escenario.

**Recomendación:** documentar que el servidor está pensado para escuchar solo en
`127.0.0.1`, y si alguna vez se admite uso remoto, añadir autenticación y una
lista blanca de raíces permitidas.

---

## Anexo A — Cambios aplicados en esta revisión

| Archivo | Cambio | Hallazgo |
|---------|--------|----------|
| `requirements.txt` | `edge-tts` acotado a `>=7.0.0,<8` (LGPL, no GPL) | H-01 |
| `src/free_translator.py` | `User-Agent` honesto, aviso legal y advertencia única en log | H-02 |
| `frontend/src/fonts.css`, `frontend/src/assets/fonts/` | Auto-hospedaje de las tres familias + texto de la OFL | H-09 |
| `frontend/src/index.css` | Eliminado el `@import` a `fonts.googleapis.com` | H-09 |
| `frontend/index.html` | Descargo de afiliación en `<noscript>` y en JSON-LD | H-05 |
| `README.md` | Secciones de descargo legal y permisos de mods | H-05, H-08 |
| `THIRD-PARTY-NOTICES.md` | Inventario de licencias de terceros (nuevo) | H-01 |
| `tests/test_esp_and_voice.py` | Dos tests de conformidad del traductor gratuito | H-02 |

## Anexo B — Decisiones que quedan en manos del propietario

1. **H-02 / H-03.** Si el proyecto aspira a recomendarse abiertamente o a tener
   cualquier dimensión comercial, sustituir los dos servicios no contractuales
   por alternativas con licencia (DeepL o Cloud Translation para el texto; Piper
   o Azure Speech para la voz). Mientras sean el camino por defecto, conviene
   que el README no presente la herramienta como apta para uso comercial.
2. **H-05.** Confirmar la procedencia y la licencia de
   `frontend/src/assets/skyrim-ui/dragon-medallion.webp` y dejarla registrada.
3. **H-11.** Simular la red en los cinco tests que hoy llaman a Google.
4. Añadir un `SECURITY.md` con una vía de contacto para reportar
   vulnerabilidades, y un `CONTRIBUTING.md` que aclare bajo qué licencia se
   aportan las contribuciones (habitualmente, la MIT del proyecto).
