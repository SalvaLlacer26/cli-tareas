---
name: acciones-json
description: Reglas del fichero acciones.json de la CLI tareas (campos, carpetas, filtros, plantillas y validación) y del ciclo analizar → organizar → deshacer. Úsala siempre que crees o cambies acciones, carpetas de destino o el código que las lee (config.py, clasificador.py, analizador.py, organizador.py, ficha.py).
---

# Esquema de acciones.json

Raíz: `{"version": 1, "acciones": [...], "carpetas": [...]}`.

## Carpetas (las asignaturas)

- Cada carpeta: `clave` (obligatoria, p. ej. `bbdd`), `etiqueta`, `destino`, `patrones`, `respaldo`.
- Una acción puede apuntar a una carpeta con `"carpeta": "bbdd"` y **hereda** su `destino` y sus `patrones`. Así la asignatura se escribe una sola vez.
- Una carpeta con `"respaldo": true` recibe lo que no se ha podido clasificar.
- Los patrones se **ponderan**, no se cuentan igual:
  - una frase («projecte intermodular») pesa 3, una palabra larga 2, una corta 1;
  - lo que aparece en los primeros 120 caracteres (el título) pesa el doble;
  - por el nombre basta 1 punto; por el contenido hacen falta 2.

## Acciones genéricas

- Cada acción: `nombre` (único, minúsculas-con-guiones), `descripcion`, `tipo`.
- Tipos: `mover` y `copiar` (requieren `destino`), `renombrar` (requiere `plantilla`), `borrar` (siempre pide confirmación salvo `--si`).
- `filtro` opcional: `extensiones` (lista, en minúsculas), `patron` (regex válida), `mas_antiguo_que_dias`, `mayor_que_mb`.
- `plantilla`: huecos `{fecha:%Y-%m-%d}`, `{n:03}`, `{ext}`, `{nombre}`.

## El ciclo: analizar → organizar → deshacer

1. **`tareas analizar`** recorre la carpeta, extrae el texto de cada documento,
   renombra los que tienen nombres incompatibles y escribe una **ficha .md**
   en la carpeta `md`. La ficha es el portador de datos: la leen `organizar`,
   `deshacer`, `resumir` y `evaluar`.
2. **`tareas organizar`** lee las fichas, mueve cada documento a su carpeta y
   le **devuelve el nombre original**. La ficha va con él, en la carpeta `md`
   de la asignatura.
3. **`tareas deshacer`** lo devuelve todo a su sitio. Las fichas se conservan.

## Reglas al programar

- Valida el JSON en `config.py` ANTES de ejecutar; errores con `AccionNoValida(accion, campo, motivo)` y `CarpetaNoValida(carpeta, campo, motivo)`.
- `pathlib` y `shutil`; `encoding="utf-8"`; nunca `shell=True`; nunca sobrescribir (`sin_conflicto`).
- Compara nombres **normalizados a NFC** (`nombres.mismo_nombre`): un fichero en NFD y el nombre tecleado en NFC se ven iguales pero no lo son.
- Si cambias el esquema de la ficha `.md`, actualiza `ficha.py` **y** el README: la leen cuatro órdenes.

## La capa de IA

- `ia.py` es el **único** módulo que habla con el servidor de modelos. Ningún
  otro abre una conexión.
- `busqueda.py` es el **único** módulo que abre una conexión a internet
  (Wikipedia y DuckDuckGo, sin claves).
- La configuración sale de `TAREAS_IA_URL`, `TAREAS_IA_KEY`, `TAREAS_MODELO`,
  `TAREAS_IA_CA` y `TAREAS_IA_TIMEOUT`, o de un `.env`. **La clave nunca se
  escribe en el repo**: el `.env` está en el `.gitignore` desde el primer
  commit y hay un `.env.example` que lo documenta.
- Si no hay clave o no hay red, se lanza `ErrorIA` con un mensaje de **una
  línea**. La CLI lo captura y cae a la versión extractiva: **ninguna orden
  puede reventar con una traza** por un problema de red.
- **Las pruebas no salen a la red.** El fixture automático de
  `tests/conftest.py` aparta la configuración de la IA; la llamada al
  servidor se simula en `tests/test_ia.py` y `tests/test_ia_busqueda.py`. Las
  pruebas que sí necesitan el modelo de verdad van marcadas con
  `@pytest.mark.ia` y solo se ejecutan con `uv run pytest -m ia`.

### El protocolo de búsqueda

El modelo **no** tiene herramienta de búsqueda. Cuando necesita información que
no tiene, escribe una línea con esta forma y termina su turno:

```
[[BUSCAR: consulta]]
```

`ia.pedir_con_busqueda()` la busca, le pasa los resultados y le vuelve a
preguntar. **Quien decide si hace falta buscar es el modelo**, no el código: si
el documento está bien, no busca nada.

Si añades un paso nuevo que necesite internet, usa `pedir_con_busqueda()` y no
montes tu propio bucle. Y devuelve las fuentes: se escriben al final del
documento.

### Lo que devuelve el modelo

Markdown. `markdown.py` lo traduce a las secciones del documento: encabezados
de dos niveles, viñetas, tablas con tabuladores y negritas de verdad en el
`.odt` y el `.docx`.

### El comando `clasificar`

`agrupador.py` agrupa documentos en carpetas **decididas por la IA**, no por
`acciones.json`. El modelo responde con un formato muy simple (`[Carpeta]`
seguido de `- documento`) que la herramienta lee y sanea. Si añades un tipo de
agrupación, respeta ese formato: es lo que hace que funcione con cualquier
modelo.

## Trampas conocidas

- `patron` se evalúa sobre el **nombre completo** del fichero, con la extensión, y **sin distinguir mayúsculas**.
- Los filtros se combinan con Y: un fichero tiene que cumplir **todos** los que pongas.
- `extensiones` se comparan por sufijo del nombre, así que `".tar.gz"` sí funciona.
- El filtro **no baja a las subcarpetas**: solo mira el primer nivel.
- Los campos que la acción reconoce son una lista blanca. Escribir `patron` fuera de `filtro` es un error de configuración, no un descuido: si pasara, la acción se aplicaría a todos los ficheros de la carpeta.
- `analizar` genera las fichas en la subcarpeta `md`, que no se vuelve a recorrer porque es una carpeta.
- Los PDF se leen con `pdftotext` (las primeras 3 páginas). Sin esa herramienta, un PDF se marca como «formato invalido».
