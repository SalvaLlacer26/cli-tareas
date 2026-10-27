# tareas · CLI de tareas con ficheros (proyecto de 1º DAM)

## Stack y órdenes
- Python 3.12 + Typer + Rich, gestionado con uv (src layout, paquete `src/tareas`).
- Ejecutar: `uv run tareas --help` · Validar config: `uv run tareas validar` · Pruebas (semana 4): `uv run pytest`.

## Normas
- Mensajes y comentarios en español; código claro antes que listo.
- `pathlib` siempre, `encoding="utf-8"`, nada de `os.system` ni `shell=True`: tiene que funcionar en Linux, Windows y macOS.
- Nunca ejecutes acciones sobre carpetas reales: solo en `~/pruebas-tareas` y con `--simular`.
- No toques `.env` ni escribas claves en ningún fichero. No hagas `git push` ni commits: los hace el alumno.
- Antes de cambiar un fichero, explica en 2-3 líneas qué vas a hacer.
