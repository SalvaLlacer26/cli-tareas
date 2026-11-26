# Spec · CLI `tareas`

Especificación de 10 líneas: para quién es, qué resuelve, qué órdenes tendrá y
qué **no** hará. Es el contrato que precede al código (paso 1 del ciclo del
curso).

## Para quién y qué problema resuelve
- Para un estudiante de 1º de DAM que vive en la terminal y pierde tiempo
  ordenando su carpeta de descargas y preparando material de estudio a mano.
- Convierte esa faena en **una orden reutilizable**: defines qué hacer en
  `acciones.json` (fuera del código) y la herramienta lo ejecuta igual siempre.

## Qué hará (órdenes)
- `tareas acciones` / `tareas validar`: listar y validar `acciones.json`.
- `tareas ejecutar <acción> [CARPETA] --simular | --si`: correr una acción
  genérica (mover, copiar, renombrar, borrar) con simulación y confirmación.
- Semana 3, con IA: `tareas analizar` (fichas), `tareas organizar`/`deshacer`,
  `tareas clasificar` (carpetas según contenido), `tareas resumir` (apuntes
  completos del tema acotado por un documento) y `tareas evaluar` /
  `tareas formulario_evaluar` (exámenes).

## Qué NO hará
- No tocará nunca carpetas reales sin pasar antes por `--simular` y por
  `~/pruebas-tareas`.
- No guardará claves en el repo ni en el historial: la clave del modelo vive en
  un `.env` ignorado por git.
- No revirá con un *traceback* ante un error previsible (ruta inexistente, JSON
  roto, sin red): mensaje de una línea y código de salida adecuado.
- No dependerá de la IA para lo que no la necesita: sin red siguen funcionando
  las acciones del sistema.
