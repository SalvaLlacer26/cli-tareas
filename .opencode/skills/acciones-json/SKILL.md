---
name: acciones-json
description: Reglas del fichero acciones.json de la CLI tareas (campos, tipos, carpetas, filtros, plantillas y validación). Úsala siempre que crees o cambies acciones, carpetas de destino o el código que las lee (config.py, acciones.py, motor.py, carpetas.py, organizador.py).
---

# Esquema de acciones.json

Raíz: `{"version": 1, "acciones": [...], "carpetas": [...], "organizador": {...}}`.

## Acciones

- Cada acción: `nombre` (único, minúsculas-con-guiones), `descripcion`, `tipo`.
- Tipos: `mover` y `copiar` (requieren `destino`), `renombrar` (requiere `plantilla`), `borrar` (siempre pide confirmación salvo `--si`).
- `filtro` opcional: `extensiones` (lista, en minúsculas), `patron` (regex válida), `mas_antiguo_que_dias`, `mayor_que_mb`.
- `plantilla`: huecos `{fecha:%Y-%m-%d}`, `{n:03}`, `{ext}`, `{nombre}`.

## Carpetas (las asignaturas)

- Cada carpeta: `clave` (obligatoria, p. ej. `bbdd`), `etiqueta`, `destino`, `patrones`, `respaldo`.
- Una acción puede apuntar a una carpeta con `"carpeta": "bbdd"` y **hereda** su `destino` y sus `patrones`. Así la asignatura se escribe una sola vez.
- La clave cuenta siempre como patrón: un fichero que empieza por `bbdd_` es interpretable aunque su nombre no diga nada más.
- Una carpeta con `"respaldo": true` recibe lo que no se ha podido clasificar. Sin ella, se usa la primera que no tenga patrones.

## Reglas al programar

- Valida el JSON en `config.py` ANTES de ejecutar; errores con `AccionNoValida(accion, campo, motivo)` y `CarpetaNoValida(carpeta, campo, motivo)`.
- `pathlib` y `shutil`; `encoding="utf-8"`; nunca `shell=True`; nunca sobrescribir (`destino_libre`).
- Toda acción admite `--simular` y devuelve `list[Resultado]`.
- Si añades un campo o un tipo nuevo, documéntalo en el README y en esta skill.

## Cómo son las acciones de este proyecto

- Las acciones reales viven en `acciones.json` (11 acciones) y las de prueba en
  `pruebas/acciones-prueba.json`, con todas las rutas dentro de `~/pruebas-tareas`.
- Las seis acciones `apuntes-*` heredan de la carpeta `carpetas` con la misma clave.
- `origen` y `destino` admiten `~`; se expanden con `Path.expanduser()`.
- Los patrones no necesitan el flag `(?i)`: el motor los compila con `re.IGNORECASE`.
- Los resúmenes `.md` que van al lado de un documento se mueven con él, no por su cuenta.

## Trampas conocidas

- `patron` se evalúa sobre el **nombre completo** del fichero, con la extensión,
  y **sin distinguir mayúsculas** (el motor lo compila con `re.IGNORECASE`).
  No hace falta escribir `(?i)`.
- Los filtros se combinan con Y: un fichero tiene que cumplir **todos** los que pongas.
- `extensiones` se comparan por sufijo del nombre, así que `".tar.gz"` sí funciona
  (con `Path.suffix` solo se vería `".gz"`).
- `mayor_que_mb` compara con `>=` el tamaño en MB; `mas_antiguo_que_dias` mira la fecha
  de **modificación**, no la de creación.
- `borrar` no admite `confirmar: false`: `config.py` lo rechaza a propósito.
- El filtro **no baja a las subcarpetas**: solo mira el primer nivel.
- Los campos que la acción reconoce son una lista blanca (`nombre`, `descripcion`,
  `tipo`, `carpeta`, `origen`, `filtro`, `destino`, `plantilla`, `confirmar`).
  Escribir `patron` fuera de `filtro` es un error de configuración, no un descuido:
  si pasara, la acción se aplicaría a todos los ficheros de la carpeta.
- La clasificación **cuenta** patrones y gana la carpeta con más aciertos, no la
  primera que coincide. Por eso «Projecte Intermodular 1DAW» va a intermodular
  y no a entornos, aunque también mentione «github».
