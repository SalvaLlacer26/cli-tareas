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

## Trampas conocidas

- `patron` se evalúa sobre el **nombre completo** del fichero, con la extensión, y **sin distinguir mayúsculas**.
- Los filtros se combinan con Y: un fichero tiene que cumplir **todos** los que pongas.
- `extensiones` se comparan por sufijo del nombre, así que `".tar.gz"` sí funciona.
- El filtro **no baja a las subcarpetas**: solo mira el primer nivel.
- Los campos que la acción reconoce son una lista blanca. Escribir `patron` fuera de `filtro` es un error de configuración, no un descuido: si pasara, la acción se aplicaría a todos los ficheros de la carpeta.
- `analizar` genera las fichas en la subcarpeta `md`, que no se vuelve a recorrer porque es una carpeta.
- Los PDF se leen con `pdftotext` (las primeras 3 páginas). Sin esa herramienta, un PDF se marca como «formato invalido».
