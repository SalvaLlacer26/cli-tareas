# ADR-0002: La IA es una capa aparte, con clave fuera del repo y modo sin red

- Estado: aceptada
- Fecha: 2026-11-09
- Autor/a: Salvador Llácer Ivars

## Contexto

A partir de la semana 3 la herramienta usa modelos de IA para tareas que un
programa no hace bien solo: resumir un documento largo, preparar una batería de
ejercicios, agrupar ficheros por lo que dice su contenido (`clasificar`) y
proponer los ejercicios del formulario interactivo (`formulario_evaluar`).

Eso plantea tres problemas que no puede resolver cada comando por su cuenta:

1. **La clave del modelo.** Los modelos del centro se usan con una clave. Si esa
   clave se cuela en el código o en un commit, queda publicada para siempre en
   el historial de git, incluso si luego la borro.
2. **La red y el servidor.** El aula tiene conexión y un servidor de modelos;
   mi casa puede no tenerla, y el servidor se puede saturar (un 503) o tardar
   minutos con un PDF grande. Ninguna orden puede acabar en una traza de Python
   por culpa de la red.
3. **Repetición.** Si cada comando llamase al HTTP por su cuenta, habría cinco
   sitios que mantener y cinco formas distintas de fallar.

## Decisión

Toda la IA pasa por **una única capa** (`ia.py`), con una fachada
(`ProveedorIA`) que es lo único que abre una conexión con el servidor de
modelos. `busqueda.py` es el único módulo que abre una conexión a internet para
buscar (Wikipedia y DuckDuckGo, sin claves), y usa la misma política de reintentos.

**La clave nunca está en el repo.** Se lee de variables de entorno
(`TAREAS_IA_URL`, `TAREAS_IA_KEY`, `TAREAS_MODELO`, `TAREAS_IA_CA`,
`TAREAS_IA_TIMEOUT`) o de un fichero `.env` que está en el `.gitignore` desde el
primer commit. En el repo solo hay un `.env.example` documentado, sin valores.

**Modo sin red obligatorio.** Cualquier problema al hablar con el modelo
(sin clave, sin red, error del servidor, respuesta sin sentido) se convierte en
un `ErrorIA` con un mensaje de **una línea**. La CLI lo captura y **sigue
ofreciendo la versión sin IA** de la orden: `resumir` y `evaluar` caen a una
versión extractiva que saca apartados y definiciones del propio texto, y
`clasificar` pone todo en «Por clasificar». Ninguna orden revienta por no haber
modelo; lo dice y hace lo que puede.

## Alternativas consideradas

1. **Llamar al modelo desde cada comando, con la clave como parámetro.**
   - A favor: inmediato, sin clases.
   - En contra: la clave acabaría en el historial o en el `--help`; no habría un
     sitio donde centrally reintentar ni un modo sin red uniforme.

2. **Guardar la clave en `acciones.json`.**
   - A favor: un único fichero de configuración.
   - En contra: `acciones.json` **se sube a git**; la clave quedaría publicada.
     Por eso las secretos y la configuración normal van separados: el JSON se
     comparte, el `.env` no.

3. **Fallar con un error si no hay IA (sin modo sin red).**
   - A favor: el código es más corto.
   - En contra: deja la herramienta inservible sin conexión y en el servidor
     saturado, y el curso pide expresamente que no reviente.

## Consecuencias

- Positivas: un único punto que auditar; la clave nunca toca el repo ni el
  historial; la herramienta funciona conectada y desconectada; los reintentos
  ante errores momentáneos (429, 5xx) están en un solo sitio.
- Negativas: cada orden con IA necesita, además, su versión sin IA (más código);
  la versión extractiva es de peor calidad que la del modelo; hay que acordarse,
  al añadir una orden de IA nueva, de respetar el contrato de `ErrorIA`.
- Qué haré si cambio de proveedor de modelos: la API es compatible con OpenAI,
  así que bastaría con cambiar `TAREAS_IA_URL` (incluso a un Ollama local); si
  algn día otra API no lo fuese, el cambio quedaría encerrado en `ia.py`.

## El formulario interactivo y la privacidad

`tareas formulario_evaluar` abre un examen en el navegador, pero el servidor que
lo sirve **solo escucha en `127.0.0.1`** (no se expone a la red) y **quien llama
al modelo es la CLI, no el navegador**: la clave no sale del equipo ni aparece
en la página. El tipo test se corrige en local; solo lo escrito se envía al
modelo, igual que en `evaluar`.
