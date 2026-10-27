---
name: acciones-json
description: Reglas del fichero acciones.json de la CLI tareas (campos, tipos, filtros, plantillas y validación). Úsala siempre que crees o cambies acciones o el código que las lee (config.py, acciones.py, motor.py).
---

# Esquema de acciones.json

- Raíz: `{"version": 1, "acciones": [...]}`. Cada acción: `nombre` (único, minúsculas-con-guiones), `descripcion`, `tipo`.
- Tipos: `mover` y `copiar` (requieren `destino`), `renombrar` (requiere `plantilla`), `borrar` (siempre pide confirmación salvo `--si`).
- `filtro` opcional: `extensiones` (lista, en minúsculas), `patron` (regex válida), `mas_antiguo_que_dias`, `mayor_que_mb`.
- `plantilla`: huecos `{fecha:%Y-%m-%d}`, `{n:03}`, `{ext}`, `{nombre}`.

## Reglas al programar

- Valida el JSON en `config.py` ANTES de ejecutar; errores con `AccionNoValida(accion, campo, motivo)`.
- `pathlib` y `shutil`; `encoding="utf-8"`; nunca `shell=True`; nunca sobrescribir (`destino_libre`).
- Toda acción admite `--simular` y devuelve `list[Resultado]`.
- Si añades un campo o un tipo nuevo, documéntalo en el README y en esta skill.

## Cómo son las acciones de este proyecto

- Las acciones reales viven en `acciones.json` (11 acciones) y las de prueba en
  `pruebas/acciones-prueba.json`, con todas las rutas dentro de `~/pruebas-tareas`.
- Las seis acciones `apuntes-*` reparten ficheros por asignatura **leyendo el nombre**
  con `filtro.patron`. Es deliberado: si el nombre no dice nada, el fichero no se mueve.
  Si el nombre dice algo, el fichero no se mueve; se queda en Descargas.
- `origen` y `destino` admiten `~`; se expanden con `Path.expanduser()`.
- Los patrones van con el flag `(?i)` al principio para que no importen las mayúsculas.
- En JSON, la barra invertida se escribe doble: `c\\+\\+` para buscar `c++`.

## Trampas conocidas

- `patron` se evalúa sobre el **nombre completo** del fichero, con la extensión.
- Los filtros se combinan con Y: un fichero tiene que cumplir **todos** los que pongas.
- `mayor_que_mb` compara con `>=` el tamaño en MB; `mas_antiguo_que_dias` mira la fecha
  de **modificación**, no la de creación.
- `borrar` no admite `confirmar: false`: `config.py` lo rechaza a propósito.
